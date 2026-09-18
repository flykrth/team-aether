"""
Test Suite for MDIN Step 11: Pre-Screening Automated Medical-Clearance Engine (The Digital Clearance Passport).
DSOLVE 2026 - DRISHTI, College of Engineering Trivandrum (CET).

Verifies:
1. Pydantic schemas adhering to HL7 FHIR R4 CommunicationRequest and Task resources:
   - AttendingPhysician (npi, name, specialty, facility_name, fhir_endpoint, direct_email)
   - ClearanceRequestPayload (UUID, demographics, carestack_provider, physician, procedures, justification, requested_actions, status, FHIR resources)
   - ClearanceDecision (request_id, decision, physician_notes, coagulation_parameters, signed_by, timestamp)
2. MedicalClearanceService:
   - In-memory registry cache (CLEARANCE_REGISTRY)
   - create_clearance_passport:
     * Locates cardiologist / attending physician (Dr. Kenneth Vance, MD - Chief of Cardiology, Metropolitan Heart Center)
     * Maps ConceptMap clinical rationale (active Warfarin, Atrial Fibrillation, high bleeding hazard)
     * Generates interoperable FHIR Task (code: medical-clearance-request) linked to FHIR CommunicationRequest
     * Stores status as "TRANSMITTED_TO_INBOX"
   - get_clearance_by_id and get_clearance_by_patient
   - record_physician_decision:
     * Updates status and coagulation parameters
     * Triggers CareStack notification webhook and chart alert
3. REST API Endpoints:
   - POST /api/clearance/dispatch
   - GET /api/clearance/patient/{patient_id}
   - GET /api/clearance/{request_id}
   - POST /api/clearance/{request_id}/decision
   - Webhook reception verification at /api/carestack/patients/{id}/medical-clearance-status
"""

import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.clearance import (
    AttendingPhysician,
    ClearanceDecision,
    ClearanceDecisionType,
    ClearanceDispatchRequest,
    ClearanceRequestPayload,
    ClearanceStatus,
)
from backend.app.services.clearance_engine import (
    MedicalClearanceService,
    CLEARANCE_REGISTRY,
    PHYSICIAN_KENNETH_VANCE,
)
from backend.app.routers.carestack_mock import (
    PATIENT_MEDICAL_CLEARANCE_STATUS,
    PATIENT_MEDICAL_ALERTS,
)

client = TestClient(app)


# ==============================================================================
# Tier 1: Pydantic Schema & FHIR Conformance Unit Tests
# ==============================================================================

class TestClearanceDataModels:
    """Unit tests for Pydantic models conforming to HL7 FHIR R4 resources."""

    def test_attending_physician_schema(self):
        """Verify AttendingPhysician model fields and validations."""
        physician = AttendingPhysician(
            npi="1092837465",
            name="Dr. Kenneth Vance, MD",
            specialty="Cardiology",
            facility_name="Metropolitan Heart Center",
            fhir_endpoint="https://fhir.metroheart.org/r4",
            direct_email="k.vance@metroheart.org",
        )
        assert physician.npi == "1092837465"
        assert physician.name == "Dr. Kenneth Vance, MD"
        assert physician.specialty == "Cardiology"
        assert physician.facility_name == "Metropolitan Heart Center"
        assert physician.fhir_endpoint == "https://fhir.metroheart.org/r4"
        assert physician.direct_email == "k.vance@metroheart.org"

    def test_clearance_decision_schema(self):
        """Verify ClearanceDecision model serialization and coagulation parameters."""
        req_id = str(uuid.uuid4())
        decision = ClearanceDecision(
            request_id=req_id,
            decision="APPROVED_WITH_CONDITIONS",
            physician_notes="Proceed with extraction if INR <= 2.5 on morning of surgery. Apply local hemostatic agents.",
            coagulation_parameters={
                "target_inr_range": "2.0-2.5",
                "hold_medication": False,
                "hold_hours": 0,
            },
            signed_by="Dr. Kenneth Vance, MD",
        )
        assert decision.request_id == req_id
        assert decision.decision == "APPROVED_WITH_CONDITIONS"
        assert decision.coagulation_parameters["target_inr_range"] == "2.0-2.5"
        assert decision.coagulation_parameters["hold_medication"] is False
        assert decision.signed_by == "Dr. Kenneth Vance, MD"
        assert isinstance(decision.timestamp, datetime)

    def test_clearance_request_payload_schema(self):
        """Verify ClearanceRequestPayload structure, defaults, and UUID generation."""
        req_uuid = uuid.uuid4()
        payload = ClearanceRequestPayload(
            request_id=req_uuid,
            patient_id="patient-001",
            patient_demographics={
                "name": "John Doe",
                "dob": "1968-04-12",
                "mrn": "MRN-10001",
            },
            carestack_provider={
                "dentist_name": "Dr. Sarah Jenkins, DDS",
                "npi": "1982736450",
                "practice_name": "CareStack Center for Advanced Dentistry - Surgical Suite",
                "phone": "(555) 019-2830",
            },
            physician=PHYSICIAN_KENNETH_VANCE,
            proposed_procedures=[
                {
                    "cdt_code": "D7140",
                    "description": "Extraction, erupted tooth or exposed root",
                    "scheduled_appointment": "2026-09-22T09:30:00Z",
                }
            ],
            clinical_justification="Patient on active Warfarin with Atrial Fibrillation - high bleeding hazard.",
            status=ClearanceStatus.TRANSMITTED_TO_INBOX.value,
        )
        assert payload.request_id == req_uuid
        assert payload.patient_id == "patient-001"
        assert payload.status == "TRANSMITTED_TO_INBOX"
        assert len(payload.requested_actions) >= 3
        assert "Review coagulation protocol" in payload.requested_actions


# ==============================================================================
# Tier 2: MedicalClearanceService Unit Tests
# ==============================================================================

class TestMedicalClearanceService:
    """Unit tests for the clearance passport engine logic."""

    def setup_method(self):
        self.service = MedicalClearanceService()

    def test_create_clearance_passport_cardiology_warfarin(self):
        """
        Verify that for patient-001 (John Doe, on Warfarin for Atrial Fibrillation):
        - Attending cardiologist Dr. Kenneth Vance, MD is resolved
        - Clinical justification links Warfarin + Atrial Fibrillation to bleeding hazard
        - Interoperable FHIR Task (code: medical-clearance-request) is created
        - Initial status is TRANSMITTED_TO_INBOX
        """
        passport = self.service.create_clearance_passport(
            patient_id="patient-001",
            cdt_code="D7140",
        )

        assert passport is not None
        assert isinstance(passport.request_id, uuid.UUID)
        assert passport.patient_id == "patient-001"
        assert passport.patient_demographics["name"] == "John Doe"
        assert passport.patient_demographics["mrn"] == "MRN-10001"

        # Physician Resolution
        assert passport.physician.name == "Dr. Kenneth Vance, MD"
        assert passport.physician.specialty == "Cardiology"
        assert passport.physician.facility_name == "Metropolitan Heart Center"
        assert passport.physician.npi == "1092837465"

        # ConceptMap Justification Synthesis
        justification = passport.clinical_justification
        assert "Warfarin" in justification
        assert "Atrial Fibrillation" in justification or "I48.91" in justification
        assert "D7140" in justification
        assert "hemorrhage" in justification.lower() or "bleeding" in justification.lower()

        # Status & Requested Actions
        assert passport.status == "TRANSMITTED_TO_INBOX"
        assert "Review coagulation protocol" in passport.requested_actions
        assert "Specify target INR threshold" in passport.requested_actions

        # FHIR Resources
        assert passport.fhir_task is not None
        assert passport.fhir_task["resourceType"] == "Task"
        assert passport.fhir_task["status"] == "requested"
        assert passport.fhir_task["code"]["coding"][0]["code"] == "medical-clearance-request"

        assert passport.fhir_communication_request is not None
        assert passport.fhir_communication_request["resourceType"] == "CommunicationRequest"
        assert passport.fhir_communication_request["status"] == "active"
        assert passport.fhir_task["focus"]["reference"] == f"CommunicationRequest/{passport.fhir_communication_request['id']}"

        # In-Memory Cache Registry
        cached = self.service.get_clearance_by_id(str(passport.request_id))
        assert cached is not None
        assert cached.request_id == passport.request_id

    def test_get_clearance_by_patient_alias(self):
        """Verify clearance lookups work across patient ID aliases (e.g. CS-2001 vs patient-001)."""
        passport = self.service.create_clearance_passport(
            patient_id="CS-2001",
            cdt_code="D7140",
        )

        # Lookup by CareStack ID
        results_cs = self.service.get_clearance_by_patient("CS-2001")
        assert len(results_cs) >= 1
        assert any(r.request_id == passport.request_id for r in results_cs)

        # Lookup by EHR alias patient-001
        results_ehr = self.service.get_clearance_by_patient("patient-001")
        assert len(results_ehr) >= 1
        assert any(r.request_id == passport.request_id for r in results_ehr)

    def test_record_physician_decision_approval_with_conditions(self):
        """
        Verify that recording an APPROVED_WITH_CONDITIONS decision:
        - Updates passport status
        - Updates FHIR Task status to completed
        - Attaches coagulation directives
        - Triggers CareStack mock status and chart alert writeback
        """
        passport = self.service.create_clearance_passport(
            patient_id="patient-001",
            cdt_code="D7140",
        )
        req_id = str(passport.request_id)

        decision = ClearanceDecision(
            request_id=req_id,
            decision="APPROVED_WITH_CONDITIONS",
            physician_notes="Target INR 2.0-2.5 within 24h of surgery. Do not interrupt Warfarin. Use local tranexamic acid gauze.",
            coagulation_parameters={
                "target_inr_range": "2.0-2.5",
                "hold_medication": False,
                "hold_hours": 0,
            },
            signed_by="Dr. Kenneth Vance, MD",
        )

        updated = self.service.record_physician_decision(decision)

        assert updated.status == "APPROVED_WITH_CONDITIONS"
        assert updated.decision.signed_by == "Dr. Kenneth Vance, MD"
        assert updated.fhir_task["status"] == "completed"
        assert updated.conditions_or_notes == decision.physician_notes

        # Verify CareStack mock status cache received notification
        cs_records = PATIENT_MEDICAL_CLEARANCE_STATUS.get("patient-001") or PATIENT_MEDICAL_CLEARANCE_STATUS.get("CS-2001")
        assert cs_records is not None
        assert len(cs_records) >= 1
        latest = cs_records[-1]
        assert latest["status"] == "APPROVED_WITH_CONDITIONS"
        assert latest["physician_name"] == "Dr. Kenneth Vance, MD"
        assert latest["coagulation_parameters"]["target_inr_range"] == "2.0-2.5"

        # Verify CareStack patient chart alert
        alerts = PATIENT_MEDICAL_ALERTS.get("CS-2001") or PATIENT_MEDICAL_ALERTS.get("patient-001")
        assert alerts is not None
        assert any("MEDICAL CLEARANCE" in a["title"] for a in alerts)


# ==============================================================================
# Tier 3: REST API Integration Endpoints
# ==============================================================================

class TestClearanceApiEndpoints:
    """End-to-end integration tests for the clearance router API endpoints."""

    def test_root_discovery_contains_clearance_links(self):
        """Verify root endpoint exposes medical clearance discovery links."""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        endpoints = data.get("endpoints", {})
        assert "clearance_dispatch" in endpoints
        assert "clearance_patient" in endpoints

    def test_post_dispatch_clearance_endpoint(self):
        """
        POST /api/clearance/dispatch
        Creates and returns 201 Created ClearanceRequestPayload.
        """
        payload = {
            "patient_id": "patient-001",
            "cdt_code": "D7140",
        }
        resp = client.post("/api/clearance/dispatch", json=payload)
        assert resp.status_code == 201
        data = resp.json()

        assert "request_id" in data
        assert data["patient_id"] == "patient-001"
        assert data["status"] == "TRANSMITTED_TO_INBOX"
        assert data["physician"]["name"] == "Dr. Kenneth Vance, MD"
        assert data["physician"]["specialty"] == "Cardiology"
        assert len(data["proposed_procedures"]) == 1
        assert data["proposed_procedures"][0]["cdt_code"] == "D7140"
        assert "fhir_task" in data
        assert data["fhir_task"]["status"] == "requested"

    def test_get_patient_clearance_endpoint(self):
        """
        GET /api/clearance/patient/{patient_id}
        Returns list of clearance requests for the given patient.
        """
        # Dispatch first
        disp_resp = client.post(
            "/api/clearance/dispatch",
            json={"patient_id": "patient-001", "cdt_code": "D7210"},
        )
        assert disp_resp.status_code == 201
        created_id = disp_resp.json()["request_id"]

        resp = client.get("/api/clearance/patient/patient-001")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert len(items) >= 1
        assert any(item["request_id"] == created_id for item in items)

    def test_get_clearance_by_id_endpoint(self):
        """
        GET /api/clearance/{request_id}
        Retrieves specific clearance passport for physician view.
        """
        disp_resp = client.post(
            "/api/clearance/dispatch",
            json={"patient_id": "patient-001", "cdt_code": "D7140"},
        )
        created_id = disp_resp.json()["request_id"]

        resp = client.get(f"/api/clearance/{created_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["request_id"] == created_id
        assert data["patient_id"] == "patient-001"

        # Non-existent ID returns 404
        bad_id = str(uuid.uuid4())
        resp_404 = client.get(f"/api/clearance/{bad_id}")
        assert resp_404.status_code == 404

    def test_post_physician_decision_endpoint(self):
        """
        POST /api/clearance/{request_id}/decision
        Accepts ClearanceDecision, records sign-off, and updates CareStack status.
        """
        disp_resp = client.post(
            "/api/clearance/dispatch",
            json={"patient_id": "patient-001", "cdt_code": "D7140"},
        )
        req_id = disp_resp.json()["request_id"]

        decision_payload = {
            "request_id": req_id,
            "decision": "APPROVED",
            "physician_notes": "Cardiac stability confirmed. Normal sinus rhythm maintained. Proceed with procedure under local anesthesia.",
            "coagulation_parameters": {
                "target_inr_range": "2.0-3.0",
                "hold_medication": False,
                "hold_hours": 0,
            },
            "signed_by": "Dr. Kenneth Vance, MD - Chief of Cardiology",
        }

        resp = client.post(f"/api/clearance/{req_id}/decision", json=decision_payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "APPROVED"
        assert data["decision"]["signed_by"] == "Dr. Kenneth Vance, MD - Chief of Cardiology"
        assert data["conditions_or_notes"] == decision_payload["physician_notes"]

        # Verify CareStack Webhook Audit endpoint
        carestack_resp = client.get("/api/carestack/patients/CS-2001/medical-clearance-status")
        assert carestack_resp.status_code == 200
        cs_data = carestack_resp.json()
        assert cs_data["clearance_count"] >= 1
        assert any(
            s["request_id"] == req_id and s["status"] == "APPROVED"
            for s in cs_data["statuses"]
        )
