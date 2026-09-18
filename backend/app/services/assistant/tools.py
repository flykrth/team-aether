"""
Tools the MAO Assistant can call. Read tools fetch patient history; action tools drive the
application (run the agent workflow, file a physician reply, post chart alerts, and - merged in
from record_tools.py - register patients and chart medical history). consult_specialists fans a
question out to the parallel specialist models.

Every tool returns a compact JSON-serializable dict: the model reads it, so raw FHIR bundles,
CMS-1500 payloads and letters are summarized rather than passed through.
"""

import re
from typing import Any, Awaitable, Callable, Dict, List

from ...models.agent_state import create_initial_state
from ..agents import ClinicalRiskAgent, IntakeAgent
from ..agents.base import carestack_services, clearance_service
from .context import record_tool_call, turn_recorder
from .chart_edit_tools import CHART_ACTION_TOOLS, CHART_TOOL_DECLARATIONS, CHART_TOOL_FUNCTIONS
from .record_tools import RECORD_ACTION_TOOLS, RECORD_TOOL_DECLARATIONS, RECORD_TOOL_FUNCTIONS
from .visit_tools import VISIT_ACTION_TOOLS, VISIT_TOOL_DECLARATIONS, VISIT_TOOL_FUNCTIONS

ACTION_TOOLS = {"run_agent_workflow", "submit_physician_reply", "check_clearance_escalations", "post_chart_alert"}
ACTION_TOOLS |= RECORD_ACTION_TOOLS | CHART_ACTION_TOOLS | VISIT_ACTION_TOOLS  # chart edits stay blocked after an import (see execute_tool)


def _supervisor():
    from ..agent_supervisor import agent_supervisor

    return agent_supervisor


def _summarize_state(thread) -> Dict[str, Any]:
    state = thread.state
    protocol = {k: v for k, v in (state.get("clearance_protocol") or {}).items() if k != "clinical_justification"}
    records = state.get("medical_records") or {}
    return {
        "thread_status": thread.status,
        "error": thread.error,
        "patient_id": state["patient_id"],
        "patient_name": state.get("patient_name"),
        "appointment": state.get("appointment"),
        "intake_status": state.get("intake_status"),
        "conditions": records.get("conditions"),
        "medications": records.get("medications"),
        "allergies": records.get("allergies"),
        "risk_evaluations": [
            {k: e.get(k) for k in ("hazard_level", "cdt_code", "contraindications", "clinical_recommendations")}
            for e in state.get("risk_evaluations") or []
        ],
        "clearance_status": state.get("clearance_status"),
        "assigned_physician": state.get("assigned_medical_md"),
        "clearance_protocol": protocol,
        "agent_log": [f"{l['agent_name']}: {l['action']}" for l in state.get("agent_logs") or []],
    }


# -- read tools -------------------------------------------------------------------

async def list_patients() -> Dict[str, Any]:
    carestack = carestack_services()
    return {"patients": [
        {
            "patient_id": p.id,
            "mrn": p.mrn,
            "name": f"{p.first_name} {p.last_name}",
            "birth_date": p.birth_date,
            "next_appointment": p.next_appointment,
            "planned_procedures": [f"{t.code} {t.description}" for t in p.active_treatment_plan],
        }
        for p in carestack.MOCK_PATIENTS
    ]}


async def get_patient_history(patient_id: str) -> Dict[str, Any]:
    from ..fhir_client import fhir_client

    from ..patient_registry import find_patient_id_by_name

    carestack = carestack_services()
    info = clearance_service()._resolve_patient_info(patient_id)
    cs_patient = carestack._find_carestack_patient(patient_id)
    if not cs_patient and not info.get("fhir_patient") and find_patient_id_by_name(patient_id):
        return await get_patient_history(find_patient_id_by_name(patient_id))  # exact "First Last", never a substring
    if not cs_patient and not info.get("fhir_patient"):
        return {"found": False, "message": f"No CareStack or EHR record matches '{patient_id}'. Use list_patients."}

    concepts = IntakeAgent().normalize_fhir(info)
    observations = await fhir_client.get_observations((info.get("fhir_patient") or {}).get("id") or patient_id)
    keys = {patient_id, cs_patient.id if cs_patient else patient_id}
    alerts = [a for k in keys for a in carestack.PATIENT_MEDICAL_ALERTS.get(k, [])]
    clearances = clearance_service().get_clearance_by_patient(patient_id)

    def pick(kind: str) -> List[Dict[str, Any]]:
        return [{k: c.get(k) for k in ("code", "display", "onset", "drug_class") if c.get(k)}
                for c in concepts if c["type"] == kind]

    return {
        "found": True,
        "patient_id": cs_patient.id if cs_patient else patient_id,
        "name": info.get("name"),
        "birth_date": info.get("dob"),
        "gender": info.get("gender"),
        "medical_record_linked": bool(info.get("fhir_patient")),
        "conditions": pick("condition"),
        "medications": pick("medication"),
        "allergies": pick("allergy"),
        "observations": [
            {
                "test": (o.get("code") or {}).get("text") or ((o.get("code") or {}).get("coding") or [{}])[0].get("display"),
                "value": (o.get("valueQuantity") or {}).get("value", o.get("valueString")),  # "pending", "positive"
                "unit": (o.get("valueQuantity") or {}).get("unit"),
                "date": (o.get("effectiveDateTime") or "")[:10],
            }
            for o in observations
        ],
        "dental": None if not cs_patient else {
            "last_visit": cs_patient.last_visit,
            "next_appointment": cs_patient.next_appointment,
            "primary_dentist": cs_patient.primary_dentist,
            "treatment_plan": [
                {"cdt_code": t.code, "description": t.description, "tooth": t.tooth_number, "status": t.status, "fee": t.cost}
                for t in cs_patient.active_treatment_plan
            ],
            "documents": [
                {k: d.get(k) for k in ("document_id", "document_type", "title", "upload_timestamp")}
                for d in (cs_patient.attached_documents or [])
            ],
        },
        "chart_alerts": [
            {k: a.get(k) for k in ("title", "details", "alert_type", "source", "created_at")}
            for a in {a["alert_id"]: a for a in alerts}.values()
        ],
        "clearance_requests": [
            {
                "request_id": str(c.request_id),
                "status": c.status,
                "physician": c.physician.name,
                "procedures": [p.get("cdt_code") for p in c.proposed_procedures],
                "physician_notes": c.conditions_or_notes,
            }
            for c in clearances
        ],
    }


async def assess_clinical_risk(patient_id: str, cdt_code: str = "", procedure: str = "", todays_notes: str = "") -> Dict[str, Any]:
    """The Risk check. Writes nothing to the chart; it does start (or update) the patient's visit, which carries the
    procedure and today's notes forward to the insurance step."""
    from .. import risk_check, visits
    from .context import turn_last_user_message, turn_user_text

    # A procedure code may come from the user or from the rules, never from the model. If the model passes a D-code the
    # user did not say, it is dropped and the user's own words are resolved instead.
    wanted = (procedure or cdt_code or "").strip()
    said = turn_user_text.get()
    if said is not None:
        for code in re.findall(r"\bD\d{4}\b", wanted.upper()):
            if code not in said.upper():
                wanted = re.sub(code, "", wanted, flags=re.I).strip(" ,.;:()-")
        if len(wanted) < 3:
            wanted = turn_last_user_message.get() or wanted
    procedure, cdt_code = wanted, ""

    try:
        result = await risk_check.check(patient_id, procedure or cdt_code, todays_notes, include_evidence=False, include_ai=False)
    except KeyError as exc:
        return {"found": False, "message": str(exc).strip("'\"")}
    return {
        "patient_id": result["patient_id"], "patient_name": result["patient_name"], "record_found": result["record_found"],
        "cdt_code": result["procedure"]["cdt_code"], "procedure": result["procedure"]["label"], "hazard_level": result["hazard_level"],
        "contraindications": [f["contraindication"] for f in result["findings"]],
        "clinical_recommendations": [r for f in result["findings"] for r in f["recommendations"]],
        "physician_clearance_required": result["physician_clearance_required"],
        "reported_today_not_on_chart": [c["display"] for c in result["reported_today"]],
        "next_step": visits.next_step(result["patient_id"]) if result.get("visit") else None,
    }


async def get_agent_state(patient_id: str) -> Dict[str, Any]:
    thread = _supervisor().get_thread(patient_id)
    if thread is None:
        return {"found": False, "message": "The agents have not run for this patient yet. Use run_agent_workflow."}
    return _summarize_state(thread)


async def consult_specialists(question: str, patient_id: str = "") -> Dict[str, Any]:
    """Read-only: parallel second opinions. The specialists get no tools and cannot act."""
    from .specialists import consult

    return await consult(question, patient_id or None)


async def check_medical_coverage_pathway(patient_id: str, procedure: str = "", clinical_note: str = "", diagnosis: str = "") -> Dict[str, Any]:
    """Read-only. The Dental Coverage Recovery pipeline: payer policy + member plan, every statement quoted and verified."""
    from ..coverage import analyst

    try:
        result = await analyst.analyze({"patient_id": patient_id, "procedure": procedure, "clinical_note": clinical_note,
                                        "diagnosis": diagnosis, "region": "US"})
    except (KeyError, ValueError) as exc:
        return {"found": False, "message": str(exc).strip("'\"")}
    return {
        "patient_id": result["patient_id"], "next_step": result.get("next_step"),
        "patient_name": result["patient_name"], "dental_benefit": result["insurance"]["dental"]["status"],
        "medical_insurer": result["insurance"]["medical"]["insurer"] or "not recorded",
        "outcome": result["determination"]["outcome"], "headline": result["determination"]["headline"],
        "reason": result["determination"]["reason"],
        "policy_quotes": [{"kind": c["kind"], "met": c["met"], "quote": c["quote"][:300], "source": f"{c['source']['insurer']} - {c['source']['title']}",
                           "url": c["source"]["url"]} for c in result.get("criteria", [])[:6]],
        "missing_information": result.get("missing_information", []),
        "note": "Only the payer decides coverage. A potential pathway means a pre-treatment estimate is worth requesting.",
    }


# -- action tools -------------------------------------------------------------------

async def run_agent_workflow(patient_id: str, cdt_code: str) -> Dict[str, Any]:
    thread = await _supervisor().run(patient_id, [cdt_code], trigger="manual.run")
    return _summarize_state(thread)


async def submit_physician_reply(patient_id: str, reply_text: str) -> Dict[str, Any]:
    try:
        thread = await _supervisor().ingest_physician_response(patient_id, reply_text)
    except (KeyError, ValueError) as exc:
        return {"ok": False, "message": str(exc).strip("'\"")}
    return _summarize_state(thread)


async def check_clearance_escalations(hours_since_dispatch: float = 0) -> Dict[str, Any]:
    escalated = _supervisor().check_escalations(hours_since_dispatch or None)
    return {"escalated_patients": [t.patient_id for t in escalated]}


async def post_chart_alert(patient_id: str, title: str, details: str) -> Dict[str, Any]:
    carestack = carestack_services()
    try:
        result = await carestack.write_medical_alert(
            patient_id,
            carestack.MedicalAlertCreate(title=title, details=details, alert_type="warning",
                                         category="pharmacology", source="MAO Assistant"),
        )
    except Exception as exc:
        return {"ok": False, "message": getattr(exc, "detail", str(exc))}
    # Self-contained, so the chat widget never has to guess which call it belongs to
    return {"ok": True, "alert_id": result["alert"]["alert_id"], "message": result["message"],
            "patient_id": patient_id, "title": title, "details": details}


# -- registry -------------------------------------------------------------------------

_PATIENT = {"type": "string", "description": "CareStack ID, MRN or alias, e.g. CS-9921, MRN-10001, pat-1"}
_CDT = {"type": "string", "description": "CDT dental procedure code, e.g. D7210 (surgical extraction), D7140, D1110"}


def _decl(name: str, description: str, properties: Dict[str, Any] = None, required: List[str] = None) -> Dict[str, Any]:
    decl: Dict[str, Any] = {"name": name, "description": description}
    if properties:
        decl["parameters"] = {"type": "object", "properties": properties, "required": required or list(properties)}
    return decl


TOOL_DECLARATIONS: List[Dict[str, Any]] = [
    _decl("list_patients", "List every patient in the CareStack practice with their planned procedures. Use to resolve a name to a patient_id."),
    _decl("get_patient_history", "Full patient history: demographics, medical conditions (ICD-10), medications (RxNorm), allergies, labs, dental treatment plan, documents, chart alerts and clearance requests.", {"patient_id": _PATIENT}),
    _decl("assess_clinical_risk", "The Risk check for a planned procedure: hazard level, contraindications, recommendations. Pass the procedure in the user's words (or a CDT code) and anything the user says they learned today as todays_notes. Changes nothing on the chart; it starts the patient's VISIT, which carries this context to the insurance step.", {"patient_id": _PATIENT, "procedure": {"type": "string", "description": "Procedure in the user's words, or a CDT code"},
           "todays_notes": {"type": "string", "description": "What the user learned from the patient today, verbatim"}}, required=["patient_id", "procedure"]),
    _decl("check_medical_coverage_pathway", "Read-only. When a patient's dental benefit cannot pay, checks whether the dental problem has a "
          "legitimate MEDICAL-insurance pathway, from the payer's published policy and the member's plan document. Returns an outcome "
          "(no_pathway / potential_pathway / needs_review / dental_active) with verbatim policy quotes. The only source you may use for "
          "insurance coverage statements.",
          {"patient_id": _PATIENT, "procedure": {"type": "string", "description": "Optional: omit it to use the procedure of the visit in progress"},
           "clinical_note": {"type": "string", "description": "Clinical findings the user stated: diagnosis, imaging, symptoms, cause (trauma, infection...)"},
           "diagnosis": {"type": "string"}}, required=["patient_id"]),
    _decl("get_agent_state", "Current state of the multi-agent workflow for a patient: clearance status, physician, restrictions, billing claim, agent log.", {"patient_id": _PATIENT}),
    _decl("consult_specialists", "Ask the parallel specialist panel (clinical-safety reviewer, treatment-planning reviewer, patient-communication drafter; each a different model/provider) for second opinions. They see the compact patient history but have no tools and take no actions. Returns their opinions for you to synthesize.", {"question": {"type": "string", "description": "The self-contained question or situation to review, including the procedure if relevant"}, "patient_id": _PATIENT}, required=["question"]),
    _decl("run_agent_workflow", "ACTION. Run the MAO agents (intake, risk, physician clearance) for a patient and procedure. May post a chart alert, dispatch a clearance request to the physician and upload a Letter of Medical Necessity.", {"patient_id": _PATIENT, "cdt_code": _CDT}),
    _decl("submit_physician_reply", "ACTION. File the physician's free-text reply to a pending clearance request; extracts restrictions and clears the appointment if approved.", {"patient_id": _PATIENT, "reply_text": {"type": "string", "description": "The physician's reply, verbatim"}}),
    _decl("check_clearance_escalations", "ACTION. Escalate clearance requests unanswered for more than 48 hours (patient nudge SMS + front-desk flag).", {"hours_since_dispatch": {"type": "number", "description": "Override elapsed hours for a demo; 0 uses real elapsed time"}}, required=[]),
    _decl("post_chart_alert", "ACTION. Post a medical alert to the patient's CareStack chart.", {"patient_id": _PATIENT, "title": {"type": "string"}, "details": {"type": "string"}}),
    *RECORD_TOOL_DECLARATIONS,
    *CHART_TOOL_DECLARATIONS,
    *VISIT_TOOL_DECLARATIONS,
]

TOOL_FUNCTIONS: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    f.__name__: f
    for f in (list_patients, get_patient_history, assess_clinical_risk, check_medical_coverage_pathway, get_agent_state, consult_specialists,
              run_agent_workflow, submit_physician_reply, check_clearance_escalations, post_chart_alert)
}
TOOL_FUNCTIONS.update(RECORD_TOOL_FUNCTIONS)
TOOL_FUNCTIONS.update(CHART_TOOL_FUNCTIONS)
TOOL_FUNCTIONS.update(VISIT_TOOL_FUNCTIONS)
assert set(TOOL_FUNCTIONS) == {d["name"] for d in TOOL_DECLARATIONS}


def _record_imported_this_turn() -> bool:
    return any(call["tool"] == "import_previous_record" for call in turn_recorder.get() or [])


def tool_succeeded(result: Dict[str, Any]) -> bool:
    return "error" not in result and result.get("ok", True) is not False


async def execute_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Runs a tool call from the model. Bad names/arguments come back as data so the model can recover."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        result: Dict[str, Any] = {"error": f"Unknown tool '{name}'"}
    elif name in ACTION_TOOLS - RECORD_ACTION_TOOLS and _record_imported_this_turn():
        # An imported record is untrusted text. Whatever it says, it cannot trigger another action in the same turn.
        result = {"error": f"{name} is blocked for the rest of this turn because a previous record was just imported. "
                           "Tell the user what you intended and ask them to confirm in their next message."}
    else:
        try:
            result = await func(**(args or {}))
        except TypeError as exc:
            result = {"error": f"Bad arguments for {name}: {exc}"}
        except Exception as exc:  # a tool failure should reach the model as an error, not crash the chat
            result = {"error": f"{name} failed: {exc}"}
    record_tool_call(name, args or {}, result)  # the orchestrator builds the chat widgets from these
    return result
