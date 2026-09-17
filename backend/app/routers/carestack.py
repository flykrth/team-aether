"""
CareStack PMS integration router mounted at /api/carestack.
Re-exports the full CareStack Web API V1 router and provides interoperability
bridges for CareStack Dental PMS, including three-key authentication (VendorKey, AccountKey, AccountId),
patient management, periodontal charting, and bi-directional EHR synchronization.
"""

from .carestack_mock import (
    router,
    MOCK_PATIENTS,
    MOCK_PROCEDURE_CODES,
    MOCK_APPOINTMENTS,
    SYNCED_CLINICAL_CACHE,
    PATIENT_MEDICAL_ALERTS,
    verify_carestack_credentials,
)

__all__ = [
    "router",
    "MOCK_PATIENTS",
    "MOCK_PROCEDURE_CODES",
    "MOCK_APPOINTMENTS",
    "SYNCED_CLINICAL_CACHE",
    "PATIENT_MEDICAL_ALERTS",
    "verify_carestack_credentials",
]
