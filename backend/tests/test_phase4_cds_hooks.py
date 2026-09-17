"""
Test suite for Phase 4 of the Medical-Dental Interoperability Node (MDIN).
Verifies:
1. CDS Hooks Pydantic models (CDSServiceDiscovery, CDSService, CDSRequest, CDSCard, etc.)
   and strict CDS Hooks v1.0/v2.0 constraints (max 140 character summary, indicator enum).
2. GET /cds-services Discovery endpoint with prefetch templates for:
   - patient-view-alert
   - order-select-contraindication
3. POST /cds-services/patient-view-alert:
   - Evaluates patient-view hook upon opening patient chart in CareStack.
   - Highlights systemic health risks (anticoagulation, prosthetic valve, uncontrolled diabetes HbA1c 9.2%).
4. POST /cds-services/order-select-contraindication:
   - High Hemorrhage Check: Bleeding procedure (D7140/D7210/D4341) + Warfarin -> critical card with target INR 2.0-3.0.
   - Antibiotic Prophylaxis Check: Mucosal bleeding + Prosthetic Valve + Penicillin allergy ->
     critical/warning card with Clindamycin 600mg or Azithromycin 500mg PO 1h prior.
   - Low Risk / Clean: Non-invasive procedure (D0120) or healthy patient -> empty cards list [] to prevent alert fatigue.
5. Prefetch payload optimization:
   - Direct prefetch evaluation eliminates round-trip latency.
   - Seamless automated fallback to simulated FHIR EHR store when prefetch is omitted.
"""

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.cds_hooks import (
    CDSServiceDiscovery,
    CDSService,
    CDSRequest,
    CDSSuggestionAction,
    CDSSuggestion,
    CDSLink,
    CDSSource,
    CDSCard,
    CDSResponse,
)

client = TestClient(app)


# --- 1. CDS Hooks Pydantic Models Validation Tests ---

def test_cds_models_instantiation_and_validation():
    """Verify all CDS Hooks models instantiate and serialize according to spec."""
    source = CDSSource(label="MDIN Clinical Safety Node", url="https://carestack.com")
    action = CDSSuggestionAction(
        type="create",
        description="Order STAT INR Blood Test",
        resource={"resourceType": "ServiceRequest", "code": {"text": "INR"}},
    )
    suggestion = CDSSuggestion(
        label="Order Pre-Op INR",
        uuid="sugg-101",
        actions=[action],
        isRecommended=True,
    )
    link = CDSLink(
        label="ADA Guidelines",
        url="https://www.ada.org",
        type="absolute",
    )
    card = CDSCard(
        summary="High Bleeding Hazard: Patient on Anticoagulant (Warfarin)",
        detail="Verify latest INR (target 2.0-3.0 before invasive dental surgery).",
        indicator="critical",
        source=source,
        suggestions=[suggestion],
        links=[link],
    )
    response = CDSResponse(cards=[card])

    assert len(response.cards) == 1
    assert response.cards[0].indicator == "critical"
    assert len(response.cards[0].summary) <= 140
    assert response.cards[0].suggestions[0].actions[0].type == "create"

    # Verify request model
    req = CDSRequest(
        hook="order-select",
        hookInstance="uuid-test-1",
        context={"patientId": "patient-001", "selections": ["D7140"]},
    )
    assert req.hook == "order-select"
    assert req.context["selections"] == ["D7140"]


def test_cds_card_summary_max_length_enforced():
    """Verify CDSCard raises ValidationError when summary exceeds 140 chars per CDS Hooks specification."""
    source = CDSSource(label="Test Source")
    long_summary = "X" * 141

    with pytest.raises(ValidationError):
        CDSCard(
            summary=long_summary,
            indicator="warning",
            source=source,
        )


def test_cds_card_indicator_enum_enforced():
    """Verify CDSCard raises ValidationError when indicator is not in info | warning | critical."""
    source = CDSSource(label="Test Source")

    with pytest.raises(ValidationError):
        CDSCard(
            summary="Valid summary",
            indicator="fatal",  # Invalid indicator
            source=source,
        )


# --- 2. CDS Discovery Endpoint Tests ---

def test_cds_discovery_endpoint():
    """Verify GET /cds-services returns required services and prefetch definitions."""
    res = client.get("/cds-services")
    assert res.status_code == 200
    data = res.json()
    assert "services" in data
    discovery = CDSServiceDiscovery.model_validate(data)

    service_map = {s.id: s for s in discovery.services}
    assert "patient-view-alert" in service_map
    assert "order-select-contraindication" in service_map

    # Check patient-view-alert service metadata
    pv_service = service_map["patient-view-alert"]
    assert pv_service.hook == "patient-view"
    assert pv_service.prefetch is not None
    assert "patient" in pv_service.prefetch
    assert "conditions" in pv_service.prefetch
    assert "medications" in pv_service.prefetch

    # Check order-select-contraindication service metadata
    os_service = service_map["order-select-contraindication"]
    assert os_service.hook == "order-select"
    assert os_service.prefetch is not None
    assert "conditions" in os_service.prefetch


# --- 3. Service 1: Patient-View Hook Evaluation Tests ---

def test_patient_view_john_doe_anticoagulant_alert():
    """patient-001 (John Doe): Active Warfarin therapy triggers systemic bleeding precaution card."""
    payload = {
        "hook": "patient-view",
        "hookInstance": "pv-inst-001",
        "context": {"patientId": "patient-001"},
    }
    res = client.post("/cds-services/patient-view-alert", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    summaries = [c.summary for c in response.cards]
    assert any("Anticoagulant" in s or "Warfarin" in s for s in summaries)
    assert any("Penicillin" in s for s in summaries)


def test_patient_view_jane_smith_cardiac_valve_alert():
    """patient-002 (Jane Smith): Prosthetic cardiac valve triggers AHA antibiotic prophylaxis alert."""
    payload = {
        "hook": "patient-view",
        "hookInstance": "pv-inst-002",
        "context": {"patientId": "patient-002"},
    }
    res = client.post("/cds-services/patient-view-alert", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    summaries = [c.summary for c in response.cards]
    assert any("Prosthetic" in s or "Prophylaxis" in s for s in summaries)
    valve_card = next(c for c in response.cards if "Prosthetic" in c.summary)
    assert valve_card.indicator in ("info", "warning")
    assert len(valve_card.suggestions) >= 1


def test_patient_view_robert_taylor_uncontrolled_diabetes():
    """patient-003 (Robert Taylor): Type 2 Diabetes with HbA1c 9.2% triggers delayed healing warning."""
    payload = {
        "hook": "patient-view",
        "hookInstance": "pv-inst-003",
        "context": {"patientId": "patient-003"},
    }
    res = client.post("/cds-services/patient-view-alert", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    summaries = [c.summary for c in response.cards]
    assert any("Diabetes" in s or "Glycemic" in s or "9.2%" in s for s in summaries)
    dm_card = next(c for c in response.cards if "Diabetes" in c.summary or "Glycemic" in c.summary)
    assert dm_card.indicator == "warning"
    assert "4548-4" in dm_card.detail or "HbA1c" in dm_card.detail
    assert len(dm_card.suggestions) >= 1


def test_patient_view_clean_patient_no_alerts():
    """Non-existent or low-risk patient produces empty cards list [] to prevent alert fatigue."""
    payload = {
        "hook": "patient-view",
        "hookInstance": "pv-inst-clean",
        "context": {"patientId": "healthy-patient-999"},
    }
    res = client.post("/cds-services/patient-view-alert", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())
    assert response.cards == []


# --- 4. Service 2: Order-Select Hook Evaluation Tests ---

def test_order_select_bleeding_procedure_extraction_on_warfarin():
    """
    High Hemorrhage Check:
    CDT D7140 (Simple Extraction) on patient-001 (Warfarin anticoagulant therapy)
    -> Critical card with INR target 2.0-3.0 and order INR suggestion.
    """
    payload = {
        "hook": "order-select",
        "hookInstance": "os-inst-001",
        "context": {
            "patientId": "patient-001",
            "selections": ["D7140"],
        },
    }
    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    assert len(response.cards) >= 1
    bleed_card = next((c for c in response.cards if "Bleeding Hazard" in c.summary), None)
    assert bleed_card is not None
    assert bleed_card.indicator == "critical"
    assert bleed_card.summary == "High Bleeding Hazard: Patient on Anticoagulant (Warfarin)"
    assert len(bleed_card.summary) <= 140
    assert "2.0-3.0" in bleed_card.detail
    assert "hemostatic" in bleed_card.detail.lower()

    # Verify suggestion to order INR lab verification or MD consult
    assert len(bleed_card.suggestions) >= 1
    action = bleed_card.suggestions[0].actions[0]
    assert action.type == "create"
    assert "INR" in action.description


def test_order_select_deep_scaling_on_warfarin():
    """
    High Hemorrhage Check:
    CDT D4341 (Periodontal Scaling) on patient-001 (Warfarin therapy)
    -> Critical high bleeding hazard card.
    """
    payload = {
        "hook": "order-select",
        "hookInstance": "os-inst-002",
        "context": {
            "patientId": "patient-001",
            "selections": ["D4341"],
        },
    }
    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    assert any(c.indicator == "critical" and "Bleeding Hazard" in c.summary for c in response.cards)


def test_order_select_surgical_extraction_on_warfarin():
    """
    High Hemorrhage Check:
    CDT D7210 (Surgical Extraction) on patient-001 (Warfarin therapy)
    -> Critical high bleeding hazard card.
    """
    payload = {
        "hook": "order-select",
        "hookInstance": "os-inst-003",
        "context": {
            "patientId": "patient-001",
            "selections": ["D7210"],
        },
    }
    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    assert any(c.indicator == "critical" and "Bleeding Hazard" in c.summary for c in response.cards)


def test_order_select_prosthetic_valve_non_allergic_prophylaxis():
    """
    Antibiotic Prophylaxis Check (Non-allergic):
    patient-002 has Prosthetic Heart Valve (no penicillin allergy).
    CDT D1110 (Adult Prophylaxis / Cleaning) causes mucosal bleeding.
    -> Returns standard AHA Antibiotic Prophylaxis card.
    """
    payload = {
        "hook": "order-select",
        "hookInstance": "os-inst-004",
        "context": {
            "patientId": "patient-002",
            "selections": ["D1110"],
        },
    }
    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    assert len(response.cards) >= 1
    proph_card = next(c for c in response.cards if "Prophylaxis" in c.summary)
    assert "Amoxicillin" in proph_card.detail or "AHA" in proph_card.detail


def test_order_select_prosthetic_valve_with_penicillin_allergy():
    """
    Antibiotic Prophylaxis Check (Allergic):
    Patient with Prosthetic Cardiac Valve AND Penicillin allergy undergoing mucosal bleeding procedure (D7140).
    -> Critical card specifying:
       'AHA Prophylaxis Alert: Requires Clindamycin 600mg or Azithromycin 500mg PO 1h prior. Penicillin/Amoxicillin contraindicated.'
    """
    # Create request with inline prefetch containing both Prosthetic Valve and Penicillin allergy
    payload = {
        "hook": "order-select",
        "hookInstance": "os-inst-005",
        "context": {
            "patientId": "patient-valve-allergic",
            "selections": ["D7140"],
        },
        "prefetch": {
            "conditions": {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Condition",
                            "id": "cond-valve",
                            "code": {
                                "coding": [
                                    {"system": "http://snomed.info/sct", "code": "315215002", "display": "Prosthetic cardiac valve present"}
                                ]
                            },
                        }
                    }
                ],
            },
            "allergies": {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "AllergyIntolerance",
                            "id": "alg-pcn",
                            "code": {
                                "coding": [
                                    {"system": "http://snomed.info/sct", "code": "70618001", "display": "Allergy to penicillin"}
                                ]
                            },
                        }
                    }
                ],
            },
        },
    }

    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    assert len(response.cards) >= 1
    proph_card = next(c for c in response.cards if "Prophylaxis" in c.summary)
    expected_summary = "AHA Prophylaxis Alert: Requires Clindamycin 600mg or Azithromycin 500mg PO 1h prior. Penicillin/Amoxicillin contraindicated."
    assert proph_card.summary == expected_summary
    assert len(proph_card.summary) <= 140
    assert proph_card.indicator in ("critical", "warning")
    assert "Clindamycin" in proph_card.detail
    assert "contraindicated" in proph_card.detail.lower()

    # Verify suggestion recommends Clindamycin
    assert len(proph_card.suggestions) >= 1
    assert "Clindamycin" in proph_card.suggestions[0].label


def test_order_select_low_risk_procedure_clean_no_cards():
    """
    Low Risk / Clean:
    CDT D0120 (Periodic oral evaluation - exam without bleeding) on patient-001 (Warfarin)
    or healthy patient
    -> Returns empty cards list [] to prevent clinical alert fatigue.
    """
    payload = {
        "hook": "order-select",
        "hookInstance": "os-inst-006",
        "context": {
            "patientId": "patient-001",
            "selections": ["D0120"],
        },
    }
    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    # Examination alone does not involve surgical bleeding; should return empty list
    assert response.cards == []


# --- 5. Prefetch Payload Acceleration & Fallback Tests ---

def test_prefetch_payload_direct_evaluation():
    """Verify endpoint evaluates prefetch directly for custom patients without round-trip EHR lookup."""
    payload = {
        "hook": "order-select",
        "hookInstance": "os-prefetch-001",
        "context": {
            "patientId": "custom-patient-x",
            "selections": ["D7140"],
        },
        "prefetch": {
            "patient": {
                "resourceType": "Patient",
                "id": "custom-patient-x",
            },
            "medications": {
                "resourceType": "Bundle",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "MedicationRequest",
                            "id": "med-warfarin-custom",
                            "status": "active",
                            "medicationCodeableConcept": {
                                "coding": [
                                    {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "855332", "display": "Warfarin Sodium 5 MG"}
                                ]
                            },
                        }
                    }
                ],
            },
        },
    }

    res = client.post("/cds-services/order-select-contraindication", json=payload)
    assert res.status_code == 200
    response = CDSResponse.model_validate(res.json())

    assert len(response.cards) == 1
    assert response.cards[0].summary == "High Bleeding Hazard: Patient on Anticoagulant (Warfarin)"
    assert response.cards[0].indicator == "critical"


def test_service_aliases_and_legacy_endpoints():
    """Verify endpoint aliases (/patient-view-service, /order-select-service, /med-dental-risk-evaluator)."""
    # /patient-view-service alias
    res_pv = client.post(
        "/cds-services/patient-view-service",
        json={"hook": "patient-view", "hookInstance": "alias-1", "context": {"patientId": "patient-001"}},
    )
    assert res_pv.status_code == 200
    assert len(res_pv.json()["cards"]) >= 1

    # /order-select-service alias
    res_os = client.post(
        "/cds-services/order-select-service",
        json={"hook": "order-select", "hookInstance": "alias-2", "context": {"patientId": "patient-001", "selections": ["D7140"]}},
    )
    assert res_os.status_code == 200
    assert len(res_os.json()["cards"]) >= 1

    # Legacy /med-dental-risk-evaluator
    res_legacy = client.post(
        "/cds-services/med-dental-risk-evaluator",
        json={"hook": "patient-view", "hookInstance": "legacy-1", "context": {"patientId": "EHR-88201"}},
    )
    assert res_legacy.status_code == 200
    assert any("MRONJ" in c["summary"] for c in res_legacy.json()["cards"])
