"""
MDIN Step 14: Central Agentic Supervisor for the CareStack Multi-Agent Orchestrator (MAO).

`AgenticSupervisor` compiles a LangGraph StateGraph over the shared `MAOState` and hands the
state between four agent nodes:

    START -> intake -> risk -> (clearance if REQUIRED_PENDING) -> billing -> END

It runs continuously in the background: CareStack appointment bookings / webhook events are
queued with `submit_event`, consumed by a worker task, and every node transition is published
to per-patient subscribers so the frontend can render agent reasoning in real time
(`GET /api/agents/stream/{patient_id}`).

If LangGraph is not importable the supervisor falls back to an equivalent deterministic
state-transition loop, so the API stays functional.
"""

import asyncio
import logging
import uuid
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from ..models.agent_state import (
    MAOState,
    create_initial_state,
    make_agent_log,
    utc_now_iso,
    validate_state,
)

try:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without langgraph installed
    LANGGRAPH_AVAILABLE = False

logger = logging.getLogger(__name__)

INTAKE_NODE = "intake_agent"
RISK_NODE = "risk_agent"
CLEARANCE_NODE = "clearance_agent"
BILLING_NODE = "billing_agent"

# Channels merged with operator.add in MAOState (nodes return only new entries)
APPEND_CHANNELS = ("risk_evaluations", "agent_logs")

# Event types accepted from CareStack / webhooks that start a supervisor thread
TRIGGER_EVENTS = {
    "appointment.booked",
    "appointment.updated",
    "treatment_plan.procedure_added",
    "recall.due",
    "manual.run",
}

HAZARD_ORDER = {"LOW": 0, "MODERATE": 1, "CRITICAL": 2}


def _is_invasive(cdt_code: str) -> bool:
    """Oral surgery (D7xxx), periodontal surgery (D42xx) and implant placement (D60xx)."""
    code = (cdt_code or "").upper()
    return code.startswith("D7") or code.startswith("D42") or code.startswith("D60")


def _resource_text(resource: Dict[str, Any], field: str) -> str:
    concept = resource.get(field) or {}
    if concept.get("text"):
        return concept["text"]
    codings = concept.get("coding") or [{}]
    return codings[0].get("display") or codings[0].get("code") or ""


def _clearance_service():
    """
    Lazy accessor: clearance_engine and the routers package import each other, and the cycle only
    resolves when the routers package is loaded first (as it is under the FastAPI app).
    """
    from .. import routers  # noqa: F401
    from .clearance_engine import medical_clearance_service

    return medical_clearance_service


# ---------------------------------------------------------------------------
# Agent nodes
# ---------------------------------------------------------------------------

class IntakeAgentNode:
    """Pulls the patient's demographics and medical history into the shared state."""

    name = "Intake Agent"
    icon = "clipboard-list"

    async def __call__(self, state: MAOState) -> Dict[str, Any]:
        medical_clearance_service = _clearance_service()

        patient_id = state["patient_id"]
        info = medical_clearance_service._resolve_patient_info(patient_id)
        found = bool(info.get("cs_patient") or info.get("fhir_patient"))

        conditions = [t for t in (_resource_text(c, "code") for c in info.get("conditions", [])) if t]
        medications = [
            t for t in (_resource_text(m, "medicationCodeableConcept") for m in info.get("medications", [])) if t
        ]
        allergies = [t for t in (_resource_text(a, "code") for a in info.get("allergies", [])) if t]

        entries = [{"resource": r} for key in ("conditions", "medications", "allergies") for r in info.get(key, [])]
        if info.get("fhir_patient"):
            entries.insert(0, {"resource": info["fhir_patient"]})

        if found:
            log = make_agent_log(
                self.name,
                "Linked external medical record",
                f"Retrieved {len(conditions)} conditions, {len(medications)} medications and "
                f"{len(allergies)} allergies from the FHIR R4 EHR.",
                self.icon,
            )
        else:
            log = make_agent_log(
                self.name,
                "No external medical record found",
                f"Patient '{patient_id}' is not linked to a medical EHR; conversational intake required.",
                self.icon,
            )

        return {
            "patient_name": state.get("patient_name") or (info.get("name") if found else "") or "",
            "dob": state.get("dob") or (info.get("dob") if found else "") or "",
            "medical_records": {
                "conditions": conditions,
                "medications": medications,
                "allergies": allergies,
                "raw_fhir_bundle": {"resourceType": "Bundle", "type": "collection", "entry": entries},
            },
            "intake_status": "PORTAL_LINKED" if found else "PENDING",
            "agent_logs": [log],
        }


class RiskAgentNode:
    """Evaluates the scheduled CDT procedures against the patient's systemic profile."""

    name = "Clinical Risk Agent"
    icon = "shield-alert"

    # (keywords, hazard when invasive, contraindication, recommendation)
    RULES = [
        (
            ("warfarin", "coumadin", "apixaban", "eliquis", "rivaroxaban", "xarelto", "dabigatran", "anticoagul"),
            "CRITICAL",
            "Active anticoagulant therapy: post-operative hemorrhage hazard",
            "Obtain physician clearance and a current INR before the procedure; plan local hemostatic measures.",
        ),
        (
            ("clopidogrel", "plavix", "prasugrel", "ticagrelor", "stent"),
            "CRITICAL",
            "Antiplatelet therapy / coronary stent: ischemic and bleeding liability",
            "Do not interrupt antiplatelet therapy without cardiology review; limit epinephrine dosing.",
        ),
        (
            ("alendronate", "fosamax", "zoledronic", "reclast", "bisphosphonate", "denosumab", "prolia"),
            "CRITICAL",
            "Antiresorptive therapy: medication-related osteonecrosis of the jaw (MRONJ) risk",
            "Confirm therapy duration with the prescriber and consider conservative alternatives to extraction.",
        ),
        (
            ("diabetes",),
            "MODERATE",
            "Diabetes mellitus: impaired healing and infection risk",
            "Verify recent HbA1c and schedule a morning appointment after a normal meal.",
        ),
        (
            ("hypertension",),
            "MODERATE",
            "Hypertension: hemodynamic sensitivity to vasoconstrictors",
            "Record pre-operative blood pressure and limit epinephrine-containing anesthetic.",
        ),
    ]

    async def __call__(self, state: MAOState) -> Dict[str, Any]:
        records = state.get("medical_records") or {}
        appointment = dict(state.get("appointment") or {})
        cdt_codes = appointment.get("cdt_codes") or []
        invasive = [c for c in cdt_codes if _is_invasive(c)]
        profile = " | ".join(records.get("conditions", []) + records.get("medications", [])).lower()

        hazard = "LOW"
        contraindications: List[str] = []
        recommendations: List[str] = []
        for keywords, level, contraindication, recommendation in self.RULES:
            if not any(k in profile for k in keywords):
                continue
            # Systemic findings only become procedural hazards for invasive care
            effective = level if invasive else "LOW"
            if HAZARD_ORDER[effective] > HAZARD_ORDER[hazard]:
                hazard = effective
            contraindications.append(contraindication)
            recommendations.append(recommendation)

        clearance_required = hazard == "CRITICAL"
        if clearance_required:
            appointment["status"] = "REQUIRES_ACTION"

        evaluation = {
            "hazard_level": hazard,
            "contraindications": contraindications,
            "clinical_recommendations": recommendations,
            "cdt_codes": cdt_codes,
            "evaluated_at": utc_now_iso(),
        }
        log = make_agent_log(
            self.name,
            f"Hazard level {hazard}",
            (
                f"Evaluated {', '.join(cdt_codes) or 'no procedures'} against "
                f"{len(records.get('conditions', []))} conditions / {len(records.get('medications', []))} medications. "
                + ("Physician clearance required." if clearance_required else "No physician clearance required.")
            ),
            self.icon,
        )
        return {
            "risk_evaluations": [evaluation],
            "clearance_status": "REQUIRED_PENDING" if clearance_required else "NOT_REQUIRED",
            "appointment": appointment,
            "agent_logs": [log],
        }


class ClearanceAgentNode:
    """Locates the attending physician and transmits a Digital Clearance Passport to their EHR."""

    name = "Medical Clearance Agent"
    icon = "stethoscope"

    async def __call__(self, state: MAOState) -> Dict[str, Any]:
        medical_clearance_service = _clearance_service()

        cdt_codes = (state.get("appointment") or {}).get("cdt_codes") or []
        cdt_code = next((c for c in cdt_codes if _is_invasive(c)), cdt_codes[0] if cdt_codes else "D7140")

        passport = medical_clearance_service.create_clearance_passport(
            patient_id=state["patient_id"], cdt_code=cdt_code
        )
        physician = passport.physician
        log = make_agent_log(
            self.name,
            "Dispatched FHIR Task to physician EHR",
            f"Clearance passport {passport.request_id} for {cdt_code} transmitted to {physician.name} "
            f"({physician.facility_name}).",
            self.icon,
        )
        return {
            "clearance_status": "TRANSMITTED_TO_EHR",
            "assigned_medical_md": {
                "name": physician.name,
                "npi": physician.npi,
                "facility": physician.facility_name,
                "specialty": physician.specialty,
                "direct_endpoint": physician.fhir_endpoint,
            },
            "agent_logs": [log],
        }


class CommercialBillingAgentNode:
    """Evaluates CDT -> CPT medical cross-coding eligibility for the scheduled procedures."""

    name = "Commercial Billing Agent"
    icon = "receipt"

    async def __call__(self, state: MAOState) -> Dict[str, Any]:
        from .crosswalk_engine import crosswalk_engine

        cdt_codes = (state.get("appointment") or {}).get("cdt_codes") or []
        best = None
        for cdt_code in cdt_codes:
            try:
                opportunity = crosswalk_engine.evaluate_patient(state["patient_id"], cdt_code)
            except Exception as exc:  # unknown patient / unmapped code is not fatal to the thread
                logger.warning("Cross-coding evaluation failed for %s/%s: %s", state["patient_id"], cdt_code, exc)
                continue
            if opportunity.is_eligible and (best is None or opportunity.estimated_coverage > best.estimated_coverage):
                best = opportunity

        if best is None:
            return {
                "cross_bill_eligible": False,
                "agent_logs": [
                    make_agent_log(
                        self.name,
                        "No medical cross-billing opportunity",
                        f"No qualifying ICD-10 justification for {', '.join(cdt_codes) or 'the scheduled visit'}.",
                        self.icon,
                    )
                ],
            }

        return {
            "cross_bill_eligible": True,
            "commercial_claims": {
                "suggested_cpt": best.suggested_cpt or "",
                "justifying_icd10": best.justifying_icd10,
                "estimated_savings": float(best.estimated_coverage),
                "cms1500_ready": best.claim_preview is not None,
                "lomn_attached": False,
            },
            "agent_logs": [
                make_agent_log(
                    self.name,
                    f"Cross-coded {best.cdt_code} to CPT {best.suggested_cpt}",
                    f"Justified by {', '.join(best.justifying_icd10)}; estimated medical coverage "
                    f"${best.estimated_coverage:,.2f}.",
                    self.icon,
                )
            ],
        }


def route_after_risk(state: MAOState) -> str:
    """Conditional handoff: physician clearance only when the Risk agent demands it."""
    return CLEARANCE_NODE if state.get("clearance_status") == "REQUIRED_PENDING" else BILLING_NODE


def merge_state(state: MAOState, update: Dict[str, Any]) -> MAOState:
    """Applies a node's partial update with the same reducer semantics as the LangGraph channels."""
    merged = dict(state)
    for key, value in update.items():
        if key in APPEND_CHANNELS:
            merged[key] = list(merged.get(key) or []) + list(value or [])
        else:
            merged[key] = value
    return MAOState(**merged)


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------

class SupervisorThread:
    """Execution record for one supervisor run over a single patient."""

    def __init__(self, patient_id: str, state: MAOState, trigger: str):
        self.thread_id = f"{patient_id}:{uuid.uuid4().hex[:8]}"
        self.patient_id = patient_id
        self.trigger = trigger
        self.state = state
        self.status = "QUEUED"  # QUEUED | RUNNING | COMPLETED | FAILED
        self.started_at = utc_now_iso()
        self.completed_at: Optional[str] = None
        self.error: Optional[str] = None
        self.events: List[Dict[str, Any]] = []

    @property
    def finished(self) -> bool:
        return self.status in ("COMPLETED", "FAILED")

    def summary(self) -> Dict[str, Any]:
        return {
            "thread_id": self.thread_id,
            "patient_id": self.patient_id,
            "trigger": self.trigger,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "state": self.state,
        }


class AgenticSupervisor:
    """Central supervisor owning the agent graph, background event loop and execution streams."""

    def __init__(self, step_delay_seconds: float = 0.0):
        self.step_delay_seconds = step_delay_seconds
        self.nodes: Dict[str, Callable[[MAOState], Any]] = {
            INTAKE_NODE: IntakeAgentNode(),
            RISK_NODE: RiskAgentNode(),
            CLEARANCE_NODE: ClearanceAgentNode(),
            BILLING_NODE: CommercialBillingAgentNode(),
        }
        self.engine = "langgraph" if LANGGRAPH_AVAILABLE else "deterministic"
        self.graph = self._build_graph() if LANGGRAPH_AVAILABLE else None

        self.threads: Dict[str, SupervisorThread] = {}  # latest thread per patient (key: lowercased id)
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._event_queue: Optional[asyncio.Queue] = None
        self._worker: Optional[asyncio.Task] = None
        self._tasks: set = set()  # strong refs so in-flight thread tasks are not garbage collected
        self._listeners: List[Callable[[Dict[str, Any]], Any]] = []

    # -- graph ------------------------------------------------------------

    def _build_graph(self):
        builder = StateGraph(MAOState)
        for name, node in self.nodes.items():
            builder.add_node(name, node)
        builder.add_edge(START, INTAKE_NODE)
        builder.add_edge(INTAKE_NODE, RISK_NODE)
        builder.add_conditional_edges(RISK_NODE, route_after_risk, [CLEARANCE_NODE, BILLING_NODE])
        builder.add_edge(CLEARANCE_NODE, BILLING_NODE)
        builder.add_edge(BILLING_NODE, END)
        return builder.compile(checkpointer=InMemorySaver())

    async def _iterate_nodes(self, thread: SupervisorThread) -> AsyncIterator[Dict[str, Dict[str, Any]]]:
        """Yields `{node_name: partial_update}` per executed node, from LangGraph or the fallback loop."""
        if self.graph is not None:
            config = {"configurable": {"thread_id": thread.thread_id}}
            async for chunk in self.graph.astream(thread.state, config, stream_mode="updates"):
                yield chunk
            return

        state = thread.state
        current = INTAKE_NODE
        while current:
            update = await self.nodes[current](state)
            state = merge_state(state, update)
            yield {current: update}
            if current == INTAKE_NODE:
                current = RISK_NODE
            elif current == RISK_NODE:
                current = route_after_risk(state)
            elif current == CLEARANCE_NODE:
                current = BILLING_NODE
            else:
                current = None

    # -- execution --------------------------------------------------------

    def _key(self, patient_id: str) -> str:
        return patient_id.strip().lower()

    def create_thread(
        self,
        patient_id: str,
        cdt_codes: Optional[List[str]] = None,
        trigger: str = "manual.run",
        appointment_timestamp: Optional[str] = None,
        operatory: str = "",
    ) -> SupervisorThread:
        state = create_initial_state(
            patient_id=patient_id,
            cdt_codes=cdt_codes,
            appointment_timestamp=appointment_timestamp,
            operatory=operatory,
        )
        thread = SupervisorThread(patient_id, state, trigger)
        self.threads[self._key(patient_id)] = thread
        return thread

    async def run_thread(self, thread: SupervisorThread) -> SupervisorThread:
        """Executes the agent graph for a thread, publishing one event per state handoff."""
        thread.status = "RUNNING"
        self._publish(thread, "thread_started", data={"trigger": thread.trigger, "engine": self.engine})
        try:
            async for chunk in self._iterate_nodes(thread):
                for node_name, update in chunk.items():
                    if not isinstance(update, dict):
                        continue
                    thread.state = merge_state(thread.state, update)
                    self._publish(
                        thread,
                        "agent_step",
                        node=node_name,
                        data={"logs": update.get("agent_logs", []), "state": thread.state},
                    )
                    if self.step_delay_seconds:
                        await asyncio.sleep(self.step_delay_seconds)
            validate_state(thread.state)
            thread.status = "COMPLETED"
        except Exception as exc:
            logger.exception("Supervisor thread %s failed", thread.thread_id)
            thread.status = "FAILED"
            thread.error = str(exc)
        thread.completed_at = utc_now_iso()
        self._publish(
            thread,
            "thread_completed" if thread.status == "COMPLETED" else "thread_failed",
            data={"state": thread.state, "error": thread.error},
        )
        return thread

    async def run(self, patient_id: str, cdt_codes: Optional[List[str]] = None, **kwargs) -> SupervisorThread:
        """Runs a full supervisor thread inline and returns it once finished."""
        return await self.run_thread(self.create_thread(patient_id, cdt_codes, **kwargs))

    # -- background loop & event listeners ---------------------------------

    async def start(self) -> None:
        """Starts the continuous background worker (idempotent). Call from the app lifespan."""
        if self._worker and not self._worker.done():
            return
        self._event_queue = asyncio.Queue()
        self._worker = asyncio.create_task(self._worker_loop(), name="mao-supervisor")

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        self._worker = None
        self._event_queue = None

    @property
    def running(self) -> bool:
        return bool(self._worker and not self._worker.done())

    def add_listener(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        """Registers a callback (sync or async) invoked with every published supervisor event."""
        self._listeners.append(callback)

    async def submit_event(self, event_type: str, payload: Dict[str, Any]) -> SupervisorThread:
        """
        Entry point for CareStack appointment bookings / webhooks. Creates the thread immediately
        (so streams can attach) and runs it on the background worker, or inline if no worker is up.
        """
        if event_type not in TRIGGER_EVENTS:
            raise ValueError(f"Unsupported event type '{event_type}'. Expected one of {sorted(TRIGGER_EVENTS)}")
        patient_id = str(payload.get("patient_id") or payload.get("PatientId") or "").strip()
        if not patient_id:
            raise ValueError("Event payload requires 'patient_id'")

        cdt_codes = payload.get("cdt_codes") or ([payload["cdt_code"]] if payload.get("cdt_code") else [])
        thread = self.create_thread(
            patient_id,
            cdt_codes=cdt_codes,
            trigger=event_type,
            appointment_timestamp=payload.get("timestamp") or payload.get("DateTime"),
            operatory=str(payload.get("operatory") or payload.get("OperatoryId") or ""),
        )
        if self.running and self._event_queue is not None:
            await self._event_queue.put(thread)
        else:
            await self.run_thread(thread)
        return thread

    async def _worker_loop(self) -> None:
        assert self._event_queue is not None
        while True:
            thread = await self._event_queue.get()
            # Each thread runs as its own task so a slow patient never blocks the queue
            task = asyncio.create_task(self.run_thread(thread), name=f"mao-{thread.thread_id}")
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    # -- streaming ---------------------------------------------------------

    def get_thread(self, patient_id: str) -> Optional[SupervisorThread]:
        return self.threads.get(self._key(patient_id))

    def _publish(self, thread: SupervisorThread, event_type: str, node: Optional[str] = None, data: Any = None) -> None:
        event = {
            "type": event_type,
            "thread_id": thread.thread_id,
            "patient_id": thread.patient_id,
            "node": node,
            "sequence": len(thread.events),
            "timestamp": utc_now_iso(),
            "data": data or {},
        }
        thread.events.append(event)
        for queue in self._subscribers.get(thread.thread_id, []):
            queue.put_nowait(event)
        for listener in self._listeners:
            try:
                result = listener(event)
                if asyncio.iscoroutine(result):
                    asyncio.ensure_future(result)
            except Exception:
                logger.exception("MAO event listener failed")

    async def stream(self, patient_id: str) -> AsyncIterator[Dict[str, Any]]:
        """Replays the patient's thread history, then follows it live until the thread finishes."""
        thread = self.get_thread(patient_id)
        if thread is None:
            return
        queue: asyncio.Queue = asyncio.Queue()
        subscribers = self._subscribers.setdefault(thread.thread_id, [])
        subscribers.append(queue)
        try:
            # No await between subscribing and snapshotting, so no event is missed or duplicated
            replay = list(thread.events)
            for event in replay:
                yield event
            if thread.finished:
                return
            while True:
                event = await queue.get()
                yield event
                if event["type"] in ("thread_completed", "thread_failed"):
                    return
        finally:
            subscribers.remove(queue)
            if not subscribers:
                self._subscribers.pop(thread.thread_id, None)

    def describe(self) -> Dict[str, Any]:
        return {
            "engine": self.engine,
            "background_worker_running": self.running,
            "nodes": list(self.nodes),
            "edges": [
                ["START", INTAKE_NODE],
                [INTAKE_NODE, RISK_NODE],
                [RISK_NODE, f"{CLEARANCE_NODE} (clearance_status == REQUIRED_PENDING)"],
                [RISK_NODE, f"{BILLING_NODE} (otherwise)"],
                [CLEARANCE_NODE, BILLING_NODE],
                [BILLING_NODE, "END"],
            ],
            "trigger_events": sorted(TRIGGER_EVENTS),
            "active_threads": [
                {k: v for k, v in t.summary().items() if k != "state"} for t in self.threads.values()
            ],
        }


agent_supervisor = AgenticSupervisor()
