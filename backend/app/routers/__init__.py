"""
API routers for CareStack PMS, HL7 FHIR R4 EHR, and CDS Hooks.
"""

from .carestack_mock import router as carestack_mock_router
from .fhir_ehr_mock import router as fhir_ehr_router
from .cds_services import router as cds_router
from .billing import router as billing_router
from .carestack import router as carestack_legacy_router
from .fhir import router as fhir_legacy_router

# Default active routers for MDIN
carestack_router = carestack_mock_router
fhir_router = fhir_ehr_router

__all__ = [
    "carestack_router",
    "fhir_router",
    "cds_router",
    "billing_router",
    "carestack_mock_router",
    "fhir_ehr_mock_router",
    "carestack_legacy_router",
    "fhir_legacy_router",
]
