"""
Exhaustive Automated End-to-End Test Suite for the Medical-Dental Interoperability Node (MDIN).
DSOLVE 2026 - DRISHTI, College of Engineering Trivandrum (CET).

Validates every technical layer:
A. Infrastructure & Gateway Verification:
   - test_01_gateway_cors_and_health
   - test_02_cds_hooks_discovery
B. Synthetic USCDI v5 FHIR EHR Node:
   - test_03_demographic_patient_lookup
   - test_04_patient_everything_bundle_integrity
C. Clinical ConceptMap Semantic Translation:
   - test_05_concept_map_translate_warfarin
   - test_06_concept_map_translate_endocarditis
D. Dual CDS Hooks Decision Engine (Clinical Safety + Revenue):
   - test_07_order_select_bleeding_risk_warfarin
   - test_08_order_select_routine_no_fatigue
   - test_09_order_select_antibiotic_penicillin_allergy
E. Administrative Decision Support & Medical Cross-Coding (CMS-1500):
   - test_10_administrative_cross_walk_evaluation
F. Automated Letter of Medical Necessity & Document Writeback:
   - test_11_generate_and_attach_lomn
   - test_12_carestack_document_storage_verification
G. CareStack PMS Chart Integration:
   - test_13_carestack_medical_alert_writeback
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings

client = TestClient(app)


# ==============================================================================
# A. Infrastructure & Gateway Verification
# ==============================================================================

def test_01_gateway_cors_and_health():
    """Execute GET /health and GET /, assert HTTP 200 and verify active CORS headers."""
    # Root service metadata endpoint
    root_res = client.get("/")
    assert root_res.status_code == 200
    root_data = root_res.json()
    assert root_data["status"] == "online"
    assert root_data["service"] == settings.PROJECT_NAME
    assert root_data["version"] == settings.VERSION

    # Health check endpoint
    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"

    # Verify Access-Control-Allow-Origin headers for frontend access
    cors_origin = "http://localhost:5173"
    cors_res = client.get("/health", headers={"Origin": cors_origin})
    assert cors_res.status_code == 200
    assert cors_res.headers.get("access-control-allow-origin") == cors_origin

    # Verify CORS preflight OPTIONS request
    preflight_res = client.options(
        "/health",
        headers={
            "Origin": cors_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert preflight_res.status_code == 200
    assert preflight_res.headers.get("access-control-allow-origin") == cors_origin


def test_02_cds_hooks_discovery():
    """Execute GET /cds-services, assert schema contains patient-view and order-select with prefetch."""
    res = client.get("/cds-services")
    assert res.status_code == 200
    data = res.json()
    assert "services" in data
    assert isinstance(data["services"], list)

    service_map = {s["id"]: s for s in data["services"]}
    assert "patient-view-alert" in service_map
    assert "order-select-contraindication" in service_map

    # Validate patient-view prefetch templates
    pv_service = service_map["patient-view-alert"]
    assert pv_service["hook"] == "patient-view"
    assert "prefetch" in pv_service
    assert "patient" in pv_service["prefetch"]
    assert "conditions" in pv_service["prefetch"]
    assert "medications" in pv_service["prefetch"]

    # Validate order-select prefetch templates
    os_service = service_map["order-select-contraindication"]
    assert os_service["hook"] == "order-select"
    assert "prefetch" in os_service
    assert "conditions" in os_service["prefetch"]


# ==============================================================================
# B. Synthetic USCDI v5 FHIR EHR Node
# ==============================================================================

def test_03_demographic_patient_lookup():
    """Query GET /api/fhir/Patient?family=Doe&birthdate=1968-04-12, assert matched identifier is pat-1."""
    res = client.get("/api/fhir/Patient?family=Doe&birthdate=1968-04-12")
    assert res.status_code == 200
    data = res.json()
    assert data["resourceType"] == "Bundle"
    assert data["total"] >= 1

    patient = data["entry"][0]["resource"]
    matched_id = patient["id"]
    # John Doe is represented by pat-1 (canonical patient-001)
    assert matched_id in ("pat-1", "patient-001") or any(
        ident.get("value") == "pat-1" for ident in patient.get("identifier", [])
    )
    assert any(name.get("family") == "Doe" for name in patient.get("name", []))
    assert patient.get("birthDate") == "1968-04-12"


def test_04_patient_everything_bundle_integrity():
    """Query GET /api/fhir/Patient/pat-1/$everything and assert presence of I48.91, 855332, and 70618001."""
    res = client.get("/api/fhir/Patient/pat-1/$everything")
    assert res.status_code == 200
    bundle = res.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "searchset"

    resources = [entry["resource"] for entry in bundle.get("entry", [])]
    types = {r.get("resourceType") for r in resources}
    assert "Patient" in types
    assert "Condition" in types
    assert "MedicationRequest" in types
    assert "AllergyIntolerance" in types

    # Condition: ICD-10 I48.91 (Atrial Fibrillation)
    conditions = [r for r in resources if r.get("resourceType") == "Condition"]
    has_afib = any(
        any(c.get("code") == "I48.91" for c in cond.get("code", {}).get("coding", []))
        for cond in conditions
    )
    assert has_afib, "USCDI v5 bundle must contain Condition ICD-10 I48.91 (Atrial Fibrillation)"

    # MedicationRequest: RxNorm 855332 (Warfarin Sodium 5 MG)
    meds = [r for r in resources if r.get("resourceType") == "MedicationRequest"]
    has_warfarin = any(
        any(c.get("code") == "855332" for c in med.get("medicationCodeableConcept", {}).get("coding", []))
        for med in meds
    )
    assert has_warfarin, "USCDI v5 bundle must contain MedicationRequest RxNorm 855332 (Warfarin)"

    # AllergyIntolerance: SNOMED 70618001 (Penicillin Allergy)
    allergies = [r for r in resources if r.get("resourceType") == "AllergyIntolerance"]
    has_penicillin_allergy = any(
        any(c.get("code") == "70618001" for c in alg.get("code", {}).get("coding", []))
        for alg in allergies
    )
    assert has_penicillin_allergy, "USCDI v5 bundle must contain AllergyIntolerance SNOMED 70618001 (Penicillin)"


# ==============================================================================
# C. Clinical ConceptMap Semantic Translation
# ==============================================================================

def test_05_concept_map_translate_warfarin():
    """Execute POST /api/fhir/ConceptMap/$translate with code 855332 -> ACTIVE_ANTICOAGULANT."""
    payload = {
        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "code": "855332",
    }
    res = client.post("/api/fhir/ConceptMap/$translate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["result"] is True
    assert len(data["match"]) >= 1
    first_match = data["match"][0]
    assert first_match["concept"]["code"] == "ACTIVE_ANTICOAGULANT"
    assert first_match["equivalence"] == "equivalent"


def test_06_concept_map_translate_endocarditis():
    """Execute POST /api/fhir/ConceptMap/$translate with code 315215002 -> AHA_PROPHYLAXIS_REQUIRED."""
    payload = {
        "system": "http://snomed.info/sct",
        "code": "315215002",
    }
    res = client.post("/api/fhir/ConceptMap/$translate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["result"] is True
    assert len(data["match"]) >= 1
    first_match = data["match"][0]
    assert first_match["concept"]["code"] == "AHA_PROPHYLAXIS_REQUIRED"


# ==============================================================================
# D. Dual CDS Hooks Decision Engine (Clinical Safety + Revenue)
# ==============================================================================

def test_07_order_select_bleeding_risk_warfarin():
    """Send POST /cds-services/order-select-contraindication with pat-1 and D7140 Extraction."""
    payload = {
        "hook": "order-select",
        "hookInstance": "e2e-order-select-bleeding-01",
        "context": {
            "patientId": "pat-1",
            "selections": ["D7140"],
        },
    }
    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    data = res.json()
    cards = data.get("cards", [])
    assert len(cards) >= 1

    bleed_card = next((c for c in cards if "Bleeding" in c["summary"] or "Anticoagulant" in c["summary"]), cards[0])
    assert bleed_card["indicator"] == "critical"
    assert len(bleed_card["summary"]) <= 140
    assert any(term in bleed_card["summary"] for term in ("Warfarin", "Anticoagulant", "Bleeding"))

    detail = bleed_card["detail"].lower()
    assert "inr" in detail and "2.0-3.0" in detail
    assert any(h in detail for h in ("hemostatic", "tranexamic", "sponge", "local"))


def test_08_order_select_routine_no_fatigue():
    """Send POST /cds-services/order-select-contraindication with pat-1 and D0120 Periodic Exam."""
    payload = {
        "hook": "order-select",
        "hookInstance": "e2e-order-select-routine-02",
        "context": {
            "patientId": "pat-1",
            "selections": ["D0120"],
        },
    }
    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data.get("cards") == [], "Routine examination must yield empty cards list [] to prevent alert fatigue"


def test_09_order_select_antibiotic_penicillin_allergy():
    """Send POST /cds-services/order-select-contraindication with pat-2 (Jane Smith) and D4341 Scaling."""
    payload = {
        "hook": "order-select",
        "hookInstance": "e2e-order-select-proph-03",
        "context": {
            "patientId": "pat-2",
            "selections": ["D4341"],
        },
    }
    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    data = res.json()
    cards = data.get("cards", [])
    assert len(cards) >= 1

    proph_card = next((c for c in cards if "Prophylaxis" in c["summary"] or "Valve" in c["summary"]), cards[0])
    assert proph_card["indicator"] in ("critical", "warning")
    assert len(proph_card["summary"]) <= 140

    text_content = (proph_card["summary"] + " " + proph_card["detail"]).lower()
    assert "amoxicillin" in text_content or "penicillin" in text_content
    assert "contraindicated" in text_content or "avoid" in text_content or "alert" in text_content
    assert "clindamycin" in text_content or "azithromycin" in text_content


# ==============================================================================
# E. Administrative Decision Support & Medical Cross-Coding (CMS-1500)
# ==============================================================================

def test_10_administrative_cross_walk_evaluation():
    """Execute POST /api/billing/evaluate-claim for pat-3 (Robert Taylor - Diabetes E11.9) + CDT D4341."""
    payload = {
        "patient_id": "pat-3",
        "cdt_code": "D4341",
    }
    res = client.post("/api/billing/evaluate-claim", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["is_eligible"] is True
    assert data["suggested_cpt"] == "41874"
    assert "E11.9" in data["justifying_icd10"]

    claim = data.get("claim_preview")
    assert claim is not None, "Response must include complete CMS-1500 claim preview"

    # Box 1-7: Patient Demographics from CareStack
    assert "Taylor" in claim["patient_name"] or "Robert" in claim["patient_name"]
    assert claim["patient_dob"] == "1974-11-05"
    assert claim["patient_gender"] == "male"

    # Box 21: Line A points to E11.9
    dx_codes = claim["diagnosis_codes"]
    assert len(dx_codes) >= 1
    assert dx_codes[0]["pointer"] == "A"
    assert dx_codes[0]["code"] == "E11.9"

    # Box 24D: Procedure Code matches CPT 41874 with pointer A
    service_lines = claim["service_lines"]
    assert len(service_lines) >= 1
    assert service_lines[0]["cpt_code"] == "41874"
    assert service_lines[0]["diagnosis_pointer"] == "A"
    assert service_lines[0]["charges"] > 0

    # Box 33: Billing Provider NPI and taxonomy code populated
    billing_provider = claim["billing_provider"]
    assert billing_provider["provider_npi"] == "1928374650"
    assert billing_provider["taxonomy_code"] == "1223S0112X"
    assert "CareStack" in billing_provider["clinic_name"]


# ==============================================================================
# F. Automated Letter of Medical Necessity & Document Writeback
# ==============================================================================

def test_11_generate_and_attach_lomn():
    """Execute POST /api/billing/generate-and-attach-lomn for pat-3 and CDT D4341."""
    payload = {
        "patient_id": "pat-3",
        "cdt_code": "D4341",
    }
    res = client.post("/api/billing/generate-and-attach-lomn", json=payload)
    assert res.status_code in (200, 201)
    data = res.json()
    assert data["status"] == "success"
    assert data.get("document_id") is not None
    assert str(data["document_id"]).startswith("DOC-")
    assert "preview_content" in data
    assert "41874" in data["preview_content"]


def test_12_carestack_document_storage_verification():
    """Execute GET /api/carestack/patients/pat-3/documents and verify ingested LOMN document."""
    res = client.get("/api/carestack/patients/pat-3/documents")
    assert res.status_code == 200
    docs = res.json()
    assert isinstance(docs, list)
    assert len(docs) >= 1

    # Verify presence of the Letter of Medical Necessity for Periodontal Therapy / CPT 41874
    found_lomn = False
    for doc in docs:
        doc_type = doc.get("document_type", "")
        title = doc.get("title", "")
        meta = str(doc.get("metadata", {}))
        if ("Letter of Medical Necessity" in doc_type or "Letter of Medical Necessity" in title) and ("41874" in title or "41874" in meta or "Periodontal" in title):
            found_lomn = True
            break

    assert found_lomn, "CareStack document repository must contain Letter of Medical Necessity for CPT 41874"


# ==============================================================================
# G. CareStack PMS Chart Integration
# ==============================================================================

def test_13_carestack_medical_alert_writeback():
    """Execute POST /api/carestack/patients/pat-1/medical-alerts with CRITICAL alert and verify persistence."""
    alert_payload = {
        "alert": "CRITICAL: Warfarin Anticoagulant Therapy",
        "title": "CRITICAL: Warfarin Anticoagulant Therapy",
        "details": "Patient is actively taking Warfarin Sodium. High risk of uncontrolled surgical hemorrhage. Pre-op INR verification mandated.",
        "alert_type": "critical",
        "category": "coagulation",
        "source": "MDIN Hematology Module",
    }

    # Post alert to patient chart
    res = client.post("/api/carestack/patients/pat-1/medical-alerts", json=alert_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["alert"]["status"] == "posted_to_chart"

    # Verify chart persistence
    get_res = client.get("/api/carestack/patients/pat-1/medical-alerts")
    assert get_res.status_code == 200
    chart_payload = get_res.json()
    assert chart_payload["alert_count"] >= 1
    alert_titles = [a.get("title", "") for a in chart_payload["alerts"]]
    assert any("CRITICAL: Warfarin Anticoagulant Therapy" in t for t in alert_titles)
