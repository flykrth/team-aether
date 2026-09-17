"""
FHIR R4 standard router mounted at /api/fhir.
Provides standard RESTful healthcare data access for Patient, Condition, Observation, and AllergyIntolerance.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from ..schemas.fhir import (
    FHIRPatient,
    FHIRCondition,
    FHIRObservation,
    FHIRAllergyIntolerance,
    FHIRCapabilityStatement,
    FHIRCodeableConcept,
    FHIRCoding,
)

router = APIRouter()

# Mock FHIR database aligned with CareStack MRNs for medical-dental correlation
MOCK_FHIR_PATIENTS: List[FHIRPatient] = [
    FHIRPatient(
        id="EHR-88201",
        name=[{"family": "Vance", "given": ["Eleanor"], "use": "official"}],
        gender="female",
        birthDate="1968-04-12",
        telecom=[{"system": "phone", "value": "555-0192"}],
    ),
    FHIRPatient(
        id="EHR-54109",
        name=[{"family": "Chen", "given": ["Marcus"], "use": "official"}],
        gender="male",
        birthDate="1982-11-03",
        telecom=[{"system": "phone", "value": "555-0143"}],
    ),
    FHIRPatient(
        id="EHR-99342",
        name=[{"family": "Taylor", "given": ["Robert"], "use": "official"}],
        gender="male",
        birthDate="1955-08-27",
        telecom=[{"system": "phone", "value": "555-0188"}],
    ),
]

MOCK_FHIR_CONDITIONS: List[FHIRCondition] = [
    # Eleanor Vance has Osteoporosis treated with Bisphosphonates (MRONJ risk for dental extractions)
    FHIRCondition(
        id="COND-101",
        clinicalStatus={"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
        code=FHIRCodeableConcept(
            coding=[
                {"system": "http://snomed.info/sct", "code": "64859006", "display": "Osteoporosis"},
                {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "M81.0", "display": "Age-related osteoporosis without current pathological fracture"},
            ],
            text="Osteoporosis on IV Bisphosphonate Therapy (Zoledronic Acid)",
        ),
        subject={"reference": "Patient/EHR-88201", "display": "Eleanor Vance"},
        onsetDateTime="2022-03-15",
    ),
    # Robert Taylor has Artificial Heart Valve & Atrial Fibrillation (Infective Endocarditis & Bleeding risk)
    FHIRCondition(
        id="COND-102",
        clinicalStatus={"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
        code=FHIRCodeableConcept(
            coding=[
                {"system": "http://snomed.info/sct", "code": "49601007", "display": "Disorder of cardiovascular system"},
                {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "Z95.2", "display": "Presence of prosthetic heart valve"},
            ],
            text="Mechanical Heart Valve (Requires Antibiotic Prophylaxis)",
        ),
        subject={"reference": "Patient/EHR-99342", "display": "Robert Taylor"},
        onsetDateTime="2018-06-20",
    ),
    # Marcus Chen has Type 2 Diabetes Mellitus
    FHIRCondition(
        id="COND-103",
        clinicalStatus={"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
        code=FHIRCodeableConcept(
            coding=[
                {"system": "http://snomed.info/sct", "code": "44054006", "display": "Type 2 diabetes mellitus"},
                {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9", "display": "Type 2 diabetes mellitus without complications"},
            ],
            text="Type 2 Diabetes Mellitus",
        ),
        subject={"reference": "Patient/EHR-54109", "display": "Marcus Chen"},
        onsetDateTime="2020-01-10",
    ),
]

MOCK_FHIR_OBSERVATIONS: List[FHIRObservation] = [
    # Marcus Chen HbA1c = 8.6% (Uncontrolled, impacts periodontal healing & implant failure risk)
    FHIRObservation(
        id="OBS-201",
        code=FHIRCodeableConcept(
            coding=[{"system": "http://loinc.org", "code": "4548-4", "display": "Hemoglobin A1c/Hemoglobin.total in Blood"}],
            text="Hemoglobin A1c",
        ),
        subject={"reference": "Patient/EHR-54109", "display": "Marcus Chen"},
        valueQuantity={"value": 8.6, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
        effectiveDateTime="2026-08-14",
    ),
    # Robert Taylor INR = 3.2 (Anticoagulated on Warfarin, surgical bleeding hazard)
    FHIRObservation(
        id="OBS-202",
        code=FHIRCodeableConcept(
            coding=[{"system": "http://loinc.org", "code": "6301-6", "display": "INR in Platelet poor plasma by Coagulation assay"}],
            text="International Normalized Ratio (INR)",
        ),
        subject={"reference": "Patient/EHR-99342", "display": "Robert Taylor"},
        valueQuantity={"value": 3.2, "unit": "{INR}", "system": "http://unitsofmeasure.org", "code": "{INR}"},
        effectiveDateTime="2026-09-10",
    ),
]

MOCK_FHIR_ALLERGIES: List[FHIRAllergyIntolerance] = [
    FHIRAllergyIntolerance(
        id="ALG-301",
        criticality="high",
        code=FHIRCodeableConcept(
            coding=[{"system": "http://snomed.info/sct", "code": "764146007", "display": "Allergy to Penicillin"}],
            text="Penicillin G (Anaphylaxis Risk - Use Clindamycin/Azithromycin for dental prophylaxis)",
        ),
        patient={"reference": "Patient/EHR-99342", "display": "Robert Taylor"},
    ),
    FHIRAllergyIntolerance(
        id="ALG-302",
        criticality="high",
        code=FHIRCodeableConcept(
            coding=[{"system": "http://snomed.info/sct", "code": "300916003", "display": "Latex allergy"}],
            text="Natural Rubber Latex Allergy (Requires non-latex dental dams & gloves)",
        ),
        patient={"reference": "Patient/EHR-88201", "display": "Eleanor Vance"},
    ),
]


@router.get("/metadata", response_model=FHIRCapabilityStatement)
async def get_capability_statement():
    """Return FHIR CapabilityStatement for the Medical-Dental Interoperability Node."""
    return FHIRCapabilityStatement(
        rest=[
            {
                "mode": "server",
                "resource": [
                    {"type": "Patient", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "Condition", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "Observation", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                    {"type": "AllergyIntolerance", "interaction": [{"code": "read"}, {"code": "search-type"}]},
                ],
            }
        ]
    )


@router.get("/Patient", response_model=List[FHIRPatient])
async def list_patients(name: Optional[str] = Query(None)):
    """Search FHIR Patient resources."""
    if not name:
        return MOCK_FHIR_PATIENTS
    name_lower = name.lower()
    return [
        p
        for p in MOCK_PATIENTS
        if any(name_lower in g.lower() for n in p.name for g in n.get("given", []))
        or any(name_lower in n.get("family", "").lower() for n in p.name)
    ]


@router.get("/Patient/{patient_id}", response_model=FHIRPatient)
async def get_patient(patient_id: str):
    """Get FHIR Patient by ID."""
    for p in MOCK_FHIR_PATIENTS:
        if p.id == patient_id:
            return p
    raise HTTPException(status_code=404, detail=f"FHIR Patient {patient_id} not found")


@router.get("/Condition", response_model=List[FHIRCondition])
async def list_conditions(patient: Optional[str] = Query(None, description="Patient reference, e.g. EHR-88201")):
    """List medical conditions, optionally filtered by patient ID."""
    if not patient:
        return MOCK_FHIR_CONDITIONS
    norm_id = patient.replace("Patient/", "")
    return [c for c in MOCK_FHIR_CONDITIONS if norm_id in c.subject.get("reference", "")]


@router.get("/Observation", response_model=List[FHIRObservation])
async def list_observations(patient: Optional[str] = Query(None, description="Patient reference")):
    """List medical diagnostic observations (HbA1c, INR, etc.)."""
    if not patient:
        return MOCK_FHIR_OBSERVATIONS
    norm_id = patient.replace("Patient/", "")
    return [o for o in MOCK_FHIR_OBSERVATIONS if norm_id in o.subject.get("reference", "")]


@router.get("/AllergyIntolerance", response_model=List[FHIRAllergyIntolerance])
async def list_allergies(patient: Optional[str] = Query(None, description="Patient reference")):
    """List allergies, including dental-critical drug & latex allergies."""
    if not patient:
        return MOCK_FHIR_ALLERGIES
    norm_id = patient.replace("Patient/", "")
    return [a for a in MOCK_FHIR_ALLERGIES if norm_id in a.patient.get("reference", "")]
