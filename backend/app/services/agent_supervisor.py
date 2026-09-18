"""
MDIN Steps 14-15: Central Agentic Supervisor for the CareStack Multi-Agent Orchestrator (MAO).

`AgenticSupervisor` compiles a LangGraph StateGraph over the shared `MAOState` and hands the
state between four agent nodes:

    START -> intake_agent -> risk_agent -+-> clearance_agent -> END   (only if REQUIRED_PENDING)
                                         +-> billing_agent   -> END   (always; parallel with clearance)

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

from .agents import ClinicalRiskAgent, CommercialBillingAgent, IntakeAgent, MedicalClearanceAgent
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

def route_after_risk(state: MAOState) -> List[str]:
    """
    Conditional fan-out: when the Risk agent demands physician clearance, the Clearance and Billing
    agents run in parallel (same superstep); otherwise Billing runs alone.
    """
    if state.get("clearance_status") == "REQUIRED_PENDING":
        return [CLEARANCE_NODE, BILLING_NODE]
    return [BILLING_NODE]


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
            INTAKE_NODE: IntakeAgent(),
            RISK_NODE: ClinicalRiskAgent(),
            CLEARANCE_NODE: MedicalClearanceAgent(),
            BILLING_NODE: CommercialBillingAgent(),
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
        builder.add_edge(CLEARANCE_NODE, END)
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
        for name in (INTAKE_NODE, RISK_NODE):
            update = await self.nodes[name](state)
            state = merge_state(state, update)
            yield {name: update}
        branch = route_after_risk(state)
        updates = await asyncio.gather(*(self.nodes[name](state) for name in branch))
        for name, update in zip(branch, updates):
            yield {name: update}

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
        simulation: Optional[Dict[str, Any]] = None,
    ) -> SupervisorThread:
        state = create_initial_state(
            patient_id=patient_id,
            cdt_codes=cdt_codes,
            appointment_timestamp=appointment_timestamp,
            operatory=operatory,
            simulation=simulation,
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

    # -- asynchronous clearance loop (after the graph has finished) ---------

    def _apply_followup(self, thread: SupervisorThread, node: str, update: Dict[str, Any]) -> None:
        thread.state = merge_state(thread.state, update)
        validate_state(thread.state)
        self._publish(thread, "agent_step", node=node,
                      data={"logs": update.get("agent_logs", []), "state": thread.state})

    async def ingest_physician_response(
        self, patient_id: str, text: str, signed_by: Optional[str] = None
    ) -> SupervisorThread:
        """
        Physician reply arrives (EHR callback / portal): the Clearance agent parses it into structured
        restrictions and clears the appointment, then the Billing agent refreshes the LOMN so it cites
        the signed clearance.
        """
        thread = self.get_thread(patient_id)
        if thread is None:
            raise KeyError(f"No supervisor thread for patient '{patient_id}'")
        if thread.state.get("clearance_status") != "TRANSMITTED_TO_EHR":
            raise ValueError(
                f"No clearance request awaiting a response (clearance_status="
                f"{thread.state.get('clearance_status')})"
            )
        update = self.nodes[CLEARANCE_NODE].ingest_physician_response(thread.state, text, signed_by)
        self._apply_followup(thread, CLEARANCE_NODE, update)
        if thread.state["appointment"].get("status") == "CLEARED_FOR_CARE" and thread.state.get("cross_bill_eligible"):
            self._apply_followup(thread, BILLING_NODE, await self.nodes[BILLING_NODE](thread.state))
        return thread

    def check_escalations(self, hours_since_dispatch: Optional[float] = None) -> List[SupervisorThread]:
        """Runs the 48h escalation check over every thread awaiting a physician. Returns escalated threads."""
        escalated = []
        for thread in self.threads.values():
            update = self.nodes[CLEARANCE_NODE].check_escalation(thread.state, hours_since_dispatch)
            if update:
                self._apply_followup(thread, CLEARANCE_NODE, update)
                escalated.append(thread)
        return escalated

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
            simulation=payload.get("simulation"),
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
                [RISK_NODE, f"{CLEARANCE_NODE} (parallel branch, only if clearance_status == REQUIRED_PENDING)"],
                [RISK_NODE, f"{BILLING_NODE} (always)"],
                [CLEARANCE_NODE, "END"],
                [BILLING_NODE, "END"],
            ],
            "trigger_events": sorted(TRIGGER_EVENTS),
            "active_threads": [
                {k: v for k, v in t.summary().items() if k != "state"} for t in self.threads.values()
            ],
        }


agent_supervisor = AgenticSupervisor()
