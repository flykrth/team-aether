"""
API routers for CareStack, FHIR, and CDS Hooks.
"""

from .carestack import router as carestack_router
from .fhir import router as fhir_router
from .cds_services import router as cds_router

__all__ = ["carestack_router", "fhir_router", "cds_router"]
