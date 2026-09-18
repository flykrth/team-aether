"""
Shared agent state schema for MDIN Step 14: CareStack Multi-Agent Orchestrator (MAO).

`MAOState` is the LangGraph channel schema handed between the Intake, Risk, Clearance and
Clearance agent nodes. `MAOStateModel` is the Pydantic mirror used to validate a
state dictionary at the boundaries (initialization and API serialization).
"""

import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field

AppointmentStatus = Literal["SCHEDULED", "REQUIRES_ACTION", "CLEARED_FOR_CARE"]
IntakeStatus = Literal["PENDING", "PORTAL_LINKED", "CONVERSATIONAL_EXTRACTED"]
HazardLevel = Literal["LOW", "MODERATE", "CRITICAL"]
ClearanceState = Literal[
    "NOT_REQUIRED",
    "REQUIRED_PENDING",
    "TRANSMITTED_TO_EHR",
    "APPROVED_WITH_CONDITIONS",
    "CLEARED",
]


# ---------------------------------------------------------------------------
# Pydantic validation models
# ---------------------------------------------------------------------------

class AppointmentState(BaseModel):
    timestamp: str = ""
    operatory: str = ""
    cdt_codes: List[str] = Field(default_factory=list)
    status: AppointmentStatus = "SCHEDULED"


class MedicalRecordsState(BaseModel):
    model_config = ConfigDict(extra="allow")

    # Coded concepts ({type, system, code, display, source, onset}) backing the display strings below
    normalized_concepts: List[Dict[str, Any]] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    raw_fhir_bundle: Dict[str, Any] = Field(default_factory=dict)


class RiskEvaluation(BaseModel):
    model_config = ConfigDict(extra="allow")

    hazard_level: HazardLevel = "LOW"
    contraindications: List[str] = Field(default_factory=list)
    clinical_recommendations: List[str] = Field(default_factory=list)


class AssignedMedicalMD(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = ""
    npi: str = ""
    facility: str = ""
    specialty: str = ""
    direct_endpoint: str = ""


class ClearanceProtocol(BaseModel):
    model_config = ConfigDict(extra="allow")

    restrictions: List[str] = Field(default_factory=list)
    hold_medications: bool = False
    inr_target: str = ""
    signed_by: str = ""


class AgentLogEntry(BaseModel):
    timestamp: str
    agent_name: str
    action: str
    details: str = ""
    icon: str = ""


class MAOStateModel(BaseModel):
    """Validated form of the shared MAO state."""

    patient_id: str
    patient_name: str = ""
    dob: str = ""
    appointment: AppointmentState = Field(default_factory=AppointmentState)
    medical_records: MedicalRecordsState = Field(default_factory=MedicalRecordsState)
    intake_status: IntakeStatus = "PENDING"
    risk_evaluations: List[RiskEvaluation] = Field(default_factory=list)
    clearance_status: ClearanceState = "NOT_REQUIRED"
    assigned_medical_md: AssignedMedicalMD = Field(default_factory=AssignedMedicalMD)
    clearance_protocol: ClearanceProtocol = Field(default_factory=ClearanceProtocol)
    agent_logs: List[AgentLogEntry] = Field(default_factory=list)
    # Optional demo inputs: intake_narrative, hours_since_dispatch, physician_response
    simulation: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# LangGraph state schema
# ---------------------------------------------------------------------------

class MAOState(TypedDict, total=False):
    """
    Shared state passed between agent nodes. Nodes return partial updates.
    `risk_evaluations` and `agent_logs` are append-only channels (operator.add reducer),
    so nodes return only their *new* entries and parallel branches merge safely.
    """

    patient_id: str
    patient_name: str
    dob: str
    appointment: Dict[str, Any]
    medical_records: Dict[str, Any]
    intake_status: str
    risk_evaluations: Annotated[List[Dict[str, Any]], operator.add]
    clearance_status: str
    assigned_medical_md: Dict[str, Any]
    clearance_protocol: Dict[str, Any]
    agent_logs: Annotated[List[Dict[str, Any]], operator.add]
    simulation: Dict[str, Any]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_agent_log(agent_name: str, action: str, details: str = "", icon: str = "") -> Dict[str, Any]:
    """Builds a validated agent log entry for the `agent_logs` channel."""
    return AgentLogEntry(
        timestamp=utc_now_iso(),
        agent_name=agent_name,
        action=action,
        details=details,
        icon=icon,
    ).model_dump()


def create_initial_state(
    patient_id: str,
    patient_name: str = "",
    dob: str = "",
    cdt_codes: Optional[List[str]] = None,
    appointment_timestamp: Optional[str] = None,
    operatory: str = "",
    simulation: Optional[Dict[str, Any]] = None,
) -> MAOState:
    """Builds a fully-populated, validated MAOState dictionary for a new supervisor thread."""
    model = MAOStateModel(
        patient_id=patient_id,
        patient_name=patient_name,
        dob=dob,
        appointment=AppointmentState(
            timestamp=appointment_timestamp or utc_now_iso(),
            operatory=operatory,
            cdt_codes=[c.upper().strip() for c in (cdt_codes or [])],
        ),
        simulation={k: v for k, v in (simulation or {}).items() if v is not None},
    )
    return MAOState(**model.model_dump())


def validate_state(state: Dict[str, Any]) -> MAOStateModel:
    """Validates an arbitrary state dictionary against the MAO schema. Raises ValidationError."""
    return MAOStateModel.model_validate(state)
