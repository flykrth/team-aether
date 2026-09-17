"""
CareStack Dental Practice Management schemas.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class DentalProcedure(BaseModel):
    code: str = Field(..., description="CDT procedure code, e.g. D7140, D4341")
    description: str = Field(..., description="Procedure name or description")
    tooth_number: Optional[str] = Field(None, description="Tooth number (Universal 1-32)")
    surface: Optional[str] = Field(None, description="Tooth surface (MODBL)")
    status: str = Field("proposed", description="proposed, scheduled, completed")
    cost: Optional[float] = None


class PerioPocket(BaseModel):
    tooth_number: str
    depth_mm: int
    bleeding_on_probing: bool = False


class CareStackPatient(BaseModel):
    id: str = Field(..., description="CareStack internal patient identifier")
    mrn: str = Field(..., description="Medical Record Number")
    first_name: str
    last_name: str
    birth_date: str
    gender: str
    email: Optional[str] = None
    phone: Optional[str] = None
    last_visit: Optional[str] = None
    next_appointment: Optional[str] = None
    primary_dentist: Optional[str] = None
    active_treatment_plan: List[DentalProcedure] = Field(default_factory=list)


class CareStackSyncRequest(BaseModel):
    patient_id: str
    target_ehr_id: Optional[str] = None
    sync_direction: str = Field("bidirectional", description="bidirectional, pull_ehr, push_carestack")


class SyncStatusResponse(BaseModel):
    status: str
    message: str
    synced_patients: int
    last_sync_timestamp: str
    carestack_connection: str
    ehr_connection: str
