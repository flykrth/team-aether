"""
Shared helpers for the MAO agents (Step 15).
"""

from typing import Any, Dict, List, Optional

ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10-cm"
RXNORM_SYSTEM = "http://www.nlm.nih.gov/research/umls/rxnorm"
SNOMED_SYSTEM = "http://snomed.info/sct"

SURGICAL_EXTRACTION_CODES = {"D7210", "D7220", "D7230", "D7240", "D7241", "D7250"}


def is_invasive(cdt_code: str) -> bool:
    """Oral surgery (D7xxx), periodontal surgery (D42xx) and implant placement (D60xx)."""
    code = (cdt_code or "").upper()
    return code.startswith("D7") or code.startswith("D42") or code.startswith("D60")


def primary_cdt(state: Dict[str, Any], default: str = "") -> str:
    """The procedure driving clinical/financial reasoning: first invasive code, else first code."""
    cdt_codes = (state.get("appointment") or {}).get("cdt_codes") or []
    return next((c for c in cdt_codes if is_invasive(c)), cdt_codes[0] if cdt_codes else default)


def carestack_services():
    """
    Lazy accessor for the CareStack simulator module. clearance_engine, crosswalk_engine and the
    routers package import each other, and the cycle only resolves when the routers package is
    loaded first (as it is under the FastAPI app), so agents never import them at module load.
    """
    from ... import routers  # noqa: F401
    from ...routers import carestack_mock

    return carestack_mock


def clearance_service():
    carestack_services()
    from ..clearance_engine import medical_clearance_service

    return medical_clearance_service


def concept_codes(state: Dict[str, Any], system: Optional[str] = None) -> List[str]:
    concepts = (state.get("medical_records") or {}).get("normalized_concepts") or []
    return [c["code"] for c in concepts if c.get("code") and (system is None or c.get("system") == system)]


def find_concepts(state: Dict[str, Any], *, codes: tuple = (), keywords: tuple = ()) -> List[Dict[str, Any]]:
    """Concepts matching any of the given codes, or whose display contains any keyword."""
    matches = []
    for concept in (state.get("medical_records") or {}).get("normalized_concepts") or []:
        display = (concept.get("display") or "").lower()
        if concept.get("code") in codes or any(k in display for k in keywords):
            matches.append(concept)
    return matches
