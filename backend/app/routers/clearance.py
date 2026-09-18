"""
API Router for Step 11: Pre-Screening Automated Medical-Clearance Engine (The Digital Clearance Passport).
Provides REST endpoints for dispatching digital clearance requests, physician view/retrieval,
and attending physician clinical sign-off with bi-directional CareStack PMS writeback.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Path

from ..models.clearance import (
    ClearanceRequestPayload,
    ClearanceDecision,
    ClearanceDispatchRequest,
)
from ..services.clearance_engine import (
    medical_clearance_service,
    MedicalClearanceService,
)

router = APIRouter()


@router.post(
    "/dispatch",
    response_model=ClearanceRequestPayload,
    status_code=status.HTTP_201_CREATED,
    summary="Dispatch Digital Clearance Passport",
    description=(
        "Synthesizes and dispatches an automated medical-clearance passport for a patient "
        "scheduled for an invasive dental procedure. Evaluates ConceptMap clinical risks "
        "(e.g. active Warfarin + Atrial Fibrillation), assigns an attending cardiologist/physician, "
        "and generates linked HL7 FHIR R4 Task and CommunicationRequest resources."
    ),
)
async def dispatch_clearance_passport(
    payload: ClearanceDispatchRequest,
):
    """Dispatch a new pre-screening clearance passport."""
    try:
        passport = medical_clearance_service.create_clearance_passport(
            patient_id=payload.patient_id,
            cdt_code=payload.cdt_code,
            carestack_data=payload.carestack_data,
            ehr_data=payload.ehr_data,
        )
        return passport
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to dispatch medical clearance passport: {str(e)}",
        )


@router.get(
    "/patient/{patient_id}",
    response_model=List[ClearanceRequestPayload],
    summary="Get Patient Clearance Passports",
    description="Retrieves all digital clearance requests associated with a patient by ID or MRN.",
)
async def get_patient_clearance_requests(
    patient_id: str = Path(..., description="CareStack or Medical EHR patient identifier"),
):
    """List all clearance requests for a patient."""
    requests = medical_clearance_service.get_clearance_by_patient(patient_id)
    return requests


@router.get(
    "/{request_id}",
    response_model=ClearanceRequestPayload,
    summary="Retrieve Clearance Passport",
    description="Retrieves a specific digital clearance passport by its UUID for physician review.",
)
async def get_clearance_passport_by_id(
    request_id: str = Path(..., description="Unique UUID string of the clearance request"),
):
    """Retrieve specific clearance passport for physician evaluation."""
    passport = medical_clearance_service.get_clearance_by_id(request_id)
    if not passport:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medical clearance request '{request_id}' not found.",
        )
    return passport


@router.post(
    "/{request_id}/decision",
    response_model=ClearanceRequestPayload,
    summary="Record Attending Physician Decision",
    description=(
        "Records the attending physician's clinical sign-off decision "
        "(APPROVED | APPROVED_WITH_CONDITIONS | REJECTED), target INR parameters, "
        "and hold directives. Automatically triggers the CareStack PMS webhook and updates "
        "the patient chart with an alert."
    ),
)
async def submit_physician_decision(
    request_id: str = Path(..., description="Unique UUID string of the clearance request"),
    decision: ClearanceDecision = ...,
):
    """Submit physician evaluation decision and trigger CareStack webhook."""
    # Ensure request_id consistency
    if decision.request_id != request_id:
        decision.request_id = request_id

    try:
        updated_passport = medical_clearance_service.record_physician_decision(decision)
        return updated_passport
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medical clearance request '{request_id}' not found in registry.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record physician clearance decision: {str(e)}",
        )
