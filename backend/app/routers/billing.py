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


# =====================================================================
# Step 9: Automated Letter of Medical Necessity & CareStack Ingestion
# =====================================================================

class GenerateAndAttachLOMNRequest(BaseModel):
    """Request payload to generate and ingest a Letter of Medical Necessity into CareStack PMS."""
    patient_id: str = Field(
        ...,
        description="CareStack Patient ID or FHIR Patient identifier (e.g. 'patient-003', 'CS-2003')",
        examples=["patient-003"],
    )
    cdt_code: str = Field(
        ...,
        description="Dental procedure code requiring medical justification (e.g. 'D4341', 'D7210', 'D7286')",
        examples=["D4341"],
    )


class GenerateAndAttachLOMNResponse(BaseModel):
    """Response containing synthesized LOMN preview, CareStack document ID, and crosswalk opportunity."""
    status: str = "success"
    document_id: str
    preview_content: str
    claim_opportunity: Dict[str, Any]
    html_content: Optional[str] = None
    verification_hash: Optional[str] = None


@router.post(
    "/generate-and-attach-lomn",
    response_model=GenerateAndAttachLOMNResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Letter of Medical Necessity and Ingest into CareStack",
    description=(
        "Orchestrates end-to-end medical cross-coding justification: "
        "1. Pulls patient demographics from CareStack PMS. "
        "2. Pulls active systemic conditions & medications from FHIR EHR. "
        "3. Evaluates crosswalk opportunity via AdministrativeCrossCodingEngine. "
        "4. Synthesizes formal clinical Letter of Medical Necessity via MedicalNecessityGenerator. "
        "5. Ingests and attaches document to CareStack patient chart with SHA-256 verification."
    ),
)
async def generate_and_attach_lomn(request: GenerateAndAttachLOMNRequest) -> GenerateAndAttachLOMNResponse:
    """
    Synthesizes a formal Letter of Medical Necessity (LOMN) and automatically persists
    it in the CareStack patient's attached_documents record.
    """
    from .carestack_mock import CARESTACK_PATIENT_ALIASES, MOCK_PATIENTS, save_patient_document, _find_carestack_patient
    from ..services.fhir_client import fhir_client, normalize_ref_id, resolve_patient_aliases
    from ..services.document_generator import medical_necessity_generator

    clean_id = (request.patient_id or "").lower().strip()
    canonical_id = CARESTACK_PATIENT_ALIASES.get(clean_id, clean_id.upper())

    # Step 1: Pull patient demographics from CareStack PMS
    cs_patient = _find_carestack_patient(request.patient_id)

    patient_demographics: Dict[str, Any] = {}
    if cs_patient:
        patient_demographics = {
            "id": cs_patient.id,
            "account_id": cs_patient.id,
            "mrn": cs_patient.mrn,
            "first_name": cs_patient.first_name,
            "last_name": cs_patient.last_name,
            "patient_name": f"{cs_patient.first_name} {cs_patient.last_name}",
            "dob": cs_patient.birth_date,
            "gender": cs_patient.gender,
            "phone": cs_patient.phone,
            "email": cs_patient.email,
        }
    else:
        # Fallback to FHIR Patient resource
        matching_keys = set(resolve_patient_aliases(clean_id))
        matching_keys.add(clean_id)
        matching_keys.add(canonical_id.lower())
        fhir_patient = None
        for p in fhir_client._local_cache["Patient"]:
            pid = p.get("id", "").lower()
            mrns = [ident.get("value", "").lower() for ident in p.get("identifier", [])]
            if pid in matching_keys or any(m in matching_keys for m in mrns):
                fhir_patient = p
                break
        if fhir_patient:
            names = fhir_patient.get("name", [{}])[0]
            given = " ".join(names.get("given", []))
            family = names.get("family", "")
            patient_demographics = {
                "id": fhir_patient.get("id"),
                "account_id": fhir_patient.get("id"),
                "mrn": fhir_patient.get("identifier", [{}])[0].get("value") or fhir_patient.get("id"),
                "first_name": given,
                "last_name": family,
                "patient_name": f"{given} {family}".strip(),
                "dob": fhir_patient.get("birthDate"),
                "gender": fhir_patient.get("gender"),
                "phone": fhir_patient.get("telecom", [{}])[0].get("value") if fhir_patient.get("telecom") else "",
                "email": "",
            }

    if not patient_demographics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{request.patient_id}' not found across CareStack PMS and FHIR EHR.",
        )

    # Step 2: Pull active conditions and medications from FHIR EHR
    target_ids = {clean_id, canonical_id.lower()}
    if cs_patient:
        target_ids.add(cs_patient.id.lower())
        target_ids.add(cs_patient.mrn.lower())
        if cs_patient.id in ("CS-1003", "CS-2003"):
            target_ids.update({"patient-003", "pat-3", "cs-1003", "cs-2003", "mrn-10003"})
    if patient_demographics.get("id"):
        target_ids.add(patient_demographics["id"].lower())
    if patient_demographics.get("mrn"):
        target_ids.add(patient_demographics["mrn"].lower())
    for a in resolve_patient_aliases(clean_id):
        target_ids.add(a.lower())
    if patient_demographics.get("id"):
        for a in resolve_patient_aliases(patient_demographics["id"]):
            target_ids.add(a.lower())

    def _matches(ref_str: str) -> bool:
        if not ref_str:
            return False
        clean = normalize_ref_id(ref_str).lower()
        return clean in target_ids

    patient_conditions = [c for c in fhir_client._local_cache["Condition"] if _matches(c.get("subject", {}).get("reference", ""))]
    patient_medications = [m for m in fhir_client._local_cache["MedicationRequest"] if _matches(m.get("subject", {}).get("reference", ""))]
    patient_observations = [o for o in fhir_client._local_cache["Observation"] if _matches(o.get("subject", {}).get("reference", ""))]


    clinical_findings = {
        "conditions": patient_conditions,
        "medications": patient_medications,
        "observations": patient_observations,
    }

    # Step 3: Evaluate cross-walk opportunity via AdministrativeCrossCodingEngine
    opportunity = crosswalk_engine.evaluate_cross_coding(
        cdt_code=request.cdt_code,
        patient_conditions=patient_conditions,
        patient_demographics=patient_demographics,
    )
    claim_opportunity = opportunity.model_dump()

    # Step 4: Call MedicalNecessityGenerator to draft the letter
    lomn_data = medical_necessity_generator.generate_letter_of_medical_necessity(
        patient_data=patient_demographics,
        clinical_findings=clinical_findings,
        crosswalk_data={
            "cdt_code": request.cdt_code,
            "suggested_cpt": opportunity.suggested_cpt,
            "cpt_code": opportunity.suggested_cpt,
            "estimated_coverage": opportunity.estimated_coverage,
            "reimbursement_category": opportunity.reimbursement_category,
            "justifying_icd10": opportunity.justifying_icd10,
            "narrative_justification": opportunity.narrative_justification,
        },
    )

    # Step 5: Automatically upload the synthesized document to CareStack's mock Document API
    target_cs_id = patient_demographics.get("id") or canonical_id
    doc_record = save_patient_document(
        patient_id=target_cs_id,
        document_type="Letter of Medical Necessity",
        title=lomn_data["title"],
        file_content=lomn_data["content_markdown"],
        metadata={
            "cdt_code": request.cdt_code,
            "cpt_code": opportunity.suggested_cpt,
            "is_crosswalk_eligible": opportunity.is_eligible,
            "generated_at": lomn_data["generated_at"],
            "verification_hash": lomn_data.get("verification_hash"),
            "html_content": lomn_data["content_html"],
        },
    )

    # Step 6: Return unified response
    return GenerateAndAttachLOMNResponse(
        status="success",
        document_id=doc_record["document_id"],
        preview_content=lomn_data["content_markdown"],
        claim_opportunity=claim_opportunity,
        html_content=lomn_data["content_html"],
        verification_hash=doc_record["verification_hash"],
    )

