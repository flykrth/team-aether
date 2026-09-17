"""
Tests for MDIN FastAPI application, CORS configuration, and mounted routers.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns system metadata and discovery links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Medical-Dental Interoperability Node" in data["service"]
    assert data["status"] == "online"
    assert "/docs" in data["endpoints"]["docs"]
    assert "/api/carestack/status" in data["endpoints"]["carestack"]
    assert "/api/fhir/metadata" in data["endpoints"]["fhir"]
    assert "/cds-services" in data["endpoints"]["cds_discovery"]


def test_health_check():
    """Verify /health endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://localhost:5173"])
def test_cors_headers_allowed_origins(origin: str):
    """Verify CORS headers allow both frontend ports (3000 & 5173)."""
    response = client.options(
        "/api/carestack/status",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin
    assert "access-control-allow-credentials" in response.headers


def test_carestack_status():
    """Verify CareStack router is mounted at /api/carestack/status."""
    response = client.get("/api/carestack/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "connected"
    assert data["synced_patients"] >= 3


def test_carestack_patients_list():
    """Verify CareStack patients list retrieval."""
    response = client.get("/api/carestack/patients")
    assert response.status_code == 200
    patients = response.json()
    assert len(patients) >= 3
    assert any(p["first_name"] == "Eleanor" for p in patients)


def test_fhir_metadata_capability():
    """Verify FHIR CapabilityStatement at /api/fhir/metadata."""
    response = client.get("/api/fhir/metadata")
    assert response.status_code == 200
    data = response.json()
    assert data["resourceType"] == "CapabilityStatement"
    assert data["fhirVersion"] == "4.0.1"


def test_fhir_patient_and_conditions():
    """Verify FHIR Patient and Condition resources."""
    response = client.get("/api/fhir/Patient")
    assert response.status_code == 200
    patients = response.json()
    assert len(patients) >= 3

    cond_res = client.get("/api/fhir/Condition?patient=EHR-88201")
    assert cond_res.status_code == 200
    conditions = cond_res.json()
    assert len(conditions) >= 1
    assert "Osteoporosis" in conditions[0]["code"]["text"]


def test_cds_services_discovery():
    """Verify CDS Hooks discovery endpoint at /cds-services."""
    response = client.get("/cds-services")
    assert response.status_code == 200
    data = response.json()
    assert "services" in data
    service_ids = [s["id"] for s in data["services"]]
    assert "med-dental-risk-evaluator" in service_ids
    assert "antibiotic-prophylaxis-check" in service_ids


def test_cds_service_evaluation_mronj():
    """Verify CDS risk evaluator detects high-risk bisphosphonate + dental extraction (MRONJ)."""
    payload = {
        "hook": "patient-view",
        "hookInstance": "test-uuid-1",
        "context": {"patientId": "EHR-88201"},
    }
    response = client.post("/cds-services/med-dental-risk-evaluator", json=payload)
    assert response.status_code == 200
    cards = response.json().get("cards", [])
    assert len(cards) >= 1
    # Check that critical MRONJ warning is produced
    assert any(c["indicator"] == "critical" and "MRONJ" in c["summary"] for c in cards)
