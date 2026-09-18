"""
Assistant tools for the visit workflow, so the whole path can be driven from the chat:
patient -> history -> risk check -> procedure done -> insurance (dental first, then a medical pathway).

The risk check and the coverage check live in tools.py; they record themselves on the visit. These tools read
the visit, move it along, and handle the patient's insurance details.
"""

import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .. import visits
from ..coverage import packet, plans
from .context import turn_attachments, turn_last_user_message

VISIT_ACTION_TOOLS = {"mark_procedure_done", "set_patient_insurance", "attach_plan_document", "create_coverage_document", "close_visit"}


def _fail(exc: Exception) -> Dict[str, Any]:
    return {"ok": False, "message": str(exc).strip("'\"")}


def _status(patient_id: str, change: str = "") -> Dict[str, Any]:
    visit = visits.current(patient_id)
    insurance = plans.get_insurance(patient_id)
    return {
        "ok": True, "change": change, "patient_id": insurance["patient_id"], "next_step": visits.next_step(patient_id),
        "visit": None if visit is None else {
            "visit_id": visit["visit_id"], "stage": visit["stage"], "procedure": visit["procedure"],
            "todays_notes": visit["todays_notes"], "risk": visit["risk"] and {k: visit["risk"][k] for k in ("hazard_level", "physician_clearance_required")},
            "insurance": visit["insurance"] and {k: visit["insurance"][k] for k in ("outcome", "headline", "reason")},
            "documents": visit["documents"],
        },
        "insurance": {"dental_status": insurance["dental"]["status"], "medical_insurer": insurance["medical"]["insurer"] or None,
                      "plan_type": insurance["medical"]["plan_type"] or None, "plan_document": (insurance["plan_document"] or {}).get("title")},
    }


async def get_visit(patient_id: str) -> Dict[str, Any]:
    try:
        return _status(patient_id)
    except KeyError as exc:
        return _fail(exc)


async def mark_procedure_done(patient_id: str, outcome_note: str = "") -> Dict[str, Any]:
    try:
        visits.mark_procedure_done(patient_id, outcome_note)
        return _status(patient_id, "Procedure marked as done")
    except (KeyError, ValueError) as exc:
        return _fail(exc)


async def set_patient_insurance(patient_id: str, dental_status: Optional[str] = None, dental_carrier: Optional[str] = None,
                                medical_insurer: Optional[str] = None, plan_type: Optional[str] = None,
                                plan_name: Optional[str] = None, member_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        current = plans.get_insurance(patient_id)
        dental = None
        if dental_status or dental_carrier:
            dental = {**current["dental"], **({"status": dental_status} if dental_status else {}), **({"carrier": dental_carrier} if dental_carrier else {})}
        medical = None
        if any((medical_insurer, plan_type, plan_name, member_id)):
            known = {i.lower(): i for i in plans.insurers("US")}
            insurer = known.get((medical_insurer or "").strip().lower(), medical_insurer) if medical_insurer else current["medical"]["insurer"]
            medical = {**current["medical"], "insurer": insurer or "", **({"plan_type": plan_type} if plan_type else {}),
                       **({"plan_name": plan_name} if plan_name else {}), **({"member_id": member_id} if member_id else {})}
        plans.set_insurance(patient_id, dental, medical)
        status = _status(patient_id, "Insurance details saved")
        status["insurers_in_policy_library"] = plans.insurers("US")
        return status
    except (KeyError, ValueError) as exc:
        return _fail(exc)


async def attach_plan_document(patient_id: str, attachment: Optional[str] = None) -> Dict[str, Any]:
    """Files an attached PDF/text as the member's plan document. Same consent rule as charting an attachment."""
    said = (turn_last_user_message.get() or "").lower()
    if not re.search(r"\b(plan|policy|sbc|certificate|coverage|benefit|insurance)\b", said) or not re.search(r"\b(add|attach|upload|use|save|file|store|set|here is|this is)\b", said):
        return {"ok": False, "message": "The user has not asked to use an attachment as a plan document. Ask them first."}
    attached = turn_attachments.get() or []
    wanted = (attachment or "").strip().lower()
    match = next((a for a in attached if a["filename"].lower() == wanted), attached[0] if len(attached) == 1 else None)
    if match is None:
        return {"ok": False, "message": "No such attached document. Available: " + (", ".join(a["filename"] for a in attached) or "none") + "."}
    try:
        plans.set_plan_document(patient_id, match["filename"], match["text"], "chat attachment")
        return _status(patient_id, f"Plan document '{match['filename']}' saved for this patient")
    except (KeyError, ValueError) as exc:
        return _fail(exc)


async def create_coverage_document(patient_id: str, reviewed_by: str = "") -> Dict[str, Any]:
    try:
        chart_id = plans._resolve(patient_id)
        visit = visits.current(chart_id)
        outcome = ((visit or {}).get("insurance") or {}).get("outcome")
        if outcome == "needs_review":
            return {"ok": False, "message": "No document can be created: the insurance check came back 'Needs human review', which is NOT a confirmed "
                                            "pathway. Tell the user that plainly, say what the chart still needs to answer, and do not retry."}
        if outcome == "dental_active":
            return {"ok": False, "message": "No document is needed: the dental benefit is active, so this is billed to the dental plan as usual."}
        document = packet.build(chart_id, reviewed_by)
        visits.add_document(chart_id, document)
        return {"ok": True, "document_id": document["document_id"], "document_type": document["document_type"], "title": document["title"],
                "preview": document["content_markdown"][:1200], "next_step": visits.next_step(chart_id)}
    except (KeyError, ValueError) as exc:
        return _fail(exc)


async def close_visit(patient_id: str) -> Dict[str, Any]:
    try:
        visits.close(patient_id)
        return _status(patient_id, "Visit closed")
    except (KeyError, ValueError) as exc:
        return _fail(exc)


_PATIENT = {"type": "string", "description": "CareStack ID, MRN or alias, e.g. CS-9921"}

VISIT_TOOL_DECLARATIONS: List[Dict[str, Any]] = [
    {"name": "get_visit", "description": ("Where this patient's visit stands and what comes next: procedure, risk result, whether the procedure is "
                                          "done, insurance details and the insurance outcome. Call it when unsure what the next step is."),
     "parameters": {"type": "object", "properties": {"patient_id": _PATIENT}, "required": ["patient_id"]}},
    {"name": "mark_procedure_done", "description": "ACTION. Record that the planned procedure was carried out. Only when the user says so. The next step is insurance.",
     "parameters": {"type": "object", "properties": {"patient_id": _PATIENT, "outcome_note": {"type": "string", "description": "What the user said about how it went, if anything"}}, "required": ["patient_id"]}},
    {"name": "set_patient_insurance", "description": ("ACTION. Save what the user tells you about the patient's insurance. dental_status is one of active, expired, "
                                                      "exhausted (annual maximum used up), denied, none. Pass only what the user stated; never guess an insurer or plan type."),
     "parameters": {"type": "object", "properties": {
         "patient_id": _PATIENT, "dental_status": {"type": "string", "enum": ["active", "expired", "exhausted", "denied", "none"]},
         "dental_carrier": {"type": "string"}, "medical_insurer": {"type": "string", "description": "e.g. Aetna, Cigna, UnitedHealthcare"},
         "plan_type": {"type": "string", "enum": ["HMO", "PPO", "POS", "EPO", "Traditional"]}, "plan_name": {"type": "string"}, "member_id": {"type": "string"}},
         "required": ["patient_id"]}},
    {"name": "attach_plan_document", "description": ("ACTION. Save an ATTACHED file as the member's medical plan document (SBC / Certificate of Coverage), so the coverage "
                                                     "check can read the plan's own exclusions. Only when the user asks for that."),
     "parameters": {"type": "object", "properties": {"patient_id": _PATIENT, "attachment": {"type": "string", "description": "Filename of the attachment"}}, "required": ["patient_id"]}},
    {"name": "create_coverage_document", "description": ("ACTION. After check_medical_coverage_pathway: files the pre-treatment estimate request (potential pathway; needs "
                                                         "reviewed_by, the name of the person approving it, which you must ask for) or the patient explanation (no pathway)."),
     "parameters": {"type": "object", "properties": {"patient_id": _PATIENT, "reviewed_by": {"type": "string"}}, "required": ["patient_id"]}},
    {"name": "close_visit", "description": "ACTION. Close the visit once insurance is settled. Only when the user asks.",
     "parameters": {"type": "object", "properties": {"patient_id": _PATIENT}, "required": ["patient_id"]}},
]

VISIT_TOOL_FUNCTIONS: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    f.__name__: f for f in (get_visit, mark_procedure_done, set_patient_insurance, attach_plan_document, create_coverage_document, close_visit)
}
assert set(VISIT_TOOL_FUNCTIONS) == {d["name"] for d in VISIT_TOOL_DECLARATIONS}
