"""
API routers for CareStack PMS, HL7 FHIR R4 EHR, and CDS Hooks.
"""

from .carestack_mock import router as carestack_mock_router
from .fhir import router as fhir_router
from .cds_services import router as cds_router
from .billing import router as billing_router
from .clearance import router as clearance_router
from .agents import router as agents_router
from .assistant import router as assistant_router
from .risk import router as risk_router
from .records import router as records_router
from .carestack import router as carestack_legacy_router

# Active routers for MDIN
carestack_router = carestack_mock_router
fhir_ehr_router = fhir_router
fhir_ehr_mock_router = fhir_router
fhir_legacy_router = fhir_router

__all__ = [
    "carestack_router",
    "fhir_router",
    "cds_router",
    "billing_router",
    "clearance_router",
    "agents_router",
    "assistant_router",
    "risk_router",
    "records_router",
    "carestack_mock_router",
    "fhir_ehr_router",
    "fhir_ehr_mock_router",
    "carestack_legacy_router",
    "fhir_legacy_router",
]
