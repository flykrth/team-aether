"""
HL7 FHIR R4 Router Adapter.
Backward-compatibility adapter re-exporting production FHIR endpoints from backend.app.routers.fhir
and backend.app.services.fhir_client.
Mock data structures have been deprecated and replaced by live HL7 Public Test Server integration.
"""

from .fhir import (
    router,
    TranslateRequest,
    EvaluateRisksRequest,
    get_capability_statement,
    search_patients,
    get_patient_by_id,
    get_patient_everything,
    list_conditions,
    list_medication_requests,
    list_allergies,
    list_observations,
    translate_concept,
    evaluate_patient_risks,
)
from ..services.fhir_client import (
    fhir_client,
    normalize_ref_id,
    resolve_patient_aliases,
    calculate_similarity,
)

# Reference cache alias for backward compatibility with existing tests
FHIR_STORE = fhir_client._local_cache
_normalize_ref_id = normalize_ref_id
_resolve_patient_aliases = resolve_patient_aliases
_calculate_similarity = calculate_similarity

__all__ = [
    "router",
    "FHIR_STORE",
    "_normalize_ref_id",
    "_resolve_patient_aliases",
    "_calculate_similarity",
    "TranslateRequest",
    "EvaluateRisksRequest",
    "get_capability_statement",
    "search_patients",
    "get_patient_by_id",
    "get_patient_everything",
    "list_conditions",
    "list_medication_requests",
    "list_allergies",
    "list_observations",
    "translate_concept",
    "evaluate_patient_risks",
]
