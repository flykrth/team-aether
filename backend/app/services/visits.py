"""
The visit: one patient, one planned procedure, carried from the risk check to the insurance question.

  planned -> risk_checked -> procedure_done -> insurance_checked -> closed

It exists so nobody types anything twice. What the dentist said at the risk check (the procedure, today's
notes, what the rules found) is the context the insurance step starts from. It is a record of what was
entered and what the checks returned; it decides nothing itself.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import patient_registry

STAGES = ("planned", "risk_checked", "procedure_done", "insurance_checked", "closed")
_visits: Dict[str, List[Dict[str, Any]]] = {}   # CareStack id -> visits, newest last
_loaded_from: Optional[str] = ""


def _path() -> Optional[str]:
    registry = patient_registry._registry_path()  # same rule as the registry: under pytest nothing touches disk unless a test opts in
    return f"{registry}.visits.json" if registry else None


def _ensure_loaded() -> None:
    global _visits, _loaded_from
    path = _path()
    if _loaded_from == path:
        return
    _visits, _loaded_from = {}, path
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                _visits = {k: v for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError):
            _visits = {}


def _save() -> None:
    path = _path()
    if not path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_visits, f, indent=1)
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve(patient_id: str) -> str:
    return patient_registry.get_chart(patient_id)["patient_id"]  # KeyError for an unknown patient


def current(patient_id: str) -> Optional[Dict[str, Any]]:
    """The visit in progress, if any."""
    _ensure_loaded()
    open_visits = [v for v in _visits.get(_resolve(patient_id), []) if v["stage"] != "closed"]
    return open_visits[-1] if open_visits else None


def history(patient_id: str) -> List[Dict[str, Any]]:
    _ensure_loaded()
    return list(reversed(_visits.get(_resolve(patient_id), [])))


def _open(patient_id: str, procedure: Dict[str, Any]) -> Dict[str, Any]:
    """The visit in progress for this procedure, or a new one. A different procedure is a different visit."""
    cs_id = _resolve(patient_id)
    visit = current(cs_id)
    if visit and visit["procedure"].get("cdt_code") != procedure.get("cdt_code"):
        visit["stage"], visit["closed_at"], visit["closed_reason"] = "closed", _now(), "A different procedure was started."
        visit = None
    if visit is None:
        visit = {"visit_id": f"V-{uuid.uuid4().hex[:8].upper()}", "patient_id": cs_id, "stage": "planned", "started_at": _now(),
                 "procedure": procedure, "todays_notes": "", "risk": None, "clinical": {}, "insurance": None, "documents": []}
        _visits.setdefault(cs_id, []).append(visit)
    return visit


def record_risk_check(patient_id: str, result: Dict[str, Any], todays_notes: str) -> Dict[str, Any]:
    """Keeps what the risk check was told and what it found, as context for the rest of the visit."""
    _ensure_loaded()
    visit = _open(patient_id, result["procedure"])
    visit["procedure"] = result["procedure"]
    visit["todays_notes"] = (todays_notes or "").strip()
    visit["risk"] = {
        "checked_at": _now(), "hazard_level": result["hazard_level"],
        "physician_clearance_required": result["physician_clearance_required"],
        "findings": [{"rule_id": f["rule_id"], "hazard_level": f["hazard_level"], "contraindication": f["contraindication"],
                      "recommendations": f["recommendations"]} for f in result.get("findings", [])],
        "reported_today": [c.get("display") for c in result.get("reported_today", [])],
    }
    if STAGES.index(visit["stage"]) < STAGES.index("risk_checked"):
        visit["stage"] = "risk_checked"
    _save()
    return visit


def mark_procedure_done(patient_id: str, outcome_note: str = "") -> Dict[str, Any]:
    _ensure_loaded()
    visit = current(patient_id)
    if visit is None:
        raise ValueError("There is no visit in progress for this patient. Run a risk check for the planned procedure first.")
    if visit["risk"] is None:
        raise ValueError("The risk check has not been run for this visit yet.")
    visit["procedure_done_at"] = _now()
    visit["outcome_note"] = (outcome_note or "").strip()[:1000]
    if STAGES.index(visit["stage"]) < STAGES.index("procedure_done"):
        visit["stage"] = "procedure_done"
    _save()
    return visit


def save_clinical_details(patient_id: str, details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Diagnosis, imaging, clinical note and indication flags entered for the insurance step."""
    _ensure_loaded()
    visit = current(patient_id)
    if visit is None:
        return None
    for key in ("diagnosis", "diagnosis_codes", "imaging", "clinical_note", "flags"):
        if details.get(key) not in (None, "", {}, []):
            visit["clinical"][key] = details[key]
    _save()
    return visit


def record_insurance_check(patient_id: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    _ensure_loaded()
    visit = current(patient_id)
    if visit is None:
        return None
    determination = result["determination"]
    visit["insurance"] = {
        "checked_at": _now(), "outcome": determination["outcome"], "headline": determination["headline"], "reason": determination["reason"],
        "dental_status": result["insurance"]["dental"]["status"], "medical_insurer": result["insurance"]["medical"]["insurer"],
        "plan_verified": determination.get("plan_verified"),
        "quotes": [{"kind": c["kind"], "quote": c["quote"][:300], "source": c["source"]["title"], "url": c["source"]["url"]}
                   for c in result.get("criteria", [])[:6]],
    }
    if STAGES.index(visit["stage"]) < STAGES.index("insurance_checked") and determination["outcome"] != "needs_review":
        visit["stage"] = "insurance_checked"
    _save()
    return visit


def add_document(patient_id: str, document: Dict[str, Any]) -> None:
    _ensure_loaded()
    visit = current(patient_id)
    if visit is not None:
        visit["documents"].append({k: document.get(k) for k in ("document_id", "document_type", "title")})
        _save()


def close(patient_id: str) -> Dict[str, Any]:
    _ensure_loaded()
    visit = current(patient_id)
    if visit is None:
        raise ValueError("There is no visit in progress for this patient.")
    visit["stage"], visit["closed_at"] = "closed", _now()
    _save()
    return visit


def forget(cs_id: str) -> None:
    _ensure_loaded()
    if _visits.pop(cs_id, None) is not None:
        _save()


def insurance_context(patient_id: str) -> Dict[str, Any]:
    """What the insurance step should start from: the visit's procedure and everything clinical said so far."""
    visit = current(patient_id)
    if visit is None:
        return {}
    clinical = visit.get("clinical") or {}
    notes = [n for n in (clinical.get("clinical_note"), visit.get("todays_notes"), visit.get("outcome_note")) if n]
    return {
        "procedure": visit["procedure"].get("input") or visit["procedure"].get("label") or "",
        "clinical_note": "\n".join(dict.fromkeys(notes)),
        "diagnosis": clinical.get("diagnosis", ""), "diagnosis_codes": clinical.get("diagnosis_codes", ""),
        "imaging": clinical.get("imaging", ""), "flags": clinical.get("flags", {}),
    }


def next_step(patient_id: str) -> Dict[str, str]:
    """One sentence on where this patient's visit stands and what comes next. Used by the UI and the chat."""
    visit = current(patient_id)
    if visit is None:
        return {"stage": "none", "next": "Run a risk check for the planned procedure."}
    label = visit["procedure"].get("label", "the procedure")
    stage = visit["stage"]
    if stage == "planned":
        text = f"Run the risk check for {label}."
    elif stage == "risk_checked":
        text = ("Physician clearance is required before this procedure. " if visit["risk"]["physician_clearance_required"] else "") \
               + f"When {label} has been carried out, mark the procedure as done."
    elif stage == "procedure_done":
        text = "Check insurance: is the dental benefit active? If not, check for a medical pathway."
    else:
        text = f"{visit['insurance']['headline']}. Create the document if needed, then close the visit."
    return {"stage": stage, "next": text}
