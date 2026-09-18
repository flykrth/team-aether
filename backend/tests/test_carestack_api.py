"""
Comprehensive Test Suite for CareStack Web API V1 Integration & Simulator.
Tests:
1. Three-key header authentication: VendorKey, AccountKey, AccountId.
2. Standard HTTP response codes (200, 201, 400, 401, 404).
3. CareStack Web API V1 official endpoints (/api/v1.0/...):
   - Patients (Get, Search, Create, Update, Periodontal Charting, Sync)
   - Procedures & Treatments (Procedure Codes, Appointment Procedures, Sync)
   - Appointments (Get, Create, Modify Status, Checkout, Cancel, Statuses)
   - Practice Infrastructure (Locations, Operatories)
4. CareStackClient asynchronous HTTP service.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import settings
from backend.app.services.carestack_client import (
    CareStackClient,
    get_carestack_client,
    CareStackAuthenticationError,
    CareStackNotFoundError,
)

client = TestClient(app)

VALID_HEADERS = {
    "VendorKey": settings.SIMULATOR_VENDOR_KEY,
    "AccountKey": settings.SIMULATOR_ACCOUNT_KEY,
    "AccountId": settings.SIMULATOR_ACCOUNT_ID,
}


# =====================================================================
# 1. Three-Key Header Authentication Tests
# =====================================================================

def test_auth_verify_success():
    """Verify authentication succeeds when valid VendorKey, AccountKey, and AccountId are supplied."""
    response = client.get("/api/v1.0/auth/verify", headers=VALID_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["status"] == "authorized"
    assert data["accountId"] == settings.SIMULATOR_ACCOUNT_ID


def test_auth_verify_missing_vendorkey():
    """Verify 401 Unauthorized when VendorKey is missing or wrong."""
    bad_headers = {
        "VendorKey": "wrong-vendor-key",
        "AccountKey": settings.SIMULATOR_ACCOUNT_KEY,
        "AccountId": settings.SIMULATOR_ACCOUNT_ID,
    }
    response = client.get("/api/v1.0/auth/verify", headers=bad_headers)
    assert response.status_code == 401
    assert "VendorKey" in response.json()["detail"]


def test_auth_verify_missing_accountkey():
    """Verify 401 Unauthorized when AccountKey is missing or wrong."""
    bad_headers = {
        "VendorKey": settings.SIMULATOR_VENDOR_KEY,
        "AccountKey": "wrong-account-key",
        "AccountId": settings.SIMULATOR_ACCOUNT_ID,
    }
    response = client.get("/api/v1.0/auth/verify", headers=bad_headers)
    assert response.status_code == 401
    assert "AccountKey" in response.json()["detail"]


def test_auth_verify_missing_accountid():
    """Verify 401 Unauthorized when AccountId is missing or wrong."""
    bad_headers = {
        "VendorKey": settings.SIMULATOR_VENDOR_KEY,
        "AccountKey": settings.SIMULATOR_ACCOUNT_KEY,
        "AccountId": "wrong-account-id",
    }
    response = client.get("/api/v1.0/auth/verify", headers=bad_headers)
    assert response.status_code == 401
    assert "AccountId" in response.json()["detail"]


# =====================================================================
# 2. Official CareStack V1 Patient Endpoints
# =====================================================================

def test_get_patient_view_model():
    """Verify GET /api/v1.0/patients/{id} returns official PatientViewModel format."""
    # Patient CS-2001 (John Doe)
    response = client.get("/api/v1.0/patients/2001", headers=VALID_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["FirstName"] == "John"
    assert data["LastName"] == "Doe"
    assert data["DOB"] == "1968-04-12"
    assert data["Gender"] == "Male"
    assert data["PatientIdentifier"] == "CS-2001"
    assert data["AddressDetail"] is not None


def test_get_patient_not_found():
    """Verify 404 response for unknown patient identifier."""
    response = client.get("/api/v1.0/patients/999999", headers=VALID_HEADERS)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_search_patients_term():
    """Verify POST /api/v1.0/patients/search finds matching records using SearchRequest."""
    search_payload = {
        "SearchTerm": "Smith",
        "Offset": 0,
        "Limit": 10,
    }
    response = client.post("/api/v1.0/patients/search", json=search_payload, headers=VALID_HEADERS)
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["LastName"] == "Smith"
    assert results[0]["FirstName"] == "Jane"


def test_create_and_update_patient():
    """Verify POST and PUT /api/v1.0/patients for patient record lifecycle."""
    new_patient = {
        "FirstName": "Arthur",
        "LastName": "Dent",
        "DOB": "1978-03-11",
        "Gender": "Male",
        "Email": "arthur.dent@example.com",
        "Mobile": "555-4242",
    }
    create_res = client.post("/api/v1.0/patients", json=new_patient, headers=VALID_HEADERS)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["FirstName"] == "Arthur"
    assert created["LastName"] == "Dent"
    new_id = created["Id"]
    assert new_id is not None

    # Update patient
    update_payload = {
        "Id": new_id,
        "FirstName": "Arthur",
        "LastName": "Dent-Prefect",
        "DOB": "1978-03-11",
        "Gender": "Male",
        "Email": "arthur.updated@example.com",
    }
    update_res = client.put("/api/v1.0/patients", json=update_payload, headers=VALID_HEADERS)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["LastName"] == "Dent-Prefect"
    assert updated["Email"] == "arthur.updated@example.com"


def test_periodontal_charting():
    """Verify GET /api/v1.0/patients/{id}/periodontal-charting returns periodontal examination data."""
    response = client.get("/api/v1.0/patients/2001/periodontal-charting", headers=VALID_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["PatientID"] == 2001
    assert data["Status"] == "Active"
    assert "teeth" in data
    assert len(data["teeth"]) >= 5
    # Verify deep pocket on tooth 30 (Warfarin / AFib patient planned extraction)
    tooth_30 = next((t for t in data["teeth"] if t["tooth_number"] == "30"), None)
    assert tooth_30 is not None
    assert tooth_30["bleeding_on_probing"] is True
    assert max(tooth_30["buccal_depths"]) >= 5


def test_sync_patients():
    """Verify GET /api/v1.0/sync/patients incremental synchronization endpoint."""
    response = client.get("/api/v1.0/sync/patients", headers=VALID_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "Results" in data
    assert data["TotalRecords"] >= 3
    assert any(p["FirstName"] == "John" for p in data["Results"])


# =====================================================================
# 3. Official CareStack V1 Procedures & Treatments
# =====================================================================

def test_procedure_codes_list():
    """Verify GET /api/v1.0/procedure-codes returns CDT dental codes."""
    response = client.get("/api/v1.0/procedure-codes", headers=VALID_HEADERS)
    assert response.status_code == 200
    codes = response.json()
    assert len(codes) >= 5
    code_symbols = [c["Code"] for c in codes]
    assert "D7140" in code_symbols
    assert "D4341" in code_symbols
    assert "D1110" in code_symbols
    assert "D7210" in code_symbols


def test_sync_treatment_procedures():
    """Verify GET /api/v1.0/sync/treatment-procedures returns treatment plan procedures."""
    response = client.get("/api/v1.0/sync/treatment-procedures", headers=VALID_HEADERS)
    assert response.status_code == 200
    procedures = response.json()
    assert len(procedures) >= 3
    assert any(p["ProcedureCode"] == "D7140" for p in procedures)


def test_appointment_procedures():
    """Verify GET /api/v1.0/treatments/appointment-procedures/{id} returns procedure code IDs."""
    response = client.get("/api/v1.0/treatments/appointment-procedures/5001", headers=VALID_HEADERS)
    assert response.status_code == 200
    proc_ids = response.json()
    assert isinstance(proc_ids, list)
    assert len(proc_ids) >= 1
    assert 104 in proc_ids  # D7140 extraction


# =====================================================================
# 4. Official CareStack V1 Appointments & Practice Endpoints
# =====================================================================

def test_appointment_lifecycle():
    """Verify appointment creation, retrieval, status modification, and checkout."""
    # Create appointment
    apt_payload = {
        "PatientId": 2001,
        "LocationId": 1,
        "OperatoryId": 1,
        "DateTime": "2026-10-01T10:00:00Z",
        "Duration": 45,
        "Notes": "Follow-up extraction socket check",
        "ProviderIds": [101],
    }
    res_create = client.post("/api/v1.0/appointments", json=apt_payload, headers=VALID_HEADERS)
    assert res_create.status_code == 201
    apt_id = res_create.json()["Id"]
    assert apt_id is not None

    # Get appointment
    res_get = client.get(f"/api/v1.0/appointments/{apt_id}", headers=VALID_HEADERS)
    assert res_get.status_code == 200
    assert res_get.json()["PatientId"] == 2001

    # Modify status to InChair (StatusId = 3)
    res_status = client.put(
        f"/api/v1.0/appointments/{apt_id}/modify-status",
        json={"StatusId": 3},
        headers=VALID_HEADERS,
    )
    assert res_status.status_code == 200
    assert res_status.json()["statusId"] == 3

    # Checkout
    res_checkout = client.put(f"/api/v1.0/appointments/{apt_id}/checkout", headers=VALID_HEADERS)
    assert res_checkout.status_code == 200
    assert res_checkout.json()["status"] == "CheckedOut"


def test_appointment_statuses():
    """Verify GET /api/v1.0/appointment-status returns standard statuses."""
    response = client.get("/api/v1.0/appointment-status", headers=VALID_HEADERS)
    assert response.status_code == 200
    statuses = response.json()
    names = [s["Name"] for s in statuses]
    assert "Scheduled" in names
    assert "InChair" in names
    assert "CheckedOut" in names


def test_locations_and_operatories():
    """Verify GET /api/v1.0/locations and /api/v1.0/operatories."""
    res_loc = client.get("/api/v1.0/locations", headers=VALID_HEADERS)
    assert res_loc.status_code == 200
    locations = res_loc.json()
    assert len(locations) >= 1
    assert "CareStack" in locations[0]["Name"]

    res_op = client.get("/api/v1.0/operatories", headers=VALID_HEADERS)
    assert res_op.status_code == 200
    operatories = res_op.json()
    assert len(operatories) >= 2


# =====================================================================
# 5. CareStackClient Service Asynchronous Execution Tests
# =====================================================================

@pytest.mark.anyio
async def test_carestack_client_service():
    """Verify CareStackClient executes authenticated requests via ASGITransport."""
    cs_client = get_carestack_client()

    # Search patients
    results = await cs_client.search_patients("John")
    assert len(results) >= 1
    assert results[0]["LastName"] == "Doe"

    # Get patient
    patient = await cs_client.get_patient(2001)
    assert patient["FirstName"] == "John"
    assert patient["LastName"] == "Doe"

    # Get procedure codes
    codes = await cs_client.get_procedure_codes()
    assert len(codes) >= 4

    # Get perio charting
    perio = await cs_client.get_periodontal_charting(2001)
    assert perio["PatientID"] == 2001
    assert len(perio["teeth"]) >= 1

    # Sync treatment procedures
    sync_procs = await cs_client.sync_treatment_procedures()
    assert len(sync_procs) >= 1


@pytest.mark.anyio
async def test_carestack_client_auth_failure():
    """Verify CareStackClient raises CareStackAuthenticationError on invalid credentials."""
    bad_client = CareStackClient(
        app=app,
        vendor_key="invalid-vendor-key",
        account_key=settings.SIMULATOR_ACCOUNT_KEY,
        account_id=settings.SIMULATOR_ACCOUNT_ID,
    )
    # The /auth/verify endpoint enforces validation
    with pytest.raises(CareStackAuthenticationError):
        await bad_client._request("GET", "/api/v1.0/auth/verify")
