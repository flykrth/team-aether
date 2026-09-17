"""
HL7 FHIR R4 Simulated EHR Node Router mounted at /api/fhir.
Provides standard RESTful healthcare data access, probabilistic demographic matching,
USCDI v5 patient $everything bundle exports, and active clinical resource filtering.
"""

import json
import os
import difflib
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Request

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

router = APIRouter()

# Data file path
DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "synthetic_ehr.json")

# In-memory FHIR store
FHIR_STORE: Dict[str, List[Dict[str, Any]]] = {
    "Patient": [],
    "Condition": [],
    "MedicationRequest": [],
    "AllergyIntolerance": [],
    "Observation": [],
}


def load_synthetic_ehr():
    """Load synthetic EHR bundle and populate the in-memory FHIR store."""
    FHIR_STORE["Patient"].clear()
    FHIR_STORE["Condition"].clear()
    FHIR_STORE["MedicationRequest"].clear()
    FHIR_STORE["AllergyIntolerance"].clear()
    FHIR_STORE["Observation"].clear()

    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                bundle_data = json.load(f)
                for entry in bundle_data.get("entry", []):
                    res = entry.get("resource", {})
                    rt = res.get("resourceType")
                    if rt in FHIR_STORE:
                        FHIR_STORE[rt].append(res)
        except Exception as e:
            print(f"[MDIN] Error loading synthetic_ehr.json: {e}")

    # Seed legacy patients if not already present to guarantee 100% backward compatibility with Phase 1 tests
    existing_patient_ids = {p.get("id") for p in FHIR_STORE["Patient"]}
    if "EHR-88201" not in existing_patient_ids:
        # Eleanor Vance (Osteoporosis / MRONJ risk)
        FHIR_STORE["Patient"].append({
            "resourceType": "Patient",
            "id": "EHR-88201",
            "identifier": [{"system": "http://hospital.smarthealthit.org", "value": "EHR-88201", "use": "official"}],
            "active": True,
            "name": [{"use": "official", "family": "Vance", "given": ["Eleanor"]}],
            "gender": "female",
            "birthDate": "1968-04-12",
            "telecom": [{"system": "phone", "value": "555-0192"}],
        })
        FHIR_STORE["Condition"].append({
            "resourceType": "Condition",
            "id": "COND-101",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active", "display": "Active"}]},
            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": "confirmed", "display": "Confirmed"}]},
            "code": {
                "coding": [
                    {"system": "http://snomed.info/sct", "code": "64859006", "display": "Osteoporosis"},
                    {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "M81.0", "display": "Age-related osteoporosis without current pathological fracture"},
                ],
                "text": "Osteoporosis on IV Bisphosphonate Therapy (Zoledronic Acid)",
            },
            "subject": {"reference": "Patient/EHR-88201", "display": "Eleanor Vance"},
            "onsetDateTime": "2022-03-15",
        })
        FHIR_STORE["AllergyIntolerance"].append({
            "resourceType": "AllergyIntolerance",
            "id": "ALG-302",
            "criticality": "high",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active", "display": "Active"}]},
            "code": {
                "coding": [{"system": "http://snomed.info/sct", "code": "300916003", "display": "Latex allergy"}],
                "text": "Natural Rubber Latex Allergy (Requires non-latex dental dams & gloves)",
            },
            "patient": {"reference": "Patient/EHR-88201", "display": "Eleanor Vance"},
        })

    if "EHR-54109" not in existing_patient_ids:
        # Marcus Chen (Type 2 Diabetes / HbA1c 8.6%)
        FHIR_STORE["Patient"].append({
            "resourceType": "Patient",
            "id": "EHR-54109",
            "identifier": [{"system": "http://hospital.smarthealthit.org", "value": "EHR-54109", "use": "official"}],
            "active": True,
            "name": [{"use": "official", "family": "Chen", "given": ["Marcus"]}],
            "gender": "male",
            "birthDate": "1982-11-03",
            "telecom": [{"system": "phone", "value": "555-0143"}],
        })
        FHIR_STORE["Condition"].append({
            "resourceType": "Condition",
            "id": "COND-103",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active", "display": "Active"}]},
            "code": {
                "coding": [
                    {"system": "http://snomed.info/sct", "code": "44054006", "display": "Type 2 diabetes mellitus"},
                    {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9", "display": "Type 2 diabetes mellitus without complications"},
                ],
                "text": "Type 2 Diabetes Mellitus",
            },
            "subject": {"reference": "Patient/EHR-54109", "display": "Marcus Chen"},
            "onsetDateTime": "2020-01-10",
        })
        FHIR_STORE["Observation"].append({
            "resourceType": "Observation",
            "id": "OBS-201",
            "status": "final",
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c/Hemoglobin.total in Blood"}],
                "text": "Hemoglobin A1c",
            },
            "subject": {"reference": "Patient/EHR-54109", "display": "Marcus Chen"},
            "valueQuantity": {"value": 8.6, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
            "effectiveDateTime": "2026-08-14",
        })


# Initial load
load_synthetic_ehr()


def _calculate_similarity(query_str: str, target_str: str) -> float:
    """Calculates string similarity ratio using difflib SequenceMatcher."""
    q = query_str.strip().lower()
    t = target_str.strip().lower()
    if not q or not t:
        return 0.0
    if q == t:
        return 1.0
    if q in t or t in q:
        return 0.9
    return difflib.SequenceMatcher(None, q, t).ratio()


def _normalize_ref_id(ref_or_id: str) -> str:
    """Extract clean resource ID from reference string like 'Patient/patient-001' or 'patient-001'."""
    if not ref_or_id:
        return ""
    if "/" in ref_or_id:
        return ref_or_id.split("/")[-1].strip()
    return ref_or_id.strip()


@router.get("/metadata", response_model=CapabilityStatement)
async def get_capability_statement():
    """Return FHIR CapabilityStatement for the Medical-Dental Interoperability Node."""
    return CapabilityStatement(
        resourceType="CapabilityStatement",
        status="active",
        name="MDIN_CapabilityStatement",
        title="Medical-Dental Interoperability Node FHIR Server",
        fhirVersion="4.0.1",
        format=["json"],
        rest=[
            {
                "mode": "server",
                "resource": [
                    {"type": "Patient", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "Condition", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "MedicationRequest", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "AllergyIntolerance", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "Observation", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                ],
            }
        ],
    )


@router.get("/Patient", response_model=Union[Bundle, List[Dict[str, Any]]])
async def search_patients(
    family: Optional[str] = Query(None, description="Family (last) name to match"),
    given: Optional[str] = Query(None, description="Given (first) name to match"),
    birthdate: Optional[str] = Query(None, description="Birth date (YYYY-MM-DD)"),
    birthDate: Optional[str] = Query(None, description="Alias for birthdate"),
    identifier: Optional[str] = Query(None, description="MRN or identifier value/system"),
    name: Optional[str] = Query(None, description="General full name or partial name"),
    bundle: Optional[bool] = Query(None, description="Explicitly request Bundle (true) or List (false)"),
    _format: Optional[str] = Query(None, description="Format specifier: 'bundle' or 'list'"),
    request: Request = None,
):
    """
    Probabilistic and exact demographic search for FHIR Patient resources.
    Supports query parameters: family, given, birthdate, identifier, and general name.
    Returns an HL7 FHIR R4 Bundle with match confidence scores in search.score.
    """
    dob_query = birthdate or birthDate
    has_filter = any([family, given, dob_query, identifier, name])

    scored_patients = []

    for patient in FHIR_STORE["Patient"]:
        score = 1.0
        scores = []

        # Identifier exact match
        if identifier:
            id_val = identifier.split("|")[-1].strip().lower()
            patient_ids = [patient.get("id", "").lower()]
            for ident in patient.get("identifier", []):
                if ident.get("value"):
                    patient_ids.append(ident["value"].lower())
            if id_val in patient_ids:
                scores.append(1.0)
            else:
                scores.append(0.0)

        # Birth date exact match
        if dob_query:
            pt_dob = (patient.get("birthDate") or "").strip()
            if pt_dob == dob_query.strip():
                scores.append(1.0)
            else:
                scores.append(0.0)

        # Family name match
        if family:
            fam_scores = []
            for n in patient.get("name", []):
                fam = n.get("family", "")
                fam_scores.append(_calculate_similarity(family, fam))
            scores.append(max(fam_scores) if fam_scores else 0.0)

        # Given name match
        if given:
            giv_scores = []
            for n in patient.get("name", []):
                for g in n.get("given", []):
                    giv_scores.append(_calculate_similarity(given, g))
            scores.append(max(giv_scores) if giv_scores else 0.0)

        # General name match
        if name:
            name_scores = []
            for n in patient.get("name", []):
                full = f"{' '.join(n.get('given', []))} {n.get('family', '')}".strip()
                name_scores.append(_calculate_similarity(name, full))
                if n.get("family"):
                    name_scores.append(_calculate_similarity(name, n["family"]))
                for g in n.get("given", []):
                    name_scores.append(_calculate_similarity(name, g))
            scores.append(max(name_scores) if name_scores else 0.0)

        if has_filter:
            if scores:
                # If any zero score for an exact identifier or birthdate filter, eliminate
                if identifier and scores[0] == 0.0:
                    continue
                if dob_query:
                    # check dob index
                    dob_idx = (1 if identifier else 0)
                    if dob_idx < len(scores) and scores[dob_idx] == 0.0:
                        continue

                avg_score = sum(scores) / len(scores)
                # Keep matches with reasonable score (>= 0.6)
                if avg_score >= 0.6:
                    scored_patients.append((patient, avg_score))
        else:
            scored_patients.append((patient, 1.0))

    # Sort matches by score descending
    scored_patients.sort(key=lambda x: x[1], reverse=True)

    # Check format preferences
    return_as_list = (_format == "list" or bundle is False)

    if return_as_list:
        return [p for p, _ in scored_patients]

    # Standard FHIR R4 Bundle searchset
    entries = []
    base_url = "http://localhost:8000/api/fhir"
    for patient, match_score in scored_patients:
        entries.append(
            BundleEntry(
                fullUrl=f"{base_url}/Patient/{patient['id']}",
                resource=patient,
                search=BundleEntrySearch(
                    mode="match",
                    score=round(match_score, 2),
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


@router.get("/Patient/{patient_id}")
async def get_patient_by_id(patient_id: str):
    """Retrieve single FHIR Patient by ID or MRN."""
    norm_id = _normalize_ref_id(patient_id).lower()
    for p in FHIR_STORE["Patient"]:
        if p.get("id", "").lower() == norm_id:
            return p
        for ident in p.get("identifier", []):
            if ident.get("value", "").lower() == norm_id:
                return p
    raise HTTPException(status_code=404, detail=f"FHIR Patient '{patient_id}' not found")


@router.get("/Patient/{patient_id}/$everything", response_model=Bundle)
async def get_patient_everything(patient_id: str):
    """
    USCDI v5 FHIR $everything operation.
    Returns complete FHIR R4 Bundle containing all medical records, active conditions,
    medication requests, allergy intolerances, and diagnostic observations for the patient.
    """
    norm_id = _normalize_ref_id(patient_id).lower()

    # Find the patient
    matched_patient = None
    all_matching_keys = [norm_id]
    for p in FHIR_STORE["Patient"]:
        pid = p.get("id", "").lower()
        mrns = [ident.get("value", "").lower() for ident in p.get("identifier", [])]
        if norm_id == pid or norm_id in mrns:
            matched_patient = p
            all_matching_keys.append(pid)
            all_matching_keys.extend(mrns)
            break

    if not matched_patient:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found for $everything export.")

    entries: List[BundleEntry] = []
    base_url = "http://localhost:8000/api/fhir"

    # Add Patient resource
    entries.append(
        BundleEntry(
            fullUrl=f"{base_url}/Patient/{matched_patient['id']}",
            resource=matched_patient,
            search=BundleEntrySearch(mode="match", score=1.0),
        )
    )

    def _matches_patient(ref_str: str) -> bool:
        if not ref_str:
            return False
        clean = _normalize_ref_id(ref_str).lower()
        return any(k == clean for k in all_matching_keys)

    # Add all Conditions for patient
    for cond in FHIR_STORE["Condition"]:
        subj_ref = cond.get("subject", {}).get("reference", "")
        if _matches_patient(subj_ref):
            entries.append(
                BundleEntry(
                    fullUrl=f"{base_url}/Condition/{cond['id']}",
                    resource=cond,
                    search=BundleEntrySearch(mode="include"),
                )
            )

    # Add all MedicationRequests for patient
    for med in FHIR_STORE["MedicationRequest"]:
        subj_ref = med.get("subject", {}).get("reference", "")
        if _matches_patient(subj_ref):
            entries.append(
                BundleEntry(
                    fullUrl=f"{base_url}/MedicationRequest/{med['id']}",
                    resource=med,
                    search=BundleEntrySearch(mode="include"),
                )
            )

    # Add all AllergyIntolerances for patient
    for alg in FHIR_STORE["AllergyIntolerance"]:
        patient_ref = alg.get("patient", {}).get("reference", "")
        if _matches_patient(patient_ref):
            entries.append(
                BundleEntry(
                    fullUrl=f"{base_url}/AllergyIntolerance/{alg['id']}",
                    resource=alg,
                    search=BundleEntrySearch(mode="include"),
                )
            )

    # Add all Observations for patient
    for obs in FHIR_STORE["Observation"]:
        subj_ref = obs.get("subject", {}).get("reference", "")
        if _matches_patient(subj_ref):
            entries.append(
                BundleEntry(
                    fullUrl=f"{base_url}/Observation/{obs['id']}",
                    resource=obs,
                    search=BundleEntrySearch(mode="include"),
                )
            )

    return Bundle(
        resourceType="Bundle",
        id=f"bundle-uscdi-v5-{matched_patient['id']}-$everything",
        type="searchset",
        timestamp=datetime.now(timezone.utc).isoformat(),
        total=len(entries),
        entry=entries,
    )


@router.get("/Condition", response_model=List[Dict[str, Any]])
async def list_conditions(
    patient: Optional[str] = Query(None, description="Patient reference or ID, e.g. patient-001 or EHR-88201"),
    clinical_status: Optional[str] = Query("active", description="Filter by clinical status (default active)"),
):
    """Filter active medical conditions for a given patient."""
    results = []
    norm_patient = _normalize_ref_id(patient).lower() if patient else None

    for cond in FHIR_STORE["Condition"]:
        # Match patient if provided
        if norm_patient:
            subj_ref = _normalize_ref_id(cond.get("subject", {}).get("reference", "")).lower()
            if norm_patient not in subj_ref:
                continue

        # Check clinicalStatus
        if clinical_status:
            cs = cond.get("clinicalStatus", {})
            codings = cs.get("coding", [])
            is_match = any(c.get("code", "").lower() == clinical_status.lower() for c in codings)
            if not is_match and codings:
                continue

        results.append(cond)

    return results


@router.get("/MedicationRequest", response_model=List[Dict[str, Any]])
async def list_medication_requests(
    patient: Optional[str] = Query(None, description="Patient reference or ID"),
    status: Optional[str] = Query("active", description="Filter by medication status (default active)"),
):
    """Filter active medication requests for a given patient."""
    results = []
    norm_patient = _normalize_ref_id(patient).lower() if patient else None

    for med in FHIR_STORE["MedicationRequest"]:
        if norm_patient:
            subj_ref = _normalize_ref_id(med.get("subject", {}).get("reference", "")).lower()
            if norm_patient not in subj_ref:
                continue

        if status and med.get("status", "").lower() != status.lower():
            continue

        results.append(med)

    return results


@router.get("/AllergyIntolerance", response_model=List[Dict[str, Any]])
async def list_allergies(
    patient: Optional[str] = Query(None, description="Patient reference or ID"),
):
    """Filter allergy and intolerance records for a given patient."""
    results = []
    norm_patient = _normalize_ref_id(patient).lower() if patient else None

    for alg in FHIR_STORE["AllergyIntolerance"]:
        if norm_patient:
            patient_ref = _normalize_ref_id(alg.get("patient", {}).get("reference", "")).lower()
            if norm_patient not in patient_ref:
                continue

        results.append(alg)

    return results


@router.get("/Observation", response_model=List[Dict[str, Any]])
async def list_observations(
    patient: Optional[str] = Query(None, description="Patient reference or ID"),
):
    """Filter diagnostic observations and laboratory results (e.g. HbA1c, INR)."""
    results = []
    norm_patient = _normalize_ref_id(patient).lower() if patient else None

    for obs in FHIR_STORE["Observation"]:
        if norm_patient:
            subj_ref = _normalize_ref_id(obs.get("subject", {}).get("reference", "")).lower()
            if norm_patient not in subj_ref:
                continue

        results.append(obs)

    return results
