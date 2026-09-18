"""
Assistant tools that EDIT an existing chart: patient details, the treatment plan, and any single
history item (change it or remove it). Together with record_tools (create / add / import) the agent can
change everything about a patient that the Manual mode screens can.

Same guarantees as the rest of the assistant: the model never supplies codes (an edited item is re-coded
by the lexicon), it must look up the item's id instead of guessing it, and removal needs the user's own
message to ask for it. These tools are NOT allowed in a turn that imported a previous record
(untrusted text must not be able to trigger an edit or a deletion).
"""

import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .. import patient_registry
from .context import turn_last_user_message

CHART_ACTION_TOOLS = {"update_patient_details", "update_history_item", "remove_history_item", "remove_patient"}

_REMOVAL_VERBS = r"\b(remove|delete|erase|drop|clear|take off|strike|discontinue[sd]?|stopped|no longer|not (?:on|taking)|wrong|mistake|incorrect)\b"
_EDITABLE_DETAILS = ("first_name", "last_name", "birth_date", "gender", "phone", "email", "next_appointment", "primary_dentist")


async def _refreshed(patient_id: str, change: str) -> Dict[str, Any]:
    from .tools import get_patient_history  # tools.py imports this module

    return {"ok": True, "change": change, **await get_patient_history(patient_id)}


def _fail(exc: Exception) -> Dict[str, Any]:
    return {"ok": False, "message": str(exc).strip("'\"")}


async def get_patient_chart(patient_id: str) -> Dict[str, Any]:
    try:
        chart = patient_registry.get_chart(patient_id)
    except KeyError as exc:
        return _fail(exc)
    chart["entries"] = [{k: e[k] for k in ("resource_id", "type", "text", "code", "onset", "value", "unit", "unconfirmed")} for e in chart["entries"]]
    return {"ok": True, **chart}


async def update_patient_details(
    patient_id: str,
    first_name: Optional[str] = None, last_name: Optional[str] = None, birth_date: Optional[str] = None,
    gender: Optional[str] = None, phone: Optional[str] = None, email: Optional[str] = None,
    next_appointment: Optional[str] = None, primary_dentist: Optional[str] = None,
    planned_procedures: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    supplied = dict(first_name=first_name, last_name=last_name, birth_date=birth_date, gender=gender, phone=phone, email=email,
                    next_appointment=next_appointment, primary_dentist=primary_dentist, planned_procedures=planned_procedures)
    changes = {k: v for k, v in supplied.items() if v is not None}
    try:
        patient_registry.update_patient(patient_id, changes)
    except (KeyError, ValueError) as exc:
        return _fail(exc)
    return await _refreshed(patient_id, "Updated " + ", ".join(k.replace("_", " ") for k in changes))


async def update_history_item(
    patient_id: str, resource_id: str, text: Optional[str] = None, onset: Optional[str] = None,
    value: Optional[Any] = None, unit: Optional[str] = None,
) -> Dict[str, Any]:
    changes = {k: v for k, v in dict(text=text, onset=onset, value=value, unit=unit).items() if v is not None}
    if not changes:
        return {"ok": False, "message": "Nothing to change: pass text, onset, value or unit."}
    try:
        updated = patient_registry.update_history_entry(patient_id, resource_id, changes)
    except (KeyError, ValueError) as exc:
        return _fail(exc)
    coded = f" (coded {updated['code']})" if updated.get("code") else " (no code in the lexicon; stored as text)"
    return await _refreshed(patient_id, f"Changed history item to '{updated['text']}'{coded}")


async def remove_history_item(patient_id: str, resource_id: str) -> Dict[str, Any]:
    if not re.search(_REMOVAL_VERBS, (turn_last_user_message.get() or "").lower()):
        return {"ok": False, "message": "The user's message does not ask to remove anything. Tell them which item you would "
                                        "remove and ask them to confirm; remove it only after they say so."}
    try:
        chart = patient_registry.get_chart(patient_id)
        item = next((e for e in chart["entries"] if e["resource_id"] == resource_id), None)
        patient_registry.delete_history_entry(patient_id, resource_id)
    except KeyError as exc:
        return _fail(exc)
    return await _refreshed(patient_id, f"Removed '{item['text'] if item else resource_id}' from the chart")


async def remove_patient(patient_id: str) -> Dict[str, Any]:
    """Whole-chart deletion: the user's own message must ask for it AND name the patient (ID, MRN or name)."""
    said = (turn_last_user_message.get() or "").lower()
    try:
        chart = patient_registry.get_chart(patient_id)
    except KeyError as exc:
        return _fail(exc)
    labels = [chart["patient_id"], chart["mrn"], chart["name"], *chart["name"].split()]
    asked = re.search(r"\b(remove|delete|erase)\b", said)
    named = any(label and len(label) > 2 and label.lower() in said for label in labels)
    if not (asked and named):
        return {"ok": False, "message": f"Removing a patient deletes the whole chart. The user's message must ask to remove/delete "
                                        f"and name the patient. Ask them to confirm: 'Remove {chart['name']} ({chart['patient_id']})?'"}
    try:
        result = patient_registry.delete_patient(patient_id)
    except KeyError as exc:
        return _fail(exc)
    return {"ok": True, "change": f"Removed {result['name']} ({result['deleted']}) and the whole chart", **result}


_PATIENT = {"type": "string", "description": "CareStack ID, MRN or alias, e.g. CS-9921"}
_ITEM = {"type": "string", "description": "resource_id of the history item, exactly as returned by get_patient_chart. Never guess it."}

CHART_TOOL_DECLARATIONS: List[Dict[str, Any]] = [
    {
        "name": "get_patient_chart",
        "description": ("The editable chart: personal details, planned procedures, documents and EVERY history item with its "
                        "resource_id. Call this before update_history_item or remove_history_item to find the item's id."),
        "parameters": {"type": "object", "properties": {"patient_id": _PATIENT}, "required": ["patient_id"]},
    },
    {
        "name": "update_patient_details",
        "description": ("ACTION. Change a patient's personal details (name, date of birth YYYY-MM-DD, gender, phone, email, next "
                        "appointment, dentist) and/or replace the planned procedures list (CDT codes). Pass only the fields the "
                        "user asked to change. Say back exactly what changed."),
        "parameters": {"type": "object", "properties": {
            "patient_id": _PATIENT,
            **{name: {"type": "string"} for name in _EDITABLE_DETAILS},
            "planned_procedures": {"type": "array", "description": "The FULL new list; it replaces the current plan",
                                   "items": {"type": "object", "properties": {"code": {"type": "string", "description": "CDT code, e.g. D7210"},
                                             "description": {"type": "string"}, "tooth_number": {"type": "string"}}, "required": ["code"]}},
        }, "required": ["patient_id"]},
    },
    {
        "name": "update_history_item",
        "description": ("ACTION. Correct one existing condition, medication, allergy or lab on the chart: its wording, date "
                        "(YYYY-MM-DD, only if the user stated it), value or unit. The server re-codes the new text; never pass a code."),
        "parameters": {"type": "object", "properties": {
            "patient_id": _PATIENT, "resource_id": _ITEM,
            "text": {"type": "string", "description": "New wording in the user's own words, e.g. 'apixaban 5 mg'"},
            "onset": {"type": "string"}, "value": {"type": "number"}, "unit": {"type": "string"},
        }, "required": ["patient_id", "resource_id"]},
    },
    {
        "name": "remove_history_item",
        "description": ("ACTION, destructive. Remove one history item from the chart. Only when the user asks to remove/delete it "
                        "or says the patient stopped it; the server refuses otherwise. Name the item you removed."),
        "parameters": {"type": "object", "properties": {"patient_id": _PATIENT, "resource_id": _ITEM}, "required": ["patient_id", "resource_id"]},
    },
]

CHART_TOOL_DECLARATIONS.append({
    "name": "remove_patient",
    "description": ("ACTION, destructive and permanent. Remove a patient and their entire chart from the practice. Only when the "
                    "user explicitly asks to remove/delete that patient by name or ID; the server refuses otherwise. If there is "
                    "any doubt which patient is meant, ask first."),
    "parameters": {"type": "object", "properties": {"patient_id": _PATIENT}, "required": ["patient_id"]},
})

CHART_TOOL_FUNCTIONS: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
    f.__name__: f for f in (get_patient_chart, update_patient_details, update_history_item, remove_history_item, remove_patient)
}
assert set(CHART_TOOL_FUNCTIONS) == {d["name"] for d in CHART_TOOL_DECLARATIONS}
