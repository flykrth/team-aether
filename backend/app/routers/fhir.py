"""
HL7 FHIR R4 Standards Router mounted at /api/fhir.
Proxies and interacts with official HL7 Public Test Servers:
- HAPI FHIR Reference Server: https://hapi.fhir.org/baseR4
- NLM HAPI FHIR Server: https://lforms-fhir.nlm.nih.gov/baseR4
Reference: https://confluence.hl7.org/spaces/FHIR/pages/35718859/Public+Test+Servers
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..models.fhir import (
    Coding,
    CodeableConcept,
    Reference,
    Identifier,
    HumanName,
    Patient,
    Condition,
    MedicationRequest,
    AllergyIntolerance,
    Observation,
    Bundle,
    BundleEntry,
    BundleEntrySearch,
    CapabilityStatement,
)
from ..services.concept_map import terminology_engine
from ..services.fhir_client import (
    fhir_client,
    normalize_ref_id,
    resolve_patient_aliases,
    calculate_similarity,
)

router = APIRouter()


class TranslateRequest(BaseModel):
    """Request body for the FHIR ConceptMap $translate operation."""
    system: str = Field(..., description="Source terminology system URI of the code to translate")
    code: str = Field(..., description="Source code to translate")
    target: Optional[str] = Field(None, description="Target value set/system URI")


class EvaluateRisksRequest(BaseModel):
    """Request body for the Patient $evaluate-risks operation."""
    procedureCode: Optional[str] = Field(None, description="Planned dental procedure code, e.g. CDT D7140 (Extraction)")
    procedureSystem: Optional[str] = Field(
        "http://www.ada.org/cdt", description="Terminology system for the procedure code (default CDT)"
    )


@router.get("/server-status", tags=["FHIR System"])
async def get_fhir_server_status():
    """Returns live connection health, latency, and FHIR version of the public test server."""
    return await fhir_client.check_health()


@router.get("/metadata", tags=["FHIR Metadata"])
async def get_capability_statement():
    """
    Returns the HL7 FHIR R4 CapabilityStatement declaring supported RESTful interactions
    from the connected public FHIR server.
    """
    return await fhir_client.get_capability_statement()


@router.get("/Patient", response_model=Union[Bundle, List[Dict[str, Any]]], tags=["FHIR Resources"])
async def search_patients(
    family: Optional[str] = Query(None, description="Patient family/last name (probabilistic fuzzy matching enabled)"),
    given: Optional[str] = Query(None, description="Patient given/first name"),
    name: Optional[str] = Query(None, description="General patient name"),
    birthdate: Optional[str] = Query(None, description="Patient birth date (YYYY-MM-DD)"),
    birthDate: Optional[str] = Query(None, description="FHIR standard birthDate parameter"),
    identifier: Optional[str] = Query(None, description="Patient identifier or MRN"),
    _format: Optional[str] = Query(None, description="Set to 'list' or 'json' for flat resource list"),
    bundle: Optional[bool] = Query(None, description="Set false to return flat list instead of Bundle"),
):
    """
    Searches patients across the connected HL7 FHIR server and local master patient indices.
    Supports exact, fuzzy, and probabilistic demographic matching with confidence scoring.
    """
    dob_query = birthdate or birthDate
    scored_patients = await fhir_client.search_patients(
        family=family,
        given=given,
        birthdate=dob_query,
        identifier=identifier,
        name=name,
    )

    return_as_list = (_format == "list" or bundle is False)
    if return_as_list:
        return [p for p, _ in scored_patients]

    entries = []
    base_url = "http://localhost:8000/api/fhir"
    for pt, score in scored_patients:
        entries.append(
            BundleEntry(
                fullUrl=f"{base_url}/Patient/{pt['id']}",
                resource=pt,
                search=BundleEntrySearch(
                    mode="match",
                    score=score,
                ),
            )
        )

    return Bundle(
        resourceType="Bundle",
        id=f"bundle-patient-search-{int(datetime.now(timezone.utc).timestamp())}",
        type="searchset",
        timestamp=datetime.now(timezone.utc).isoformat(),
        total=len(entries),
        entry=entries,
    )


@router.get("/Patient/{patient_id}", tags=["FHIR Resources"])
async def get_patient_by_id(patient_id: str):
    """Retrieve single FHIR Patient by ID or MRN from the public FHIR test server."""
    patient = await fhir_client.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"FHIR Patient '{patient_id}' not found")
    return patient


@router.get("/Patient/{patient_id}/$everything", response_model=Bundle, tags=["FHIR Operations"])
async def get_patient_everything(patient_id: str):
    """
    USCDI v5 FHIR $everything operation.
    Exports complete clinical record Bundle (Patient, Conditions, Medications, Allergies, Observations).
    """
    bundle = await fhir_client.get_patient_everything(patient_id)
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found for $everything export.")
    return Bundle.model_validate(bundle)


@router.get("/Condition", response_model=List[Dict[str, Any]], tags=["FHIR Resources"])
async def list_conditions(
    patient: Optional[str] = Query(None, description="Patient reference or ID, e.g. patient-001 or EHR-88201"),
    clinical_status: Optional[str] = Query("active", description="Filter by clinical status (default active)"),
):
    """Filter active medical conditions for a given patient."""
    return await fhir_client.get_conditions(patient_id_or_mrn=patient, status=clinical_status)


@router.get("/MedicationRequest", response_model=List[Dict[str, Any]], tags=["FHIR Resources"])
async def list_medication_requests(
    patient: Optional[str] = Query(None, description="Patient reference or ID"),
    status: Optional[str] = Query("active", description="Filter by medication status (default active)"),
):
    """Filter active medication requests for a given patient."""
    return await fhir_client.get_medication_requests(patient_id_or_mrn=patient, status=status)


@router.get("/AllergyIntolerance", response_model=List[Dict[str, Any]], tags=["FHIR Resources"])
async def list_allergies(
    patient: Optional[str] = Query(None, description="Patient reference or ID"),
):
    """Filter allergy and intolerance records for a given patient."""
    return await fhir_client.get_allergies(patient_id_or_mrn=patient)


@router.get("/Observation", response_model=List[Dict[str, Any]], tags=["FHIR Resources"])
async def list_observations(
    patient: Optional[str] = Query(None, description="Patient reference or ID"),
):
    """Filter diagnostic observations and laboratory results (e.g. HbA1c, INR)."""
    return await fhir_client.get_observations(patient_id_or_mrn=patient)


@router.post("/ConceptMap/$translate", tags=["FHIR Terminology"])
async def translate_concept(body: TranslateRequest):
    """
    HL7 FHIR R4 ConceptMap $translate operation.
    Translates a single coded medical concept (ICD-10-CM, SNOMED-CT, or RxNorm) into
    dental clinical alert concept(s) using the medical-to-dental-contraindications ConceptMap.
    """
    return terminology_engine.translate_concept(body.system, body.code)


@router.post("/Patient/{patient_id}/$evaluate-risks", tags=["FHIR Operations"])
async def evaluate_patient_risks(patient_id: str, body: Optional[EvaluateRisksRequest] = None):
    """
    Semantic dental risk evaluation for a patient.
    Retrieves the patient's active conditions, medications, and allergies, translates
    them via the ConceptMap terminology engine, and returns synthesized dental alerts.
    """
    patient = await fhir_client.get_patient(patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found for $evaluate-risks.")

    clean_id = patient["id"]
    conditions = await fhir_client.get_conditions(clean_id)
    medications = await fhir_client.get_medication_requests(clean_id)
    allergies = await fhir_client.get_allergies(clean_id)

    alerts = terminology_engine.synthesize_patient_risk(conditions, medications, allergies)

    procedure_code = body.procedureCode if body else None
    procedure_system = (body.procedureSystem if body else None) or "http://www.ada.org/cdt"

    return {
        "resourceType": "Parameters",
        "patientId": clean_id,
        "procedure": (
            {"system": procedure_system, "code": procedure_code} if procedure_code else None
        ),
        "alertCount": len(alerts),
        "alerts": alerts,
    }


@router.post("/sync-to-server", tags=["FHIR Operations"])
async def sync_resource_to_server(resource: Dict[str, Any]):
    """Pushes a FHIR resource directly to the configured HL7 Public Test Server."""
    try:
        res = await fhir_client.sync_resource_to_server(resource)
        return {"status": "success", "result": res}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Public FHIR Server synchronization error: {e}")
