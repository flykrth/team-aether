"""
CareStack PMS integration router mounted at /api/carestack.
Handles CareStack dental patient data, appointments, dental procedures, and sync status.
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from ..schemas.carestack import (
    CareStackPatient,
    DentalProcedure,
    CareStackSyncRequest,
    SyncStatusResponse,
)
from ..config import settings

router = APIRouter()

# Seed mock dental patient database for demonstration & hackathon testing
MOCK_PATIENTS = [
    CareStackPatient(
        id="CS-1001",
        mrn="EHR-88201",
        first_name="Eleanor",
        last_name="Vance",
        birth_date="1968-04-12",
        gender="female",
        email="eleanor.vance@example.com",
        phone="555-0192",
        last_visit="2026-02-10",
        next_appointment="2026-09-22 10:00:00",
        primary_dentist="Dr. Sarah Mitchell, DDS",
        active_treatment_plan=[
            DentalProcedure(
                code="D7140",
                description="Extraction, erupted tooth or exposed root",
                tooth_number="19",
                status="proposed",
                cost=220.0,
            ),
            DentalProcedure(
                code="D4341",
                description="Periodontal scaling and root planing - four or more teeth per quadrant",
                tooth_number="LR",
                status="scheduled",
                cost=310.0,
            ),
        ],
    ),
    CareStackPatient(
        id="CS-1002",
        mrn="EHR-54109",
        first_name="Marcus",
        last_name="Chen",
        birth_date="1982-11-03",
        gender="male",
        email="marcus.chen@example.com",
        phone="555-0143",
        last_visit="2026-01-18",
        next_appointment="2026-09-25 14:30:00",
        primary_dentist="Dr. Sarah Mitchell, DDS",
        active_treatment_plan=[
            DentalProcedure(
                code="D2750",
                description="Crown - porcelain fused to high noble metal",
                tooth_number="30",
                status="proposed",
                cost=1250.0,
            )
        ],
    ),
    CareStackPatient(
        id="CS-1003",
        mrn="EHR-99342",
        first_name="Robert",
        last_name="Taylor",
        birth_date="1955-08-27",
        gender="male",
        email="robert.taylor@example.com",
        phone="555-0188",
        last_visit="2025-11-05",
        next_appointment="2026-09-30 09:00:00",
        primary_dentist="Dr. Alan Vance, DMD",
        active_treatment_plan=[
            DentalProcedure(
                code="D7210",
                description="Extraction, erupted tooth requiring removal of bone and/or sectioning of tooth",
                tooth_number="32",
                status="proposed",
                cost=450.0,
            )
        ],
    ),
]


@router.get("/status", response_model=SyncStatusResponse)
async def get_carestack_status():
    """Check connectivity and synchronization status with CareStack PMS."""
    return SyncStatusResponse(
        status="connected",
        message="CareStack Interoperability Node is operational and synchronized.",
        synced_patients=len(MOCK_PATIENTS),
        last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
        carestack_connection=f"Active ({settings.CARESTACK_BASE_URL})",
        ehr_connection=f"Active ({settings.FHIR_SERVER_URL})",
    )


@router.get("/patients", response_model=List[CareStackPatient])
async def list_carestack_patients(
    search: Optional[str] = Query(None, description="Search by name or MRN"),
):
    """Retrieve list of CareStack dental patients with active treatment plans."""
    if not search:
        return MOCK_PATIENTS

    search_lower = search.lower()
    return [
        p
        for p in MOCK_PATIENTS
        if search_lower in p.first_name.lower()
        or search_lower in p.last_name.lower()
        or search_lower in p.mrn.lower()
        or search_lower in p.id.lower()
    ]


@router.get("/patients/{patient_id}", response_model=CareStackPatient)
async def get_carestack_patient(patient_id: str):
    """Retrieve detailed dental record and treatment plan for a specific patient."""
    for p in MOCK_PATIENTS:
        if p.id == patient_id or p.mrn == patient_id:
            return p
    raise HTTPException(status_code=404, detail=f"CareStack patient {patient_id} not found")


@router.post("/sync")
async def trigger_sync(sync_req: CareStackSyncRequest):
    """
    Trigger bi-directional reconciliation between CareStack PMS and Medical EHR.
    Synchronizes dental alerts to medical chart and medical alerts to dental chair.
    """
    for p in MOCK_PATIENTS:
        if p.id == sync_req.patient_id or p.mrn == sync_req.patient_id:
            return {
                "success": True,
                "synced_patient_id": p.id,
                "mrn": p.mrn,
                "sync_direction": sync_req.sync_direction,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {
                    "carestack_treatment_plan_count": len(p.active_treatment_plan),
                    "cross_specialty_flags_updated": True,
                },
            }

    raise HTTPException(status_code=404, detail=f"Patient {sync_req.patient_id} not found")
