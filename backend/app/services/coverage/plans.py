"""
The patient's side of the question: dental benefit status, medical plan, and the plan document.

Dental status is a staff-entered select (active / expired / exhausted / denied / none); there is no
eligibility lookup. The medical plan document (Summary of Benefits and Coverage, Certificate of
Coverage) is uploaded, read by the same ingestion as any other PDF, and kept on this machine only.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .. import patient_registry
from . import policy_store, retrieval

DENTAL_STATUSES = ("active", "expired", "exhausted", "denied", "none", "unknown")


def _plan_dir() -> str:
    path = os.path.join(policy_store.cache_dir(), "member_plans")
    os.makedirs(path, exist_ok=True)
    return path


def _resolve(patient_id: str) -> str:
    return patient_registry.get_chart(patient_id)["patient_id"]  # raises KeyError for an unknown patient


def _path(cs_id: str) -> str:
    return os.path.join(_plan_dir(), re.sub(r"[^A-Za-z0-9._-]", "_", cs_id) + ".json")


def _load(cs_id: str) -> Dict[str, Any]:
    try:
        with open(_path(cs_id), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(cs_id: str, record: Dict[str, Any]) -> None:
    with open(_path(cs_id), "w", encoding="utf-8") as f:
        json.dump(record, f)


def forget(cs_id: str) -> None:
    """Removes the stored insurance profile and plan document of a deleted patient."""
    try:
        os.remove(_path(cs_id))
    except OSError:
        pass


def insurers(region: str = "US") -> List[str]:
    seen: List[str] = []
    for source in policy_store.load_registry()["sources"]:
        if source["region"] == region and source["insurer"] not in seen:
            seen.append(source["insurer"])
    return seen


def get_insurance(patient_id: str) -> Dict[str, Any]:
    cs_id = _resolve(patient_id)
    record = _load(cs_id)
    document = record.get("plan_document")
    return {
        "patient_id": cs_id,
        "dental": record.get("dental") or {"status": "unknown", "carrier": "", "note": ""},
        "medical": record.get("medical") or {"insurer": "", "plan_name": "", "plan_type": "", "member_id": ""},
        "plan_document": {k: document[k] for k in ("title", "uploaded_at", "chars", "method")} if document else None,
    }


def set_insurance(patient_id: str, dental: Optional[Dict[str, Any]] = None, medical: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cs_id = _resolve(patient_id)
    record = _load(cs_id)
    if dental is not None:
        status = str(dental.get("status") or "unknown").lower()
        if status not in DENTAL_STATUSES:
            raise ValueError(f"dental status must be one of {', '.join(DENTAL_STATUSES)}")
        record["dental"] = {"status": status, "carrier": str(dental.get("carrier") or "")[:120], "note": str(dental.get("note") or "")[:300]}
    if medical is not None:
        record["medical"] = {k: str(medical.get(k) or "")[:120] for k in ("insurer", "plan_name", "plan_type", "member_id")}
    _save(cs_id, record)
    return get_insurance(cs_id)


def set_plan_document(patient_id: str, title: str, text: str, method: str = "") -> Dict[str, Any]:
    cs_id = _resolve(patient_id)
    if len((text or "").strip()) < 200:
        raise ValueError("That document has too little text to be a plan document.")
    record = _load(cs_id)
    source = {"id": f"plan:{cs_id}", "insurer": "Member plan document", "region": "US"}
    record["plan_document"] = {
        "title": (title or "Plan document")[:200], "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "chars": len(text), "method": method, "chunks": policy_store.chunk_document(source, text),
    }
    _save(cs_id, record)
    return get_insurance(cs_id)


def remove_plan_document(patient_id: str) -> Dict[str, Any]:
    cs_id = _resolve(patient_id)
    record = _load(cs_id)
    record.pop("plan_document", None)
    _save(cs_id, record)
    return get_insurance(cs_id)


def plan_passages(patient_id: str, query: str, codes: List[str], k: int = 6) -> List[Dict[str, Any]]:
    """Passages of the member's own plan that speak to this case. Lexical + code match; the plan never leaves the machine."""
    document = _load(_resolve(patient_id)).get("plan_document")
    if not document:
        return []
    chunks = [{**c, "title": document["title"], "url": "", "review": None, "fetched_at": document["uploaded_at"]}
              for c in document["chunks"]]
    # Exclusions and oral-surgery wording are what decide a plan-level question, so they are always searched for
    ids = retrieval._bm25(f"{query} dental oral surgery exclusion not covered accidental injury prior authorization precertification", chunks, k)
    wanted = {c.upper() for c in codes}
    coded = [c["id"] for c in chunks if wanted & {x for group in c["codes"].values() for x in group}]
    by_id = {c["id"]: c for c in chunks}
    return [by_id[i] for i in dict.fromkeys(coded + ids)][:k]
