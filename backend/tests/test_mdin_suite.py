"""
Exhaustive Automated Test Suite for the Medical-Dental Interoperability Node (MDIN).
DSOLVE 2026 - DRISHTI, College of Engineering Trivandrum (CET).

Tiers Covered:
- Tier 1: Infrastructure & Discovery
  * test_health_and_root: Server status, version, and active CORS headers.
  * test_cds_discovery_endpoint: CDS Discovery schema, required services, and prefetch templates.

- Tier 2: Synthetic USCDI v5 FHIR EHR Endpoints
  * test_fhir_patient_search_exact_and_probabilistic: Query by family & birthdate, verify pat-1, fuzzy matching.
  * test_fhir_patient_everything_bundle: USCDI v5 $everything export with Condition (I48.91), Medication (855332), Allergy (70618001).
  * test_fhir_unmatched_patient: Nonexistent patient search handled gracefully with empty searchset.

- Tier 3: FHIR ConceptMap Semantic Translation Engine
  * test_concept_map_individual_translation: RxNorm 855332 -> ACTIVE_ANTICOAGULANT (equivalent).
  * test_concept_map_cardiac_prophylaxis: SNOMED 315215002 -> AHA_PROPHYLAXIS_REQUIRED.
  * test_multifactor_risk_synthesis: Patient pat-1 with CDT D7140 -> CRITICAL_HEMORRHAGE_HAZARD.

- Tier 4: CDS Hooks Clinical Decision Support Engine
  * test_order_select_high_bleeding_risk: pat-1 (Warfarin + AFib) + D7140 Extraction -> Critical card, INR metrics, hemostasis, suggestions.
  * test_order_select_routine_procedure_no_fatigue: pat-1 + D0120 Periodic Exam -> Empty cards [] to prevent clinical alert fatigue.
  * test_order_select_prophylaxis_penicillin_allergy: pat-2 (Jane Smith - Prosthetic Valve + Penicillin Allergy) + D4341 Scaling -> Warning/Critical card, warns against Amoxicillin, recommends Clindamycin/Azithromycin.

- Tier 5: CareStack Integration & Bidirectional Writeback
  * test_carestack_webhook_patient_sync: Appointment check-in webhook synchronizes demographics & caches EHR state.
  * test_carestack_medical_alert_writeback: POST alert writeback to patient pat-1 profile and verify persistence.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.config import settings

client = TestClient(app)


# ==============================================================================
# Tier 1: Infrastructure & Discovery
# ==============================================================================

def test_health_and_root():
    """Verify server status, version, and active CORS headers across root and health endpoints."""
    # 1. Root discovery endpoint
    root_resp = client.get("/")
    assert root_resp.status_code == 200
    root_data = root_resp.json()
    assert root_data["status"] == "online"
    assert root_data["service"] == settings.PROJECT_NAME
    assert root_data["version"] == settings.VERSION
    assert "endpoints" in root_data
    assert root_data["endpoints"]["cds_discovery"] == "/cds-services"
    assert root_data["endpoints"]["fhir"] == "/api/fhir/metadata"

    # 2. Health check endpoint
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] == "healthy"
    assert health_data["version"] == settings.VERSION

    # 3. Active CORS headers for frontend origins
    cors_origin = "http://localhost:5173"
    cors_resp = client.get("/health", headers={"Origin": cors_origin})
    assert cors_resp.status_code == 200
    assert cors_resp.headers.get("access-control-allow-origin") == cors_origin
    assert cors_resp.headers.get("access-control-allow-credentials") == "true"

    # Preflight OPTIONS request check
    options_resp = client.options(
        "/health",
        headers={
            "Origin": cors_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert options_resp.status_code == 200
    assert options_resp.headers.get("access-control-allow-origin") == cors_origin


def test_cds_discovery_endpoint():
    """Verify CDS Discovery endpoint returns HTTP 200, valid services array, and prefetch templates."""
    resp = client.get("/cds-services")
    assert resp.status_code == 200
    data = resp.json()
    assert "services" in data
    assert isinstance(data["services"], list)

    service_ids = {s["id"]: s for s in data["services"]}
    assert "patient-view-alert" in service_ids
    assert "order-select-contraindication" in service_ids

    # Validate patient-view-alert service metadata & prefetch
    pv_service = service_ids["patient-view-alert"]
    assert pv_service["hook"] == "patient-view"
    assert "prefetch" in pv_service
    assert "patient" in pv_service["prefetch"]
    assert "conditions" in pv_service["prefetch"]
    assert "medications" in pv_service["prefetch"]

    # Validate order-select-contraindication service metadata & prefetch
    os_service = service_ids["order-select-contraindication"]
    assert os_service["hook"] == "order-select"
    assert "prefetch" in os_service
    assert "conditions" in os_service["prefetch"]


# ==============================================================================
# Tier 2: Synthetic USCDI v5 FHIR EHR Endpoints
# ==============================================================================

def test_fhir_patient_search_exact_and_probabilistic():
    """Query GET /api/fhir/Patient with exact & fuzzy parameters, verify matched patient ID is pat-1."""
    # Exact demographic search
    resp = client.get("/api/fhir/Patient?family=Doe&birthdate=1968-04-12")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resourceType"] == "Bundle"
    assert data["total"] >= 1

    first_patient = data["entry"][0]["resource"]
    matched_id = first_patient["id"]
    # Verify patient matches John Doe (pat-1 / patient-001 canonical)
    assert matched_id in ("pat-1", "patient-001")
    assert any(n.get("family") == "Doe" for n in first_patient.get("name", []))
    assert first_patient.get("birthDate") == "1968-04-12"

    # Probabilistic fuzzy matching (minor typo "Doee" -> matches John Doe with score > 0.6)
    fuzzy_resp = client.get("/api/fhir/Patient?family=Doee")
    assert fuzzy_resp.status_code == 200
    fuzzy_data = fuzzy_resp.json()
    assert fuzzy_data["total"] >= 1
    match_entry = fuzzy_data["entry"][0]
    assert match_entry["search"]["score"] >= 0.6
    assert any(n.get("family") == "Doe" for n in match_entry["resource"].get("name", []))


def test_fhir_patient_everything_bundle():
    """Query GET /api/fhir/Patient/pat-1/$everything and assert full USCDI v5 Bundle."""
    resp = client.get("/api/fhir/Patient/pat-1/$everything")
    assert resp.status_code == 200
    bundle = resp.json()
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "searchset"
    assert bundle["total"] >= 4

    entry_resources = [e["resource"] for e in bundle.get("entry", [])]
    types = {r.get("resourceType") for r in entry_resources}
    assert "Patient" in types
    assert "Condition" in types
    assert "MedicationRequest" in types
    assert "AllergyIntolerance" in types

    # Assert Condition ICD-10 I48.91 (Atrial Fibrillation)
    conditions = [r for r in entry_resources if r.get("resourceType") == "Condition"]
    has_icd10_afib = any(
        any(c.get("code") == "I48.91" for c in cond.get("code", {}).get("coding", []))
        for cond in conditions
    )
    assert has_icd10_afib, "USCDI v5 Bundle must contain Condition with ICD-10 I48.91"

    # Assert MedicationRequest RxNorm 855332 (Warfarin Sodium 5 MG)
    medications = [r for r in entry_resources if r.get("resourceType") == "MedicationRequest"]
    has_rxnorm_warfarin = any(
        any(c.get("code") == "855332" for c in med.get("medicationCodeableConcept", {}).get("coding", []))
        for med in medications
    )
    assert has_rxnorm_warfarin, "USCDI v5 Bundle must contain MedicationRequest with RxNorm 855332"

    # Assert AllergyIntolerance SNOMED 70618001 (Penicillin Allergy)
    allergies = [r for r in entry_resources if r.get("resourceType") == "AllergyIntolerance"]
    has_snomed_penicillin = any(
        any(c.get("code") == "70618001" for c in alg.get("code", {}).get("coding", []))
        for alg in allergies
    )
    assert has_snomed_penicillin, "USCDI v5 Bundle must contain AllergyIntolerance with SNOMED 70618001"


def test_fhir_unmatched_patient():
    """Query GET /api/fhir/Patient?family=Nonexistent and verify graceful empty searchset handling."""
    resp = client.get("/api/fhir/Patient?family=Nonexistent")
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("total", 0) == 0
        assert len(data.get("entry", [])) == 0


# ==============================================================================
# Tier 3: FHIR ConceptMap Semantic Translation Engine
# ==============================================================================

def test_concept_map_individual_translation():
    """Execute POST /api/fhir/ConceptMap/$translate for RxNorm 855332 -> ACTIVE_ANTICOAGULANT."""
    payload = {
        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "code": "855332",
    }
    resp = client.post("/api/fhir/ConceptMap/$translate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] is True
    assert len(data["match"]) >= 1

    first_match = data["match"][0]
    assert first_match["concept"]["code"] == "ACTIVE_ANTICOAGULANT"
    assert first_match["equivalence"] == "equivalent"


def test_concept_map_cardiac_prophylaxis():
    """Execute POST /api/fhir/ConceptMap/$translate for SNOMED 315215002 -> AHA_PROPHYLAXIS_REQUIRED."""
    payload = {
        "system": "http://snomed.info/sct",
        "code": "315215002",
    }
    resp = client.post("/api/fhir/ConceptMap/$translate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] is True
    assert len(data["match"]) >= 1

    first_match = data["match"][0]
    assert first_match["concept"]["code"] == "AHA_PROPHYLAXIS_REQUIRED"


def test_multifactor_risk_synthesis():
    """Execute POST /api/fhir/Patient/pat-1/$evaluate-risks with CDT D7140 (Extraction) -> CRITICAL_HEMORRHAGE_HAZARD."""
    payload = {
        "procedureCode": "D7140",
        "procedureSystem": "http://www.ada.org/cdt",
    }
    resp = client.post("/api/fhir/Patient/pat-1/$evaluate-risks", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["patientId"] in ("pat-1", "patient-001")
    assert data["procedure"]["code"] == "D7140"

    alert_codes = {a["code"] for a in data.get("alerts", [])}
    assert "CRITICAL_HEMORRHAGE_HAZARD" in alert_codes, (
        "Multi-factor risk synthesis must synthesize CRITICAL_HEMORRHAGE_HAZARD for AFib + Warfarin."
    )


# ==============================================================================
# Tier 4: CDS Hooks Clinical Decision Support Engine
# ==============================================================================

def test_order_select_high_bleeding_risk():
    """Send POST /cds-services/order-select-contraindication for pat-1 + D7140 -> Critical card with INR instructions."""
    payload = {
        "hook": "order-select",
        "hookInstance": "os-bleeding-test-01",
        "context": {
            "patientId": "pat-1",
            "selections": ["D7140"],
        },
    }
    resp = client.post("/cds-services/order-select-contraindication", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    cards = data.get("cards", [])
    assert len(cards) >= 1

    bleed_card = next((c for c in cards if "Bleeding" in c["summary"] or "Anticoagulant" in c["summary"]), cards[0])
    assert bleed_card["indicator"] == "critical"
    assert len(bleed_card["summary"]) <= 140
    assert any(term in bleed_card["summary"] for term in ("Warfarin", "Anticoagulant", "Bleeding"))

    # Detail contains clinical instructions regarding INR metrics and hemostatic precautions
    detail = bleed_card["detail"].lower()
    assert "inr" in detail and "2.0-3.0" in detail
    assert any(h in detail for h in ("hemostatic", "tranexamic", "sponge", "local"))

    # Suggestions include actionable interventions (e.g. order INR test or consult)
    assert len(bleed_card.get("suggestions", [])) >= 1
    suggestion_actions = bleed_card["suggestions"][0].get("actions", [])
    assert len(suggestion_actions) >= 1
    assert suggestion_actions[0]["type"] == "create"


def test_order_select_routine_procedure_no_fatigue():
    """Send POST /cds-services/order-select-contraindication for pat-1 + D0120 (Exam) -> Empty cards [] to prevent alert fatigue."""
    payload = {
        "hook": "order-select",
        "hookInstance": "os-routine-test-02",
        "context": {
            "patientId": "pat-1",
            "selections": ["D0120"],
        },
    }
    resp = client.post("/cds-services/order-select-contraindication", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("cards") == [], "Non-invasive routine examination must produce empty cards list [] to avoid alert fatigue."


def test_order_select_prophylaxis_penicillin_allergy():
    """Send POST /cds-services/order-select-contraindication for pat-2 (Jane Smith) + D4341 -> Warns against Amoxicillin, recommends Clindamycin/Azithromycin."""
    payload = {
        "hook": "order-select",
        "hookInstance": "os-proph-pcn-test-03",
        "context": {
            "patientId": "pat-2",
            "selections": ["D4341"],
        },
    }
    resp = client.post("/cds-services/order-select-contraindication", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    cards = data.get("cards", [])
    assert len(cards) >= 1

    proph_card = next((c for c in cards if "Prophylaxis" in c["summary"] or "Valve" in c["summary"]), cards[0])
    assert proph_card["indicator"] in ("critical", "warning")
    assert len(proph_card["summary"]) <= 140

    combined_text = (proph_card["summary"] + " " + proph_card["detail"]).lower()
    # Explicitly warns against Amoxicillin / Penicillin
    assert "amoxicillin" in combined_text or "penicillin" in combined_text
    assert "contraindicated" in combined_text or "avoid" in combined_text or "alert" in combined_text
    # Explicitly recommends non-beta-lactam alternative (Clindamycin or Azithromycin)
    assert "clindamycin" in combined_text or "azithromycin" in combined_text


# ==============================================================================
# Tier 5: CareStack Integration & Bidirectional Writeback
# ==============================================================================

def test_carestack_webhook_patient_sync():
    """Send mock webhook POST /api/carestack/webhook simulating appointment check-in, verify demographic match & cache."""
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
    resp = client.post("/api/carestack/webhook", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "synchronized"
    assert data["carestack_patient_id"] == "CS-2001"
    assert data["matched_ehr_patient_id"] in ("pat-1", "patient-001")
    assert data["cached"] is True
    assert data["alerts_generated"] >= 1

    # Verify cached context is queryable
    cache_resp = client.get("/api/carestack/cache/CS-2001")
    assert cache_resp.status_code == 200
    cached = cache_resp.json()
    assert cached["clinical_summary"]["active_conditions_count"] >= 1
    assert cached["clinical_summary"]["active_medications_count"] >= 1


def test_carestack_medical_alert_writeback():
    """Execute POST /api/carestack/patients/pat-1/medical-alerts and assert alert persists in patient profile."""
    alert_payload = {
        "alert_type": "critical",
        "category": "coagulation",
        "title": "E2E SUITE: Mandatory Hemostatic Protocol for Warfarin Anticoagulation",
        "details": "Pre-operative INR verification required (<3.0 within 48h). Prepare gelatin sponges and 4.8% tranexamic acid rinse.",
        "source": "MDIN Hematology Surveillance Engine",
        "action_required": "Place local hemostatics into extraction socket immediately post-op.",
    }

    # Write alert back using pat-1 identifier
    write_resp = client.post("/api/carestack/patients/pat-1/medical-alerts", json=alert_payload)
    assert write_resp.status_code == 200
    write_data = write_resp.json()
    assert write_data["success"] is True
    assert write_data["alert"]["status"] == "posted_to_chart"

    # Query alerts back and verify persistence
    get_resp = client.get("/api/carestack/patients/pat-1/medical-alerts")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["alert_count"] >= 1
    assert any(a["title"] == alert_payload["title"] for a in get_data["alerts"])
