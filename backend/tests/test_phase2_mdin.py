"""
Test suite for Phase 2 of the Medical-Dental Interoperability Node (MDIN).
Verifies:
1. synthetic_ehr.json FHIR R4 Bundle structure and clinical requirements for the 3 patients.
2. Pydantic models in backend.app.models.fhir.
3. FHIR EHR Mock Router (/api/fhir) endpoints:
   - Probabilistic & exact search on /Patient
   - USCDI v5 Bundle export on /Patient/{id}/$everything
   - Active filtering on /Condition, /MedicationRequest, /AllergyIntolerance, /Observation
4. CareStack Mock Router (/api/carestack) endpoints:
   - Webhook check-in / appointment creation with demographic matching & in-memory caching
   - Patient listing & search
   - High-priority medical alert chart write-backs
"""

import json
import os
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models.fhir import (
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
)

client = TestClient(app)


def test_synthetic_ehr_file_and_schema():
    """Verify synthetic_ehr.json exists, is valid FHIR R4 Bundle, and contains the 3 clinical patient personas."""
    data_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "data", "synthetic_ehr.json")
    assert os.path.exists(data_path), "synthetic_ehr.json must exist"

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate against Pydantic Bundle model
    bundle = Bundle.model_validate(data)
    assert bundle.resourceType == "Bundle"
    assert bundle.type == "collection"

    # Extract all resources
    resources_by_type = {}
    for entry in bundle.entry:
        res = entry.resource
        rt = res.get("resourceType")
        resources_by_type.setdefault(rt, []).append(res)

    assert "Patient" in resources_by_type
    assert len(resources_by_type["Patient"]) == 4  # patient-001..003 + Robert Chen (patient-chen, Step 15)

    # Patient 1: John Doe
    p1 = next((p for p in resources_by_type["Patient"] if any(n.get("family") == "Doe" for n in p.get("name", []))), None)
    assert p1 is not None
    assert p1.get("birthDate") == "1968-04-12"
    assert p1.get("gender") == "male"
    assert any(n.get("given") == ["John"] for n in p1.get("name", []))

    # Patient 1 Condition: Atrial Fibrillation (ICD-10: I48.91, SNOMED: 49436004)
    cond1 = next(
        (c for c in resources_by_type["Condition"] if "patient-001" in c.get("subject", {}).get("reference", "")),
        None,
    )
    assert cond1 is not None
    assert cond1.get("clinicalStatus", {}).get("coding", [{}])[0].get("code") == "active"
    codings1 = cond1.get("code", {}).get("coding", [])
    assert any(c.get("code") == "I48.91" for c in codings1)
    assert any(c.get("code") == "49436004" for c in codings1)

    # Patient 1 MedicationRequest: Warfarin Sodium 5 MG (RxNorm: 855332)
    med1 = next(
        (m for m in resources_by_type["MedicationRequest"] if "patient-001" in m.get("subject", {}).get("reference", "")),
        None,
    )
    assert med1 is not None
    assert med1.get("status") == "active"
    med_codings1 = med1.get("medicationCodeableConcept", {}).get("coding", [])
    assert any(c.get("code") == "855332" for c in med_codings1)

    # Patient 1 AllergyIntolerance: Penicillin (SNOMED: 70618001, Anaphylaxis)
    alg1 = next(
        (a for a in resources_by_type["AllergyIntolerance"] if "patient-001" in a.get("patient", {}).get("reference", "")),
        None,
    )
    assert alg1 is not None
    assert alg1.get("criticality") == "high"
    assert any(c.get("code") == "70618001" for c in alg1.get("code", {}).get("coding", []))
    reactions = alg1.get("reaction", [])
    assert len(reactions) >= 1
    manifestations = reactions[0].get("manifestation", [])
    assert any("Anaphylaxis" in m.get("text", "") or any(c.get("code") == "39579001" for c in m.get("coding", [])) for m in manifestations)

    # Patient 2: Jane Smith
    p2 = next((p for p in resources_by_type["Patient"] if any(n.get("family") == "Smith" for n in p.get("name", []))), None)
    assert p2 is not None
    assert p2.get("birthDate") == "1980-09-23"
    assert p2.get("gender") == "female"

    # Patient 2 Condition: Prosthetic cardiac valve / Infective Endocarditis (SNOMED: 315215002, ICD-10: I33.0)
    cond2 = next(
        (c for c in resources_by_type["Condition"] if "patient-002" in c.get("subject", {}).get("reference", "")),
        None,
    )
    assert cond2 is not None
    codings2 = cond2.get("code", {}).get("coding", [])
    assert any(c.get("code") == "315215002" for c in codings2)
    assert any(c.get("code") == "I33.0" for c in codings2)

    # Patient 2 MedicationRequest: Aspirin 81 MG (RxNorm: 243670)
    med2 = next(
        (m for m in resources_by_type["MedicationRequest"] if "patient-002" in m.get("subject", {}).get("reference", "")),
        None,
    )
    assert med2 is not None
    assert med2.get("status") == "active"
    assert any(c.get("code") == "243670" for c in med2.get("medicationCodeableConcept", {}).get("coding", []))

    # Patient 3: Robert Taylor
    p3 = next((p for p in resources_by_type["Patient"] if any(n.get("family") == "Taylor" for n in p.get("name", []))), None)
    assert p3 is not None
    assert p3.get("birthDate") == "1974-11-05"
    assert p3.get("gender") == "male"

    # Patient 3 Condition: Type 2 Diabetes Mellitus with high HbA1c (SNOMED: 73211009, ICD-10: E11.9)
    cond3 = next(
        (c for c in resources_by_type["Condition"] if "patient-003" in c.get("subject", {}).get("reference", "")),
        None,
    )
    assert cond3 is not None
    codings3 = cond3.get("code", {}).get("coding", [])
    assert any(c.get("code") == "73211009" for c in codings3)
    assert any(c.get("code") == "E11.9" for c in codings3)

    # Patient 3 Observation: HbA1c 9.2% (LOINC: 4548-4)
    obs3 = next(
        (o for o in resources_by_type["Observation"] if "patient-003" in o.get("subject", {}).get("reference", "")),
        None,
    )
    assert obs3 is not None
    assert obs3.get("status") == "final"
    assert any(c.get("code") == "4548-4" for c in obs3.get("code", {}).get("coding", []))
    assert obs3.get("valueQuantity", {}).get("value") == 9.2
    assert obs3.get("valueQuantity", {}).get("unit") == "%"


def test_fhir_models_direct_instantiation():
    """Verify Pydantic models in backend.app.models.fhir can be constructed and validated."""
    patient = Patient(
        id="test-p1",
        identifier=[Identifier(value="TEST-123", system="http://test.org")],
        name=[HumanName(family="Tester", given=["Alex"])],
        birthDate="1990-01-01",
        gender="male",
    )
    assert patient.get_full_name() == "Alex Tester"
    assert patient.get_mrn() == "TEST-123"

    cond = Condition(
        id="test-c1",
        clinicalStatus=CodeableConcept(coding=[Coding(code="active")]),
        code=CodeableConcept(text="Hypertension", coding=[Coding(system="http://snomed.info/sct", code="38341003")]),
        subject=Reference(reference="Patient/test-p1"),
    )
    assert cond.is_active() is True
    assert cond.code.get_display() == "Hypertension"

    med = MedicationRequest(
        id="test-m1",
        status="active",
        intent="order",
        subject=Reference(reference="Patient/test-p1"),
        medicationCodeableConcept=CodeableConcept(text="Lisinopril 10 MG"),
    )
    assert med.is_active() is True

    allergy = AllergyIntolerance(
        id="test-a1",
        criticality="high",
        code=CodeableConcept(text="Latex"),
        patient=Reference(reference="Patient/test-p1"),
    )
    assert allergy.criticality == "high"

    bundle = Bundle(
        type="searchset",
        entry=[{"resource": patient.model_dump()}],
        total=1,
    )
    assert bundle.resourceType == "Bundle"
    assert bundle.total == 1


def test_fhir_patient_search_exact():
    """Verify exact search query parameters on /api/fhir/Patient."""
    # Search by family name
    res = client.get("/api/fhir/Patient?family=Doe")
    assert res.status_code == 200
    data = res.json()
    assert data["resourceType"] == "Bundle"
    assert data["total"] >= 1
    p = data["entry"][0]["resource"]
    assert any(n.get("family") == "Doe" for n in p["name"])

    # Search by given name
    res_given = client.get("/api/fhir/Patient?given=Jane")
    assert res_given.status_code == 200
    data_given = res_given.json()
    assert data_given["total"] >= 1
    p_jane = data_given["entry"][0]["resource"]
    assert any("Jane" in n.get("given", []) for n in p_jane["name"])

    # Search by birthdate
    res_dob = client.get("/api/fhir/Patient?birthdate=1974-11-05")
    assert res_dob.status_code == 200
    data_dob = res_dob.json()
    assert data_dob["total"] >= 1
    p_robert = data_dob["entry"][0]["resource"]
    assert p_robert["birthDate"] == "1974-11-05"

    # Search by MRN identifier
    res_id = client.get("/api/fhir/Patient?identifier=MRN-10001")
    assert res_id.status_code == 200
    data_id = res_id.json()
    assert data_id["total"] >= 1
    p_mrn = data_id["entry"][0]["resource"]
    assert any(ident.get("value") == "MRN-10001" for ident in p_mrn.get("identifier", []))


def test_fhir_patient_search_probabilistic_fuzzy():
    """Verify probabilistic and fuzzy demographic matching on /api/fhir/Patient."""
    # Slight typo in family name "Doee" -> matches "Doe"
    res = client.get("/api/fhir/Patient?family=Doee")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    matched = data["entry"][0]
    assert matched["search"]["score"] > 0.6
    assert any(n.get("family") == "Doe" for n in matched["resource"]["name"])

    # Slight typo in given name "Jhon" -> matches "John"
    res_typo = client.get("/api/fhir/Patient?given=Jhon")
    assert res_typo.status_code == 200
    data_typo = res_typo.json()
    assert data_typo["total"] >= 1


def test_fhir_patient_search_list_format():
    """Verify _format=list or bundle=false returns flat list of Patient resources."""
    res = client.get("/api/fhir/Patient?family=Doe&_format=list")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["resourceType"] == "Patient"


def test_fhir_patient_everything_uscdi_v5():
    """Verify GET /api/fhir/Patient/{id}/$everything returns full USCDI v5 FHIR Bundle."""
    # John Doe (High Risk Extraction)
    res = client.get("/api/fhir/Patient/patient-001/$everything")
    assert res.status_code == 200
    bundle = res.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "searchset"
    assert bundle["total"] >= 4  # Patient, Condition, MedicationRequest, AllergyIntolerance

    types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert "Patient" in types
    assert "Condition" in types
    assert "MedicationRequest" in types
    assert "AllergyIntolerance" in types

    # Jane Smith (Endocarditis / Prophylaxis)
    res_jane = client.get("/api/fhir/Patient/patient-002/$everything")
    assert res_jane.status_code == 200
    bundle_jane = res_jane.json()
    assert bundle_jane["total"] >= 3
    types_jane = {e["resource"]["resourceType"] for e in bundle_jane["entry"]}
    assert "Patient" in types_jane
    assert "Condition" in types_jane
    assert "MedicationRequest" in types_jane

    # Robert Taylor (Diabetic Healing Delay)
    res_rob = client.get("/api/fhir/Patient/patient-003/$everything")
    assert res_rob.status_code == 200
    bundle_rob = res_rob.json()
    types_rob = {e["resource"]["resourceType"] for e in bundle_rob["entry"]}
    assert "Patient" in types_rob
    assert "Condition" in types_rob
    assert "Observation" in types_rob

    # Non-existent patient returns 404
    res_404 = client.get("/api/fhir/Patient/non-existent-id-999/$everything")
    assert res_404.status_code == 404


def test_fhir_clinical_resource_filtering():
    """Verify active filtering on Condition, MedicationRequest, and AllergyIntolerance endpoints."""
    # Active conditions for John Doe
    cond_res = client.get("/api/fhir/Condition?patient=patient-001")
    assert cond_res.status_code == 200
    conds = cond_res.json()
    assert len(conds) >= 1
    assert "Atrial Fibrillation" in conds[0]["code"]["text"]

    # Active medications for John Doe
    med_res = client.get("/api/fhir/MedicationRequest?patient=patient-001")
    assert med_res.status_code == 200
    meds = med_res.json()
    assert len(meds) >= 1
    assert "Warfarin" in meds[0]["medicationCodeableConcept"]["text"]

    # Allergies for John Doe
    alg_res = client.get("/api/fhir/AllergyIntolerance?patient=patient-001")
    assert alg_res.status_code == 200
    algs = alg_res.json()
    assert len(algs) >= 1
    assert "Penicillin" in algs[0]["code"]["text"]

    # Observations for Robert Taylor
    obs_res = client.get("/api/fhir/Observation?patient=patient-003")
    assert obs_res.status_code == 200
    obs = obs_res.json()
    assert len(obs) >= 1
    assert obs[0]["valueQuantity"]["value"] == 9.2


def test_carestack_webhook_demographic_matching_and_caching():
    """Verify POST /api/carestack/webhook matches demographics against FHIR EHR and caches context in-memory."""
    # Simulate check-in for John Doe with proposed surgical extraction
    payload = {
        "event_type": "patient.checkin",
        "patient": {
            "id": "CS-2001",
            "first_name": "John",
            "last_name": "Doe",
            "birth_date": "1968-04-12",
            "gender": "male",
            "mrn": "MRN-10001",
        },
        "appointment": {
            "operatory": "Operatory 1",
            "provider": "Dr. Sarah Mitchell, DDS",
            "reason": "Extraction Tooth #30",
            "procedures": [
                {
                    "code": "D7140",
                    "description": "Extraction, erupted tooth or exposed root",
                    "tooth_number": "30",
                    "status": "scheduled",
                }
            ],
        },
    }

    res = client.post("/api/carestack/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "synchronized"
    assert data["carestack_patient_id"] == "CS-2001"
    assert data["matched_ehr_patient_id"] == "patient-001"
    assert data["cached"] is True
    assert data["alerts_generated"] >= 1

    # Verify context is stored in in-memory cache
    cache_res = client.get("/api/carestack/cache/CS-2001")
    assert cache_res.status_code == 200
    cached = cache_res.json()
    assert cached["carestack_patient_id"] == "CS-2001"
    assert cached["ehr_patient_id"] == "patient-001"
    assert cached["clinical_summary"]["active_conditions_count"] >= 1
    assert cached["clinical_summary"]["active_medications_count"] >= 1
    assert cached["clinical_summary"]["allergies_count"] >= 1

    # Verify alerts include Warfarin hemorrhage risk
    alert_titles = [a["title"] for a in cached["alerts"]]
    assert any("Anticoagulation" in t or "Hemorrhage" in t or "Warfarin" in t for t in alert_titles)
    assert any("Penicillin" in t for t in alert_titles)


def test_carestack_webhook_prosthetic_valve_prophylaxis():
    """Verify webhook for Jane Smith triggers AHA antibiotic prophylaxis alert."""
    payload = {
        "event_type": "appointment.created",
        "patient": {
            "id": "CS-2002",
            "first_name": "Jane",
            "last_name": "Smith",
            "birth_date": "1980-09-23",
            "gender": "female",
            "mrn": "MRN-10002",
        },
        "appointment": {
            "operatory": "Hygiene 1",
            "provider": "Dr. Sarah Mitchell, DDS",
            "procedures": [
                {
                    "code": "D1110",
                    "description": "Prophylaxis - adult (scaling/polishing)",
                    "tooth_number": "General",
                    "status": "scheduled",
                }
            ],
        },
    }

    res = client.post("/api/carestack/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "synchronized"
    assert data["matched_ehr_patient_id"] == "patient-002"

    alert_titles = [a["title"] for a in data["alerts"]]
    assert any("Prophylaxis" in t or "Prosthetic Valve" in t for t in alert_titles)


def test_carestack_patients_listing():
    """Verify GET /api/carestack/patients returns registered dental patients."""
    res = client.get("/api/carestack/patients")
    assert res.status_code == 200
    patients = res.json()
    assert len(patients) >= 3

    # Check that John Doe, Jane Smith, and Robert Taylor are in the list
    names = [f"{p['first_name']} {p['last_name']}" for p in patients]
    assert "John Doe" in names
    assert "Jane Smith" in names
    assert "Robert Taylor" in names

    # Test search filter
    search_res = client.get("/api/carestack/patients?search=Smith")
    assert search_res.status_code == 200
    smiths = search_res.json()
    assert len(smiths) >= 1
    assert smiths[0]["last_name"] == "Smith"


def test_carestack_medical_alerts_writeback():
    """Verify POST /api/carestack/patients/{id}/medical-alerts writes flags back to CareStack chart."""
    alert_payload = {
        "alert_type": "critical",
        "category": "coagulation",
        "title": "CHART ALERT: Mandatory Local Hemostasis (Warfarin Therapy)",
        "details": "Patient taking Warfarin 5mg daily. Pre-op INR 2.8. Prepare gelatin sponge and 4.8% tranexamic acid rinse.",
        "source": "MDIN Hematology Module",
        "action_required": "Place local hemostatic agent into socket immediately post-extraction.",
    }

    res = client.post("/api/carestack/patients/CS-2001/medical-alerts", json=alert_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "successfully written back" in data["message"]
    assert data["alert"]["status"] == "posted_to_chart"

    # Query the posted alerts
    get_res = client.get("/api/carestack/patients/CS-2001/medical-alerts")
    assert get_res.status_code == 200
    alerts_data = get_res.json()
    assert alerts_data["alert_count"] >= 1
    assert any(a["title"] == alert_payload["title"] for a in alerts_data["alerts"])
