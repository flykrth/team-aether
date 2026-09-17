"""
CareStack Dental Practice Management System (PMS) Web API V1 Schemas.
Conforms to the official CareStack Web API V1 OpenAPI 3.0 specification
from developer.carestack.com.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field


# =====================================================================
# Official CareStack Web API V1 Models
# =====================================================================

class OptionalAddressDetailModel(BaseModel):
    """CareStack patient address structure."""
    Line1: Optional[str] = None
    Line2: Optional[str] = None
    City: Optional[str] = None
    State: Optional[str] = None
    Zip: Optional[str] = None
    Country: Optional[str] = "United States"


class PatientViewModel(BaseModel):
    """
    Official CareStack PatientViewModel returned by GET /api/v1.0/patients/{id}
    and expected by POST/PUT /api/v1.0/patients.
    """
    Id: Optional[int] = Field(None, description="Internal integer ID in CareStack")
    PatientIdentifier: Optional[str] = Field(None, description="External/Chart Patient Identifier e.g. CS-2001 or MRN-10001")
    Prefix: Optional[str] = "NotSet"
    FirstName: str = Field(..., description="Given name")
    MiddleName: Optional[str] = None
    LastName: str = Field(..., description="Family name")
    Suffix: Optional[str] = None
    DOB: str = Field(..., description="Birth date in ISO or YYYY-MM-DD format")
    Gender: str = Field("NotSet", description="Male | Female | Other | NotSet")
    MaritalStatus: Optional[str] = "Single"
    Status: Optional[str] = Field("Active", description="Active | Inactive | Duplicate")
    Email: Optional[str] = None
    Mobile: Optional[str] = None
    PhoneWithExt: Optional[str] = None
    WorkPhoneWithExt: Optional[str] = None
    AddressDetail: Optional[OptionalAddressDetailModel] = None
    SSN: Optional[str] = None
    DefaultLocationId: Optional[int] = 1
    ResponsiblePartyPatientId: Optional[int] = None
    ExtentedAttributes: Optional[Dict[str, str]] = None


class FilterByField(BaseModel):
    FieldName: str
    FieldValue: str
    Operator: Optional[str] = "Equals"


class OrderByField(BaseModel):
    FieldName: str
    OrderBy: Optional[str] = "Ascending"


class SearchRequest(BaseModel):
    """Official CareStack SearchRequest payload for POST /api/v1.0/patients/search."""
    SearchTerm: Optional[str] = None
    FilterByFields: Optional[List[FilterByField]] = Field(default_factory=list)
    OrderByFields: Optional[List[OrderByField]] = Field(default_factory=list)
    SelectFields: Optional[str] = None
    IncludeInactiveRecords: Optional[bool] = False
    Offset: Optional[int] = 0
    Limit: Optional[int] = 50


class PatientSearchResponseModel(BaseModel):
    """Official CareStack search response element."""
    PatientId: int
    PatientIdentifier: Optional[str] = None
    FirstName: str
    MiddleName: Optional[str] = None
    LastName: str
    NickName: Optional[str] = None
    Email: Optional[str] = None
    SSN: Optional[str] = None
    PhoneWithExt: Optional[str] = None
    AddressLine1: Optional[str] = None
    AddressLine2: Optional[str] = None
    City: Optional[str] = None
    State: Optional[str] = None
    ZipCode: Optional[str] = None
    LocationName: Optional[str] = "Main Operatory"
    IsActive: Optional[bool] = True
    ResponsiblePartyPatientId: Optional[int] = None


class PagedResultsOfPatientViewModel(BaseModel):
    """Paged response for patient sync / listing."""
    Results: List[PatientViewModel] = Field(default_factory=list)
    TotalRecords: int = 0
    ContinueToken: Optional[str] = None


class ProcedureCodeBasicApiResponseModel(BaseModel):
    """Official CDT Dental Procedure Code returned by GET /api/v1.0/procedure-codes."""
    Id: int
    Code: str = Field(..., description="CDT procedure code e.g. D7140, D4341")
    CdtCategoryId: Optional[str] = "OralandMaxillofacialSurgery"
    CodeTypeId: Optional[str] = "Dental"
    Description: str = Field(..., description="Clinical procedure name")


class Surface(BaseModel):
    """Tooth surface involvement."""
    Mesial: bool = False
    Distal: bool = False
    Occlusal: bool = False
    Incisal: bool = False
    Facial: bool = False
    Lingual: bool = False


class TreatmentProcedureSyncModel(BaseModel):
    """Official CareStack treatment procedure for sync & appointment treatments."""
    Id: int
    PatientId: int
    TreatmentPlanId: Optional[int] = 1001
    TreatmentPlanPhaseId: Optional[int] = 1
    ProcedureCodeId: int
    ProcedureCode: Optional[str] = None
    QuadrantId: Optional[int] = None
    Tooth: Optional[str] = None
    Surfaces: Optional[Surface] = None
    MaterialId: Optional[int] = None
    ProviderId: Optional[int] = 101
    LocationId: Optional[int] = 1
    ProposedDate: Optional[str] = None
    DateOfService: Optional[str] = None
    PatientEstimate: Optional[float] = 0.0
    InsuranceEstimate: Optional[float] = 0.0
    StatusId: Optional[str] = "Proposed"
    LastUpdatedOn: Optional[str] = None
    IsDeleted: Optional[bool] = False
    AppointmentId: Optional[int] = None


class AppointmentProviderModel(BaseModel):
    ProviderId: int
    ProviderName: Optional[str] = None


class AppointmentDetailModel(BaseModel):
    """Official CareStack Appointment model."""
    Id: Optional[int] = None
    PatientId: int
    LocationId: Optional[int] = 1
    OperatoryId: Optional[int] = 1
    DateTime: str
    Duration: Optional[int] = 60
    StatusId: Optional[int] = 1
    Notes: Optional[str] = None
    BookingMode: Optional[str] = "Direct"
    AppointmentMode: Optional[str] = "InOffice"
    ProviderIds: List[int] = Field(default_factory=list)
    ProductionTypeId: Optional[int] = 1
    Providers: Optional[List[AppointmentProviderModel]] = None


class AppointmentStatusExternalModel(BaseModel):
    Id: int
    Name: str
    Description: Optional[str] = None
    Color: Optional[str] = "#3B82F6"


class LocationDetailModel(BaseModel):
    Id: int
    Name: str
    Address: Optional[str] = None
    Phone: Optional[str] = None


class OperatoryDetail(BaseModel):
    Id: int
    Name: str
    LocationId: int


class PerioMeasurement(BaseModel):
    """Detailed periodontal probing examination record for a specific tooth."""
    tooth_number: str
    buccal_depths: List[int] = Field(default_factory=lambda: [3, 2, 3])
    lingual_depths: List[int] = Field(default_factory=lambda: [3, 2, 3])
    bleeding_on_probing: bool = False
    furcation: Optional[int] = None
    mobility: Optional[int] = 0


class PeriodontalChart(BaseModel):
    """Official CareStack periodontal charting exam returned by GET /api/v1.0/patients/{id}/periodontal-charting."""
    id: Optional[str] = None
    PatientID: int
    Date: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ExamName: str = "Comprehensive Periodontal Evaluation"
    ProviderID: Optional[int] = 101
    LocationID: Optional[int] = 1
    Status: str = "Active"
    Dentition: str = "Permanent"
    teeth: List[PerioMeasurement] = Field(default_factory=list)


class CareStackErrorResponse(BaseModel):
    """Standard CareStack API Error model for 4xx/5xx responses."""
    code: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Error message summary")
    details: Optional[str] = Field(None, description="Detailed validation or error description")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# =====================================================================
# Backward Compatibility Schemas & MDIN Adapters
# =====================================================================

class DentalProcedure(BaseModel):
    """CDT Procedure representation within active treatment plans."""
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
    """
    MDIN Dental Patient Representation.
    Dual-compatible with Phase 1/2 tests/frontend and CareStack PatientViewModel.
    """
    id: str = Field(..., description="CareStack patient identifier, e.g. CS-2001")
    mrn: str = Field(..., description="Medical Record Number, e.g. MRN-10001")
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

    def to_view_model(self) -> PatientViewModel:
        """Converts to official CareStack PatientViewModel."""
        numeric_id = int("".join(c for c in self.id if c.isdigit()) or "101")
        return PatientViewModel(
            Id=numeric_id,
            PatientIdentifier=self.id,
            FirstName=self.first_name,
            LastName=self.last_name,
            DOB=self.birth_date,
            Gender=self.gender.capitalize() if self.gender else "NotSet",
            Email=self.email,
            Mobile=self.phone,
            Status="Active",
            AddressDetail=OptionalAddressDetailModel(
                Line1="123 Dental Way",
                City="Boston",
                State="MA",
                Zip="02115",
            ),
        )

    def to_search_result(self) -> PatientSearchResponseModel:
        numeric_id = int("".join(c for c in self.id if c.isdigit()) or "101")
        return PatientSearchResponseModel(
            PatientId=numeric_id,
            PatientIdentifier=self.id,
            FirstName=self.first_name,
            LastName=self.last_name,
            Email=self.email,
            PhoneWithExt=self.phone,
            IsActive=True,
        )


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
