"""
Test Suite for Step 12: External Physician Clearance Review Portal and Real-Time CareStack Callback.
DSOLVE 2026 - DRISHTI, College of Engineering Trivandrum (CET).

Verifies:
1. CareStack Webhook Callback Endpoint:
   - POST /api/carestack/patients/{patient_id}/medical-clearance-status
   - Accepts payload conforming to Step 12 specification.
   - Updates patient's record under `medical_clearance` in CareStack in-memory store:
     * Sets status to the decision
     * Appends clinical alert: "Cardiology Clearance Received: Target INR 2.0-2.5. Approved by Dr. Vance."
     * Sets is_cleared_for_surgery to True (when approved / approved with conditions).
   - Returns HTTP 200 with { "status": "acknowledged", "updated_patient_id": patient_id }.
2. End-to-end asynchronous flow:
   - Dispatch clearance request via POST /api/clearance/dispatch.
   - Physician decision submitted via POST /api/clearance/{request_id}/decision.
   - Verification of patient.medical_clearance and alert state in CareStack PMS.
"""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers.carestack_mock import (
    MOCK_PATIENTS,
    PATIENT_MEDICAL_CLEARANCE_STATUS,
    PATIENT_MEDICAL_ALERTS,
    _find_carestack_patient,
)

client = TestClient(app)


class TestStep12CareStackCallback:
    """Test CareStack PMS medical-clearance-status callback and in-memory persistence."""

    def test_carestack_clearance_status_callback_success(self):
        """
        POST /api/carestack/patients/{patient_id}/medical-clearance-status
        Verifies:
        - Payload acceptance
        - Updates patient.medical_clearance (status, is_cleared_for_surgery=True)
        - Appends clinical alert containing 'Cardiology Clearance Received: Target INR 2.0-2.5. Approved by Dr. Vance.'
        - Returns { 'status': 'acknowledged', 'updated_patient_id': 'CS-2001' }
        """
        patient_id = "CS-2001"
        payload = {
            "request_id": str(uuid.uuid4()),
            "decision": "APPROVED_WITH_CONDITIONS",
            "physician_notes": "Maintain Warfarin dosage. Verify INR on surgery day (target 2.0-2.5). Apply local Gelfoam and suture firmly.",
            "coagulation_parameters": {
                "target_inr_range": "2.0-2.5",
                "hold_medication": False,
                "hold_hours": 0,
            },
            "signed_by": "Dr. Kenneth Vance, MD (Cardiology)",
            "timestamp": "2026-09-18T10:20:34+05:30",
        }

        resp = client.post(
            f"/api/carestack/patients/{patient_id}/medical-clearance-status",
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"
        assert data["updated_patient_id"] == patient_id

        # Verify patient record in CareStack in-memory store
        patient = _find_carestack_patient(patient_id)
        assert patient is not None
        assert hasattr(patient, "medical_clearance")
        assert patient.medical_clearance is not None
        assert patient.medical_clearance["status"] == "APPROVED_WITH_CONDITIONS"
        assert patient.medical_clearance["is_cleared_for_surgery"] is True
        assert patient.medical_clearance["signed_by"] == "Dr. Kenneth Vance, MD (Cardiology)"
        assert patient.medical_clearance["coagulation_parameters"]["target_inr_range"] == "2.0-2.5"

        # Verify clinical alert appended to patient's chart
        alerts = PATIENT_MEDICAL_ALERTS.get(patient.id) or PATIENT_MEDICAL_ALERTS.get(patient_id)
        assert alerts is not None
        assert any("Cardiology Clearance Received: Target INR 2.0-2.5. Approved by Dr. Vance." in a["title"] for a in alerts)

    def test_carestack_clearance_status_rejection(self):
        """
        POST /api/carestack/patients/{patient_id}/medical-clearance-status
        Verifies rejection sets is_cleared_for_surgery to False.
        """
        patient_id = "CS-2001"
        payload = {
            "request_id": str(uuid.uuid4()),
            "decision": "REJECTED",
            "physician_notes": "Severe hemodynamic instability. Reschedule oral surgery following cardiology stabilization.",
            "coagulation_parameters": {
                "target_inr_range": "N/A",
                "hold_medication": False,
                "hold_hours": 0,
            },
            "signed_by": "Dr. Kenneth Vance, MD (Cardiology)",
            "timestamp": "2026-09-18T10:20:34+05:30",
        }

        resp = client.post(
            f"/api/carestack/patients/{patient_id}/medical-clearance-status",
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "acknowledged"

        patient = _find_carestack_patient(patient_id)
        assert patient.medical_clearance["status"] == "REJECTED"
        assert patient.medical_clearance["is_cleared_for_surgery"] is False

    def test_e2e_clearance_portal_dispatch_and_decision_callback(self):
        """
        End-to-end integration:
        1. Dispatch clearance passport via POST /api/clearance/dispatch.
        2. Submit physician decision via POST /api/clearance/{request_id}/decision.
        3. Verify real-time CareStack callback persistence.
        """
        # 1. Dispatch
        disp_resp = client.post(
            "/api/clearance/dispatch",
            json={"patient_id": "CS-2001", "cdt_code": "D7140"},
        )
        assert disp_resp.status_code == 201
        req_id = disp_resp.json()["request_id"]

        # 2. Decision by Dr. Kenneth Vance
        decision_payload = {
            "request_id": req_id,
            "decision": "APPROVED",
            "physician_notes": "Normal sinus rhythm. Verified stable INR 2.3. Cleared for surgical extraction.",
            "coagulation_parameters": {
                "target_inr_range": "2.0-2.5",
                "hold_medication": False,
                "hold_hours": 0,
            },
            "signed_by": "Dr. Kenneth Vance, MD (Cardiology)",
        }

        decision_resp = client.post(
            f"/api/clearance/{req_id}/decision",
            json=decision_payload,
        )
        assert decision_resp.status_code == 200
        passport = decision_resp.json()
        assert passport["status"] == "APPROVED"

        # 3. Verify CareStack in-memory patient has medical_clearance
        patient = _find_carestack_patient("CS-2001")
        assert patient.medical_clearance is not None
        assert patient.medical_clearance["is_cleared_for_surgery"] is True
        assert patient.medical_clearance["status"] == "APPROVED"
