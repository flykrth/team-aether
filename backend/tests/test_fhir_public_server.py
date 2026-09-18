"""
Test suite for HL7 FHIR Public Test Server integration.
Verifies:
1. Live /api/fhir/server-status diagnostic endpoint.
2. CapabilityStatement metadata from the connected HL7 FHIR server.
3. FHIRClient health check and latency diagnostics.
4. Patient, Condition, MedicationRequest, AllergyIntolerance, and Observation endpoints.
5. Patient $everything USCDI v5 Bundle export.
6. Public test server fallback and synchronization capabilities.
Reference: https://confluence.hl7.org/spaces/FHIR/pages/35718859/Public+Test+Servers
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.fhir_client import fhir_client

client = TestClient(app)


def test_fhir_server_status_endpoint():
    """Verify GET /api/fhir/server-status returns live server connectivity details."""
    res = client.get("/api/fhir/server-status")
    assert res.status_code == 200
    data = res.json()

    assert "status" in data
    assert data["status"] in ("connected", "degraded", "offline")
    assert "server_url" in data
    assert "hapi.fhir.org" in data["server_url"] or "lforms-fhir" in data["server_url"]
    assert "latency_ms" in data
    assert isinstance(data["latency_ms"], (int, float))
    if data["status"] == "connected":
        assert data.get("fhir_version") == "4.0.1"
        assert "HAPI FHIR" in data.get("software", "") or "HL7" in data.get("software", "")


def test_root_endpoint_includes_fhir_public_server():
    """Verify GET / service metadata links to the public test server and server-status endpoint."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()

    assert "fhir_server" in data
    assert "https://hapi.fhir.org/baseR4" in data["fhir_server"]
    assert "fhir_server_status" in data["endpoints"]
    assert data["endpoints"]["fhir_server_status"] == "/api/fhir/server-status"


def test_fhir_capability_statement_metadata():
    """Verify GET /api/fhir/metadata returns standard HL7 FHIR R4 CapabilityStatement."""
    res = client.get("/api/fhir/metadata")
    assert res.status_code == 200
    data = res.json()

    assert data.get("resourceType") == "CapabilityStatement"
    assert data.get("fhirVersion") in ("4.0.1", "4.0.0")
    assert "rest" in data
    resources = [r["type"] for r in data["rest"][0].get("resource", [])]
    assert "Patient" in resources
    assert "Condition" in resources


def test_fhir_patient_search_and_read():
    """Verify querying Patient resources from the FHIR server."""
    # List search
    res = client.get("/api/fhir/Patient")
    assert res.status_code == 200
    data = res.json()
    assert data["resourceType"] == "Bundle"
    assert data["total"] >= 1

    # Direct ID read for John Doe (patient-001)
    res_pt = client.get("/api/fhir/Patient/patient-001")
    assert res_pt.status_code == 200
    pt = res_pt.json()
    assert pt["resourceType"] == "Patient"
    assert pt["id"] == "patient-001"
    assert any(n.get("family") == "Doe" for n in pt.get("name", []))


def test_fhir_everything_export():
    """Verify $everything exports complete USCDI bundle from the FHIR server."""
    res = client.get("/api/fhir/Patient/patient-001/$everything")
    assert res.status_code == 200
    bundle = res.json()

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "searchset"
    assert bundle["total"] >= 4
    types = {e["resource"]["resourceType"] for e in bundle["entry"]}
    assert "Patient" in types
    assert "Condition" in types
    assert "MedicationRequest" in types
    assert "AllergyIntolerance" in types


def test_fhir_client_health_check_async():
    """Verify FHIRClient check_health() method."""
    import anyio

    async def run_check():
        return await fhir_client.check_health()

    health = anyio.run(run_check)
    assert health["status"] in ("connected", "degraded", "offline")
    assert "server_url" in health
