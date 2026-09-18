"""
Pydantic data models for MDIN Step 11: Pre-Screening Automated Medical-Clearance Engine (The Digital Clearance Passport).
Adheres to HL7 FHIR R4 CommunicationRequest and Task resources for clinical interoperability between CareStack and Medical EHRs.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


class ClearanceStatus(str, Enum):
    """Lifecycle statuses for a digital medical-clearance passport request."""
    PENDING_DISPATCH = "PENDING_DISPATCH"
    TRANSMITTED_TO_INBOX = "TRANSMITTED_TO_INBOX"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"
    REJECTED = "REJECTED"


class ClearanceDecisionType(str, Enum):
    """Allowed clinical sign-off decisions by attending physician."""
    APPROVED = "APPROVED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"
    REJECTED = "REJECTED"


class AttendingPhysician(BaseModel):
    """
    Attending physician or specialist located from synthetic FHIR record
    responsible for clinical pre-clearance evaluation.
    """
    npi: str = Field(..., description="National Provider Identifier (NPI)")
    name: str = Field(..., description="Full physician name with credentials, e.g. Dr. Kenneth Vance, MD")
    specialty: str = Field("Cardiology", description="Medical specialty (e.g. Cardiology, Internal Medicine)")
    facility_name: str = Field("Metropolitan Heart Center", description="Health system or hospital facility")
    fhir_endpoint: str = Field("https://fhir.metroheart.org/r4", description="Secured FHIR R4 direct endpoint")
    direct_email: str = Field("k.vance@metroheart.org", description="Direct secure clinical messaging address")


class ClearanceDecision(BaseModel):
    """
    Physician clinical decision and sign-off payload for medical clearance.
    """
    request_id: str = Field(..., description="Unique ID of the clearance passport request")
    decision: str = Field(
        ...,
        description="Clearance outcome: APPROVED | APPROVED_WITH_CONDITIONS | REJECTED"
    )
    physician_notes: str = Field(..., description="Clinical instructions and comments by physician")
    coagulation_parameters: Dict[str, Any] = Field(
        default_factory=lambda: {
            "target_inr_range": "2.0-2.5",
            "hold_medication": False,
            "hold_hours": 0,
        },
        description="Specific hemostasis & coagulation directives (e.g. INR target threshold, medication hold instructions)"
    )
    signed_by: str = Field(..., description="Attending physician signature name & credentials")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of physician sign-off"
    )


class FHIRTaskResource(BaseModel):
    """HL7 FHIR R4 Task resource for medical-clearance tracking."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    resourceType: str = "Task"
    id: str
    status: str = "requested"  # requested | in-progress | completed | rejected
    intent: str = "order"
    code: Dict[str, Any] = Field(
        default_factory=lambda: {
            "coding": [
                {
                    "system": "http://hl7.org/fhir/CodeSystem/task-code",
                    "code": "medical-clearance-request",
                    "display": "Pre-Operative Medical Clearance Request",
                }
            ],
            "text": "Pre-Operative Medical Clearance Request",
        }
    )
    description: Optional[str] = None
    focus: Optional[Dict[str, str]] = None
    for_patient: Dict[str, str] = Field(alias="for", description="Reference to Patient resource")
    requester: Dict[str, str] = Field(description="Reference to Practitioner (Dentist)")
    owner: Optional[Dict[str, str]] = Field(None, description="Reference to Practitioner (Physician)")
    authoredOn: str
    lastModified: str


class FHIRCommunicationRequestResource(BaseModel):
    """HL7 FHIR R4 CommunicationRequest resource containing clinical clearance justification."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    resourceType: str = "CommunicationRequest"
    id: str
    status: str = "active"
    subject: Dict[str, str] = Field(description="Reference to Patient resource")
    sender: Dict[str, str] = Field(description="Reference to Practitioner (Dentist)")
    recipient: List[Dict[str, str]] = Field(default_factory=list, description="Reference(s) to Physician")
    payload: List[Dict[str, Any]] = Field(default_factory=list, description="Clinical payload messages")
    reasonCode: List[Dict[str, Any]] = Field(default_factory=list, description="Clinical indications/diagnoses")
    authoredOn: str


class ClearanceRequestPayload(BaseModel):
    """
    The Digital Clearance Passport: Comprehensive request payload bridging
    CareStack dental PMS procedures with medical specialist pre-clearance evaluation.
    """
    model_config = ConfigDict(extra="allow")

    request_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique clearance passport identifier (UUID)"
    )
    patient_id: str = Field(..., description="CareStack or EHR Patient ID")
    patient_demographics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Patient demographic snapshot: Name, DOB, MRN, gender, address"
    )
    carestack_provider: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dentist & dental clinic snapshot: Dentist Name, NPI, Practice Name, Phone"
    )
    physician: AttendingPhysician = Field(..., description="Attending specialist to evaluate clearance")
    proposed_procedures: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Proposed dental procedures (e.g. CDT D7140 extraction, appointment timestamp, tooth)"
    )
    clinical_justification: str = Field(
        ...,
        description="Clinical rationale synthesized from ConceptMap risk engine (e.g. active Warfarin, Atrial Fibrillation, bleeding hazard)"
    )
    requested_actions: List[str] = Field(
        default_factory=lambda: [
            "Review coagulation protocol",
            "Specify target INR threshold",
            "Authorize temporary cessation of anticoagulant if applicable",
            "Confirm safe pre-procedural hemodynamic tolerance",
        ],
        description="Actionable clinical requirements for attending physician"
    )
    status: str = Field(
        default=ClearanceStatus.TRANSMITTED_TO_INBOX.value,
        description="Clearance status enum (PENDING_DISPATCH, TRANSMITTED_TO_INBOX, UNDER_REVIEW, APPROVED, APPROVED_WITH_CONDITIONS, REJECTED)"
    )
    conditions_or_notes: Optional[str] = Field(
        None,
        description="Optional conditional restrictions, hold directives, or physician notes"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp"
    )
    decision: Optional[ClearanceDecision] = Field(
        None,
        description="Recorded physician decision once signed"
    )
    fhir_task: Optional[Dict[str, Any]] = Field(
        None,
        description="HL7 FHIR R4 Task resource with code medical-clearance-request"
    )
    fhir_communication_request: Optional[Dict[str, Any]] = Field(
        None,
        description="HL7 FHIR R4 CommunicationRequest resource linked to the task"
    )


class ClearanceDispatchRequest(BaseModel):
    """API payload to initiate automated clearance passport dispatch."""
    patient_id: str = Field(..., description="Target patient identifier (e.g. patient-001, CS-2001)")
    cdt_code: str = Field("D7140", description="CDT Dental procedure code requiring clearance (e.g. D7140, D7210)")
    carestack_data: Optional[Dict[str, Any]] = Field(None, description="Optional custom CareStack context override")
    ehr_data: Optional[Dict[str, Any]] = Field(None, description="Optional custom FHIR EHR context override")
