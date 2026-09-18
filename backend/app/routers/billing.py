"""
Administrative Decision Support & Medical Cross-Coding Billing Router.
Step 8 of MDIN: Exposes RESTful endpoints for medical primary cross-coding evaluation,
CMS-1500 claim pre-population, and ANSI ASC X12N 837P electronic claim generation.
"""

from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..models.claims import (
    CMS1500Claim,
    CrossCodingOpportunity,
)
from ..services.crosswalk_engine import crosswalk_engine

router = APIRouter()


class EvaluateClaimRequest(BaseModel):
    """Request body for evaluating dental-to-medical cross-coding opportunities."""
    patient_id: str = Field(
        ...,
        description="CareStack Patient ID or FHIR Patient reference (e.g. 'patient-003', 'CS-2001', 'CS-2004')",
        examples=["patient-003"],
    )
    cdt_code: str = Field(
        ...,
        description="Dental procedure code (e.g. 'D7210', 'D7240', 'D4341', 'D4260', 'D7286')",
        examples=["D4341"],
    )
    conditions: Optional[List[Union[Dict[str, Any], str]]] = Field(
        None,
        description="Optional override list of active conditions or ICD-10 codes. If omitted, retrieved from FHIR EHR.",
    )
    demographics: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional override patient demographics. If omitted, retrieved from CareStack PMS.",
    )


class Generate837PResponse(BaseModel):
    """Response containing synthesized ANSI ASC X12N 837P electronic claim transaction."""
    status: str = "success"
    transaction_type: str = "837P (Health Care Claim: Professional)"
    edi_content: str


@router.post(
    "/evaluate-claim",
    response_model=CrossCodingOpportunity,
    summary="Evaluate Dental-to-Medical Cross-Coding Opportunity",
    description=(
        "Scans patient's active FHIR conditions for qualifying medical diagnoses, matches the "
        "procedural CDT code to valid medical CPT codes, and synthesizes a complete, pre-populated "
        "CMS-1500 claim form and 837P electronic transaction payload."
    ),
)
async def evaluate_claim(request: EvaluateClaimRequest) -> CrossCodingOpportunity:
    """
    Evaluates a dental CDT procedure code for medical insurance cross-coding.
    Returns structured CrossCodingOpportunity with full CMS-1500 JSON payload.
    """
    if request.conditions is not None:
        # User supplied explicit conditions and optional demographics
        return crosswalk_engine.evaluate_cross_coding(
            cdt_code=request.cdt_code,
            patient_conditions=request.conditions,
            patient_demographics=request.demographics,
        )

    # Automatically resolve patient conditions and demographics across CareStack PMS and FHIR EHR
    return crosswalk_engine.evaluate_patient(
        patient_id=request.patient_id,
        cdt_code=request.cdt_code,
    )


@router.get(
    "/crosswalk-rules",
    summary="Get Active HL7 FHIR ConceptMap Cross-Coding Rules",
    description="Returns the active CDT-to-CPT crosswalk mapping rules and qualifying diagnostic criteria.",
)
async def get_crosswalk_rules() -> Dict[str, Any]:
    """Returns the loaded FHIR ConceptMap cdt-to-cpt-crosswalk rules."""
    return crosswalk_engine.get_rules()


@router.post(
    "/generate-837p",
    response_model=Generate837PResponse,
    summary="Generate ANSI ASC X12N 837P EDI Transaction",
    description="Converts a CMS1500Claim schema instance into an authentic ANSI ASC X12N 837 Professional EDI string.",
)
async def generate_837p(claim: CMS1500Claim) -> Generate837PResponse:
    """Converts a CMS-1500 claim into an electronic 837P EDI transaction."""
    edi_str = claim.generate_837p()
    return Generate837PResponse(edi_content=edi_str)
