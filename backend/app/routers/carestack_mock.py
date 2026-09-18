"""
CareStack Dental Practice Management System (PMS) Web API V1 & Simulator.
Implements the official CareStack Web API V1 specification from developer.carestack.com.
Supports:
1. Three-key header authentication: VendorKey, AccountKey, AccountId.
2. Official CareStack V1 endpoints:
   - /patients, /patients/{id}, /patients/search, /patients/{id}/periodontal-charting
   - /procedure-codes, /treatments/appointment-procedures/{appointmentId}
   - /appointments, /appointments/{appointmentId}, /modify-status, /checkout, /cancel
   - /sync/patients, /sync/treatment-procedures
   - /locations, /operatories, /appointment-status
3. MDIN Interoperability bridges:
   - /webhook (Appointment / check-in demographic resolution against FHIR EHR)
   - /patients/{id}/medical-alerts (Chart alert writebacks)
   - /cache/{patient_id}, /status, /sync
"""

import uuid
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Header, Request, status
from pydantic import BaseModel, Field

from ..schemas.carestack import (
    PatientViewModel,
    OptionalAddressDetailModel,
    SearchRequest,
    PatientSearchResponseModel,
    PagedResultsOfPatientViewModel,
    ProcedureCodeBasicApiResponseModel,
    PeriodontalChart,
    PerioMeasurement,
    AppointmentDetailModel,
    AppointmentProviderModel,
    AppointmentStatusExternalModel,
    LocationDetailModel,
    OperatoryDetail,
    TreatmentProcedureSyncModel,
    Surface,
    CareStackPatient,
    DentalProcedure,
    CareStackSyncRequest,
    SyncStatusResponse,
)
from ..config import settings
from .fhir_ehr_mock import FHIR_STORE, _calculate_similarity, _normalize_ref_id

router = APIRouter()

# =====================================================================
# In-Memory Storage & Clinical Context Caches
# =====================================================================

SYNCED_CLINICAL_CACHE: Dict[str, Dict[str, Any]] = {}
PATIENT_MEDICAL_ALERTS: Dict[str, List[Dict[str, Any]]] = {}

CARESTACK_PATIENT_ALIASES: Dict[str, str] = {
    "pat-1": "CS-2001",
    "patient-001": "CS-2001",
    "patient-1": "CS-2001",
    "mrn-10001": "CS-2001",
    "cs-2001": "CS-2001",
    "pat-2": "CS-2002",
    "patient-002": "CS-2002",
    "patient-2": "CS-2002",
    "mrn-10002": "CS-2002",
    "cs-2002": "CS-2002",
    "pat-3": "CS-2003",
    "patient-003": "CS-2003",
    "patient-3": "CS-2003",
    "mrn-10003": "CS-2003",
    "cs-1003": "CS-2003",
    "cs-2003": "CS-2003",
    "pat-4": "CS-2004",
    "patient-004": "CS-2004",
    "patient-4": "CS-2004",
    "mrn-10004": "CS-2004",
    "cs-2004": "CS-2004",
    "pat-5": "CS-2005",
    "patient-005": "CS-2005",
    "patient-5": "CS-2005",
    "mrn-10005": "CS-2005",
    "cs-2005": "CS-2005",
}

# =====================================================================
# Authentication Helper for CareStack Web API V1
# =====================================================================

def verify_carestack_credentials(
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
    enforce: bool = False,
) -> Dict[str, str]:
    """
    Validates CareStack three-key API authentication headers:
    VendorKey, AccountKey, AccountId.
    If provided or if enforcement is active, credentials must match configured keys.
    """
    # If any key is provided, validate all 3
    if vendorkey is not None or accountkey is not None or accountid is not None or enforce:
        valid_vendor = (vendorkey == settings.CARESTACK_VENDOR_KEY)
        valid_account_key = (accountkey == settings.CARESTACK_ACCOUNT_KEY)
        valid_account_id = (accountid == settings.CARESTACK_ACCOUNT_ID)

        if not (valid_vendor and valid_account_key and valid_account_id):
            missing_or_invalid = []
            if not valid_vendor:
                missing_or_invalid.append("VendorKey")
            if not valid_account_key:
                missing_or_invalid.append("AccountKey")
            if not valid_account_id:
                missing_or_invalid.append("AccountId")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unauthorized: Invalid or missing CareStack credentials ({', '.join(missing_or_invalid)}). "
                       f"CareStack Web API requires valid VendorKey, AccountKey, and AccountId headers.",
            )

    return {
        "VendorKey": vendorkey or settings.CARESTACK_VENDOR_KEY,
        "AccountKey": accountkey or settings.CARESTACK_ACCOUNT_KEY,
        "AccountId": accountid or settings.CARESTACK_ACCOUNT_ID,
    }


# =====================================================================
# Seed Clinical Dental Data Aligned with Official CareStack Models
# =====================================================================

MOCK_PROCEDURE_CODES: List[ProcedureCodeBasicApiResponseModel] = [
    ProcedureCodeBasicApiResponseModel(
        Id=101,
        Code="D0120",
        CdtCategoryId="Diagnostic",
        CodeTypeId="Dental",
        Description="Periodic oral evaluation - established patient",
    ),
    ProcedureCodeBasicApiResponseModel(
        Id=102,
        Code="D1110",
        CdtCategoryId="Preventive",
        CodeTypeId="Dental",
        Description="Prophylaxis - adult (scaling and polishing)",
    ),
    ProcedureCodeBasicApiResponseModel(
        Id=103,
        Code="D4341",
        CdtCategoryId="Periodontics",
        CodeTypeId="Dental",
        Description="Periodontal scaling and root planing - four or more teeth per quadrant",
    ),
    ProcedureCodeBasicApiResponseModel(
        Id=104,
        Code="D7140",
        CdtCategoryId="OralandMaxillofacialSurgery",
        CodeTypeId="Dental",
        Description="Extraction, erupted tooth or exposed root",
    ),
    ProcedureCodeBasicApiResponseModel(
        Id=105,
        Code="D7210",
        CdtCategoryId="OralandMaxillofacialSurgery",
        CodeTypeId="Dental",
        Description="Extraction, erupted tooth requiring removal of bone and/or sectioning of tooth",
    ),
    ProcedureCodeBasicApiResponseModel(
        Id=106,
        Code="D2740",
        CdtCategoryId="Restorative",
        CodeTypeId="Dental",
        Description="Crown - porcelain/ceramic substrate",
    ),
    ProcedureCodeBasicApiResponseModel(
        Id=107,
        Code="D2750",
        CdtCategoryId="Restorative",
        CodeTypeId="Dental",
        Description="Crown - porcelain fused to high noble metal",
    ),
    ProcedureCodeBasicApiResponseModel(
        Id=108,
        Code="D9110",
        CdtCategoryId="AdjunctiveGeneralServices",
        CodeTypeId="Dental",
        Description="Palliative emergency treatment of dental pain - minor procedure",
    ),
]

MOCK_LOCATIONS: List[LocationDetailModel] = [
    LocationDetailModel(
        Id=1,
        Name="CareStack Center for Advanced Dentistry - Main Operatory",
        Address="100 Healthcare Boulevard, Suite 400, Boston, MA 02115",
        Phone="(555) 019-2830",
    ),
    LocationDetailModel(
        Id=2,
        Name="CareStack Periodontal & Surgical Annex",
        Address="104 Healthcare Boulevard, Suite 210, Boston, MA 02115",
        Phone="(555) 019-2835",
    ),
]

MOCK_OPERATORIES: List[OperatoryDetail] = [
    OperatoryDetail(Id=1, Name="Operatory 1 (Surgical)", LocationId=1),
    OperatoryDetail(Id=2, Name="Operatory 2 (Restorative)", LocationId=1),
    OperatoryDetail(Id=3, Name="Hygiene 1 (Prophylaxis)", LocationId=1),
    OperatoryDetail(Id=4, Name="Operatory 3 (Endodontics)", LocationId=2),
]

MOCK_APPOINTMENT_STATUSES: List[AppointmentStatusExternalModel] = [
    AppointmentStatusExternalModel(Id=1, Name="Scheduled", Description="Appointment booked on schedule", Color="#3B82F6"),
    AppointmentStatusExternalModel(Id=2, Name="Confirmed", Description="Patient confirmed arrival", Color="#10B981"),
    AppointmentStatusExternalModel(Id=3, Name="InChair", Description="Patient currently seated in operatory", Color="#F59E0B"),
    AppointmentStatusExternalModel(Id=4, Name="CheckedOut", Description="Clinical procedure completed and patient departed", Color="#6B7280"),
    AppointmentStatusExternalModel(Id=5, Name="Cancelled", Description="Appointment cancelled or rescheduled", Color="#EF4444"),
]

# Registered CareStack dental patients
MOCK_PATIENTS: List[CareStackPatient] = [
    CareStackPatient(
        id="CS-2001",
        mrn="MRN-10001",
        first_name="John",
        last_name="Doe",
        birth_date="1968-04-12",
        gender="male",
        email="john.doe@example.com",
        phone="555-0101",
        last_visit="2026-01-15",
        next_appointment="2026-09-22 09:30:00",
        primary_dentist="Dr. Sarah Mitchell, DDS",
        active_treatment_plan=[
            DentalProcedure(
                code="D7140",
                description="Extraction, erupted tooth or exposed root",
                tooth_number="30",
                status="proposed",
                cost=250.0,
            ),
            DentalProcedure(
                code="D4341",
                description="Periodontal scaling and root planing - four or more teeth per quadrant",
                tooth_number="LL",
                status="scheduled",
                cost=320.0,
            ),
        ],
    ),
    CareStackPatient(
        id="CS-2002",
        mrn="MRN-10002",
        first_name="Jane",
        last_name="Smith",
        birth_date="1980-09-23",
        gender="female",
        email="jane.smith@example.com",
        phone="555-0102",
        last_visit="2026-03-10",
        next_appointment="2026-09-24 11:00:00",
        primary_dentist="Dr. Sarah Mitchell, DDS",
        active_treatment_plan=[
            DentalProcedure(
                code="D1110",
                description="Prophylaxis - adult (scaling/polishing, induces bacteremia)",
                tooth_number="General",
                status="scheduled",
                cost=110.0,
            ),
            DentalProcedure(
                code="D2740",
                description="Crown - porcelain/ceramic substrate",
                tooth_number="14",
                status="proposed",
                cost=1350.0,
            ),
        ],
    ),
    CareStackPatient(
        id="CS-1003",
        mrn="MRN-10003",
        first_name="Robert",
        last_name="Taylor",
        birth_date="1974-11-05",
        gender="male",
        email="robert.taylor@example.com",
        phone="555-0103",
        last_visit="2025-11-05",
        next_appointment="2026-09-30 09:00:00",
        primary_dentist="Dr. Alan Vance, DMD",
        active_treatment_plan=[
            DentalProcedure(
                code="D7210",
                description="Extraction, erupted tooth requiring removal of bone and/or sectioning of tooth",
                tooth_number="32",
                status="proposed",
                cost=450.0,
            )
        ],
    ),
    CareStackPatient(
        id="CS-1001",
        mrn="EHR-88201",
        first_name="Eleanor",
        last_name="Vance",
        birth_date="1968-04-12",
        gender="female",
        email="eleanor.vance@example.com",
        phone="555-0192",
        last_visit="2026-02-10",
        next_appointment="2026-09-22 10:00:00",
        primary_dentist="Dr. Sarah Mitchell, DDS",
        active_treatment_plan=[
            DentalProcedure(
                code="D7140",
                description="Extraction, erupted tooth or exposed root",
                tooth_number="19",
                status="proposed",
                cost=220.0,
            ),
            DentalProcedure(
                code="D4341",
                description="Periodontal scaling and root planing",
                tooth_number="LR",
                status="scheduled",
                cost=310.0,
            ),
        ],
    ),
    CareStackPatient(
        id="CS-1002",
        mrn="EHR-54109",
        first_name="Marcus",
        last_name="Chen",
        birth_date="1982-11-03",
        gender="male",
        email="marcus.chen@example.com",
        phone="555-0143",
        last_visit="2026-01-18",
        next_appointment="2026-09-25 14:30:00",
        primary_dentist="Dr. Sarah Mitchell, DDS",
        active_treatment_plan=[
            DentalProcedure(
                code="D2750",
                description="Crown - porcelain fused to high noble metal",
                tooth_number="30",
                status="proposed",
                cost=1250.0,
            )
        ],
    ),
    CareStackPatient(
        id="CS-2004",
        mrn="MRN-10004",
        first_name="Marcus",
        last_name="Chen",
        birth_date="1985-06-14",
        gender="male",
        email="marcus.chen@example.com",
        phone="555-0104",
        last_visit="2026-02-14",
        next_appointment="2026-09-28 10:00:00",
        primary_dentist="Dr. Alan Vance, DMD",
        active_treatment_plan=[
            DentalProcedure(
                code="D7210",
                description="Extraction, erupted tooth requiring removal of bone and/or sectioning of tooth",
                tooth_number="17",
                status="proposed",
                cost=480.0,
            )
        ],
    ),
    CareStackPatient(
        id="CS-2005",
        mrn="MRN-10005",
        first_name="Sarah",
        last_name="Jenkins",
        birth_date="1972-03-29",
        gender="female",
        email="sarah.jenkins@example.com",
        phone="555-0105",
        last_visit="2026-03-01",
        next_appointment="2026-09-29 11:30:00",
        primary_dentist="Dr. Sarah Mitchell, DDS",
        active_treatment_plan=[
            DentalProcedure(
                code="D7286",
                description="Incisional biopsy of oral tissue",
                tooth_number="Buccal Mucosa",
                status="proposed",
                cost=350.0,
            )
        ],
    ),
]

# Simulated active appointments
MOCK_APPOINTMENTS: Dict[int, Dict[str, Any]] = {
    5001: {
        "Id": 5001,
        "PatientId": 2001,
        "LocationId": 1,
        "OperatoryId": 1,
        "DateTime": "2026-09-22T09:30:00Z",
        "Duration": 60,
        "StatusId": 1,
        "Notes": "Scheduled for surgical extraction tooth #30",
        "BookingMode": "Direct",
        "AppointmentMode": "InOffice",
        "ProviderIds": [101],
        "ProductionTypeId": 1,
        "Procedures": [104, 103],  # D7140, D4341
    },
    5002: {
        "Id": 5002,
        "PatientId": 2002,
        "LocationId": 1,
        "OperatoryId": 3,
        "DateTime": "2026-09-24T11:00:00Z",
        "Duration": 45,
        "StatusId": 2,
        "Notes": "Scheduled for adult prophylaxis and crown prep",
        "BookingMode": "Direct",
        "AppointmentMode": "InOffice",
        "ProviderIds": [101],
        "ProductionTypeId": 1,
        "Procedures": [102, 106],  # D1110, D2740
    },
}


# =====================================================================
# Official CareStack Web API V1 Endpoints
# =====================================================================

@router.get("/auth/verify", tags=["CareStack Web API V1 - Authentication"])
async def verify_credentials_endpoint(
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    CareStack credential verification endpoint.
    Tests that VendorKey, AccountKey, and AccountId headers match authorized keys.
    """
    creds = verify_carestack_credentials(vendorkey, accountkey, accountid, enforce=True)
    return {
        "authenticated": True,
        "status": "authorized",
        "accountId": creds["AccountId"],
        "message": "CareStack API keys validated successfully.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/patients/{patient_id}", response_model=Union[PatientViewModel, CareStackPatient], tags=["CareStack Web API V1 - Patients"])
async def get_patient_record(
    patient_id: str,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    GET /api/v1.0/patients/{id}
    Retrieves a CareStack patient record by integer ID, CareStack patient identifier, or MRN.
    Returns official CareStack PatientViewModel or CareStackPatient.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    # Search in MOCK_PATIENTS
    clean_id = patient_id.strip()
    clean_num = "".join(c for c in clean_id if c.isdigit())

    for p in MOCK_PATIENTS:
        p_num = "".join(c for c in p.id if c.isdigit())
        if p.id == clean_id or p.mrn == clean_id or (clean_num and p_num == clean_num):
            # If requested via official header or /api/v1.0 format, return PatientViewModel
            if vendorkey or accountkey or clean_id.isdigit():
                return p.to_view_model()
            return p

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"CareStack patient '{patient_id}' not found")


@router.post("/patients/search", response_model=List[PatientSearchResponseModel], tags=["CareStack Web API V1 - Patients"])
async def search_patients(
    request: SearchRequest,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    POST /api/v1.0/patients/search
    Searches CareStack dental patients by name, patient identifier, or phone.
    Returns official PatientSearchResponseModel list.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    results = []
    term = (request.SearchTerm or "").lower().strip()

    for p in MOCK_PATIENTS:
        if not term or (
            term in p.first_name.lower()
            or term in p.last_name.lower()
            or term in p.id.lower()
            or term in p.mrn.lower()
            or (p.phone and term in p.phone.lower())
        ):
            results.append(p.to_search_result())

    offset = request.Offset or 0
    limit = request.Limit or 50
    return results[offset : offset + limit]


@router.post("/patients", response_model=PatientViewModel, status_code=status.HTTP_201_CREATED, tags=["CareStack Web API V1 - Patients"])
async def create_patient(
    patient: PatientViewModel,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    POST /api/v1.0/patients
    Creates a new patient record in CareStack PMS.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    new_num = max([int("".join(c for c in p.id if c.isdigit()) or 1000) for p in MOCK_PATIENTS] + [2000]) + 1
    new_id = f"CS-{new_num}"
    new_mrn = f"MRN-{new_num}"

    created_pt = CareStackPatient(
        id=new_id,
        mrn=new_mrn,
        first_name=patient.FirstName,
        last_name=patient.LastName,
        birth_date=patient.DOB[:10] if patient.DOB else "1990-01-01",
        gender=patient.Gender.lower() if patient.Gender else "unknown",
        email=patient.Email,
        phone=patient.Mobile or patient.PhoneWithExt,
    )
    MOCK_PATIENTS.append(created_pt)
    result = created_pt.to_view_model()
    result.Id = new_num
    return result


@router.put("/patients", response_model=PatientViewModel, tags=["CareStack Web API V1 - Patients"])
async def update_patient(
    patient: PatientViewModel,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    PUT /api/v1.0/patients
    Updates an existing patient record in CareStack PMS.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    for p in MOCK_PATIENTS:
        p_num = "".join(c for c in p.id if c.isdigit())
        if (patient.Id and str(patient.Id) == p_num) or (patient.PatientIdentifier and patient.PatientIdentifier == p.id):
            p.first_name = patient.FirstName
            p.last_name = patient.LastName
            if patient.Email:
                p.email = patient.Email
            if patient.Mobile:
                p.phone = patient.Mobile
            return p.to_view_model()

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient to update not found")


@router.get("/patients/{patient_id}/periodontal-charting", response_model=PeriodontalChart, tags=["CareStack Web API V1 - Perio"])
async def get_periodontal_charting(
    patient_id: str,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    GET /api/v1.0/patients/{patientId}/periodontal-charting
    Retrieves comprehensive periodontal probing depths and examination records.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    clean_num = int("".join(c for c in patient_id if c.isdigit()) or "2001")

    # Generate realistic periodontal measurements for key teeth (1 to 32)
    teeth_data = []
    for tooth in ["2", "3", "14", "15", "18", "19", "30", "31"]:
        # Teeth with deeper pockets indicating periodontal disease
        if tooth in ["19", "30"]:
            teeth_data.append(
                PerioMeasurement(
                    tooth_number=tooth,
                    buccal_depths=[5, 4, 6],
                    lingual_depths=[5, 5, 6],
                    bleeding_on_probing=True,
                    furcation=2,
                    mobility=1,
                )
            )
        else:
            teeth_data.append(
                PerioMeasurement(
                    tooth_number=tooth,
                    buccal_depths=[3, 2, 3],
                    lingual_depths=[3, 2, 3],
                    bleeding_on_probing=False,
                )
            )

    return PeriodontalChart(
        id=f"PERIO-{clean_num}",
        PatientID=clean_num,
        Date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ExamName="Comprehensive Full-Mouth Periodontal Probing",
        ProviderID=101,
        LocationID=1,
        Status="Active",
        Dentition="Permanent",
        teeth=teeth_data,
    )


@router.get("/procedure-codes", response_model=List[ProcedureCodeBasicApiResponseModel], tags=["CareStack Web API V1 - Treatments"])
async def list_procedure_codes(
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    GET /api/v1.0/procedure-codes
    Retrieves all American Dental Association (ADA) Code on Dental Procedures and Nomenclature (CDT) codes.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)
    return MOCK_PROCEDURE_CODES


@router.get("/treatments/appointment-procedures/{appointment_id}", response_model=List[int], tags=["CareStack Web API V1 - Treatments"])
async def get_appointment_procedures(
    appointment_id: int,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    GET /api/v1.0/treatments/appointment-procedures/{appointmentId}
    Returns procedure code IDs associated with a specific appointment.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    apt = MOCK_APPOINTMENTS.get(appointment_id)
    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Appointment {appointment_id} not found")

    return apt.get("Procedures", [])


@router.get("/appointments/{appointment_id}", response_model=AppointmentDetailModel, tags=["CareStack Web API V1 - Appointments"])
async def get_appointment(
    appointment_id: int,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    GET /api/v1.0/appointments/{appointmentId}
    Retrieves appointment details from CareStack.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    apt = MOCK_APPOINTMENTS.get(appointment_id)
    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Appointment {appointment_id} not found")

    return AppointmentDetailModel(
        Id=apt["Id"],
        PatientId=apt["PatientId"],
        LocationId=apt.get("LocationId", 1),
        OperatoryId=apt.get("OperatoryId", 1),
        DateTime=apt["DateTime"],
        Duration=apt.get("Duration", 60),
        StatusId=apt.get("StatusId", 1),
        Notes=apt.get("Notes"),
        BookingMode=apt.get("BookingMode", "Direct"),
        AppointmentMode=apt.get("AppointmentMode", "InOffice"),
        ProviderIds=apt.get("ProviderIds", [101]),
        Providers=[AppointmentProviderModel(ProviderId=101, ProviderName="Dr. Sarah Mitchell, DDS")],
    )


@router.post("/appointments", response_model=AppointmentDetailModel, status_code=status.HTTP_201_CREATED, tags=["CareStack Web API V1 - Appointments"])
async def create_appointment(
    appointment: AppointmentDetailModel,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    POST /api/v1.0/appointments
    Books a new chairside appointment.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    new_id = max(MOCK_APPOINTMENTS.keys(), default=5000) + 1
    apt_data = appointment.model_dump()
    apt_data["Id"] = new_id
    MOCK_APPOINTMENTS[new_id] = apt_data

    return AppointmentDetailModel(
        Id=new_id,
        PatientId=appointment.PatientId,
        LocationId=appointment.LocationId or 1,
        OperatoryId=appointment.OperatoryId or 1,
        DateTime=appointment.DateTime,
        Duration=appointment.Duration or 60,
        StatusId=1,
        Notes=appointment.Notes,
        ProviderIds=appointment.ProviderIds or [101],
        Providers=[AppointmentProviderModel(ProviderId=101, ProviderName="Dr. Sarah Mitchell, DDS")],
    )


@router.put("/appointments/{appointment_id}/modify-status", tags=["CareStack Web API V1 - Appointments"])
async def modify_appointment_status(
    appointment_id: int,
    payload: Dict[str, Any],
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    PUT /api/v1.0/appointments/{appointmentId}/modify-status
    Modifies status of appointment (e.g. InChair, Confirmed).
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    apt = MOCK_APPOINTMENTS.get(appointment_id)
    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Appointment {appointment_id} not found")

    new_status = payload.get("StatusId", 2)
    apt["StatusId"] = new_status
    return {
        "success": True,
        "appointmentId": appointment_id,
        "statusId": new_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.put("/appointments/{appointment_id}/checkout", tags=["CareStack Web API V1 - Appointments"])
async def checkout_appointment(
    appointment_id: int,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    PUT /api/v1.0/appointments/{appointmentId}/checkout
    Checks out an appointment post-treatment.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    apt = MOCK_APPOINTMENTS.get(appointment_id)
    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Appointment {appointment_id} not found")

    apt["StatusId"] = 4  # CheckedOut
    return {
        "success": True,
        "appointmentId": appointment_id,
        "status": "CheckedOut",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.put("/appointments/{appointment_id}/cancel", tags=["CareStack Web API V1 - Appointments"])
async def cancel_appointment(
    appointment_id: int,
    payload: Optional[Dict[str, Any]] = None,
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    PUT /api/v1.0/appointments/{appointmentId}/cancel
    Cancels an appointment.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    apt = MOCK_APPOINTMENTS.get(appointment_id)
    if not apt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Appointment {appointment_id} not found")

    apt["StatusId"] = 5  # Cancelled
    apt["CancelReason"] = (payload or {}).get("CancelReason", "Patient request")
    return {
        "success": True,
        "appointmentId": appointment_id,
        "status": "Cancelled",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/appointment-status", response_model=List[AppointmentStatusExternalModel], tags=["CareStack Web API V1 - Appointments"])
async def get_appointment_statuses(
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    GET /api/v1.0/appointment-status
    Lists all appointment status enumerations.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)
    return MOCK_APPOINTMENT_STATUSES


@router.get("/sync/patients", response_model=PagedResultsOfPatientViewModel, tags=["CareStack Web API V1 - Sync"])
async def sync_patients_endpoint(
    modifiedSince: Optional[str] = Query(None, description="ISO timestamp for incremental sync"),
    continueToken: Optional[str] = Query(None, description="Continuation token for pagination"),
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    GET /api/v1.0/sync/patients
    Incremental synchronization of patient records.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    view_models = [p.to_view_model() for p in MOCK_PATIENTS]
    return PagedResultsOfPatientViewModel(
        Results=view_models,
        TotalRecords=len(view_models),
        ContinueToken=None,
    )


@router.get("/sync/treatment-procedures", response_model=List[TreatmentProcedureSyncModel], tags=["CareStack Web API V1 - Sync"])
async def sync_treatment_procedures(
    modifiedSince: Optional[str] = Query(None),
    continueToken: Optional[str] = Query(None),
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """
    GET /api/v1.0/sync/treatment-procedures
    Returns all treatment plan procedures across registered patients for sync.
    """
    verify_carestack_credentials(vendorkey, accountkey, accountid)

    sync_list = []
    proc_counter = 7001
    for p in MOCK_PATIENTS:
        p_num = int("".join(c for c in p.id if c.isdigit()) or "2001")
        for proc in p.active_treatment_plan:
            code_id = next((c.Id for c in MOCK_PROCEDURE_CODES if c.Code == proc.code), 104)
            sync_list.append(
                TreatmentProcedureSyncModel(
                    Id=proc_counter,
                    PatientId=p_num,
                    TreatmentPlanId=1001,
                    TreatmentPlanPhaseId=1,
                    ProcedureCodeId=code_id,
                    ProcedureCode=proc.code,
                    Tooth=proc.tooth_number,
                    PatientEstimate=proc.cost or 250.0,
                    StatusId=proc.status.capitalize(),
                    LastUpdatedOn=datetime.now(timezone.utc).isoformat(),
                )
            )
            proc_counter += 1

    return sync_list


@router.get("/locations", response_model=List[LocationDetailModel], tags=["CareStack Web API V1 - Practice"])
async def list_locations(
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """GET /api/v1.0/locations - List all clinic locations."""
    verify_carestack_credentials(vendorkey, accountkey, accountid)
    return MOCK_LOCATIONS


@router.get("/operatories", response_model=List[OperatoryDetail], tags=["CareStack Web API V1 - Practice"])
async def list_operatories(
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """GET /api/v1.0/operatories - List all practice operatories."""
    verify_carestack_credentials(vendorkey, accountkey, accountid)
    return MOCK_OPERATORIES


@router.get("/production-types", tags=["CareStack Web API V1 - Practice"])
async def list_production_types(
    vendorkey: Optional[str] = Header(None, alias="VendorKey"),
    accountkey: Optional[str] = Header(None, alias="AccountKey"),
    accountid: Optional[str] = Header(None, alias="AccountId"),
):
    """GET /api/v1.0/production-types - List production types."""
    verify_carestack_credentials(vendorkey, accountkey, accountid)
    return [
        {"Id": 1, "Name": "General Dentistry"},
        {"Id": 2, "Name": "Oral and Maxillofacial Surgery"},
        {"Id": 3, "Name": "Periodontics"},
        {"Id": 4, "Name": "Prosthodontics"},
    ]


# =====================================================================
# MDIN Interoperability Bridges & Webhook Ingestion
# =====================================================================

class WebhookPatientDemographics(BaseModel):
    """Demographics passed within a CareStack webhook event."""
    id: str = Field(..., description="CareStack internal patient identifier, e.g. CS-2001")
    first_name: str = Field(..., description="Patient given name")
    last_name: str = Field(..., description="Patient family name")
    birth_date: str = Field(..., description="Birth date in YYYY-MM-DD format")
    gender: Optional[str] = Field(None, description="male | female | other")
    mrn: Optional[str] = Field(None, description="External Medical Record Number if known")
    email: Optional[str] = None
    phone: Optional[str] = None


class WebhookAppointmentDetails(BaseModel):
    """Appointment context passed with webhook."""
    appointment_id: Optional[str] = Field(default_factory=lambda: f"APT-{uuid.uuid4().hex[:6].upper()}")
    date_time: Optional[str] = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    operatory: Optional[str] = "Operatory 2"
    provider: Optional[str] = "Dr. Sarah Mitchell, DDS"
    reason: Optional[str] = "Surgical Dental Extraction"
    procedures: List[DentalProcedure] = Field(default_factory=list)


class CareStackWebhookEvent(BaseModel):
    """CareStack Webhook payload for appointment creation or patient check-in."""
    event_type: str = Field("patient.checkin", description="appointment.created | patient.checkin | appointment.updated")
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    patient: WebhookPatientDemographics
    appointment: Optional[WebhookAppointmentDetails] = None


class MedicalAlertCreate(BaseModel):
    """High-priority medical flag payload written back into CareStack's chart."""
    alert_type: str = Field(..., description="critical | warning | info")
    category: str = Field(..., description="coagulation | cardiac | metabolic | allergy | pharmacology")
    title: str = Field(..., description="Brief alert title for chairside display")
    details: str = Field(..., description="Detailed clinical guidance and contraindications")
    source: str = Field("MDIN Interoperability Node", description="Originating surveillance engine")
    action_required: Optional[str] = Field(None, description="Required clinician action (e.g. Pre-op antibiotic)")


def _match_ehr_patient(demographics: WebhookPatientDemographics) -> Optional[Dict[str, Any]]:
    """
    Queries the simulated FHIR EHR node via demographic matching.
    Calculates exact and probabilistic similarity scores on name, DOB, and identifier.
    """
    best_match = None
    best_score = 0.0

    target_first = demographics.first_name.strip().lower()
    target_last = demographics.last_name.strip().lower()
    target_dob = demographics.birth_date.strip()
    target_mrn = demographics.mrn.strip().lower() if demographics.mrn else None

    for pt in FHIR_STORE["Patient"]:
        score = 0.0
        # Check MRN / Identifier exact match
        if target_mrn:
            pt_mrns = [ident.get("value", "").lower() for ident in pt.get("identifier", [])]
            pt_mrns.append(pt.get("id", "").lower())
            if target_mrn in pt_mrns:
                return {"patient": pt, "confidence": 1.0, "match_type": "exact_mrn"}

        # Birth date match
        dob_match = (pt.get("birthDate") == target_dob)
        if dob_match:
            score += 0.4
        else:
            score -= 0.3

        # Name match
        name_scores = []
        for n in pt.get("name", []):
            fam = n.get("family", "").lower()
            givens = [g.lower() for g in n.get("given", [])]

            fam_sim = _calculate_similarity(target_last, fam)
            given_sim = max([_calculate_similarity(target_first, g) for g in givens]) if givens else 0.0

            name_scores.append((fam_sim * 0.35) + (given_sim * 0.25))

        if name_scores:
            score += max(name_scores)

        if score > best_score:
            best_score = score
            best_match = pt

    if best_score >= 0.65 and best_match:
        return {"patient": best_match, "confidence": round(best_score, 2), "match_type": "probabilistic_demographic"}

    return None


def _evaluate_clinical_flags(ehr_patient_id: str, dental_procedures: List[DentalProcedure]) -> List[Dict[str, Any]]:
    """
    Analyzes synchronized EHR clinical context against dental chair procedures
    to detect cross-specialty contraindications and formulate alerts.
    """
    alerts = []
    norm_id = _normalize_ref_id(ehr_patient_id).lower()

    conditions = [
        c for c in FHIR_STORE["Condition"]
        if norm_id in _normalize_ref_id(c.get("subject", {}).get("reference", "")).lower()
    ]
    medications = [
        m for m in FHIR_STORE["MedicationRequest"]
        if norm_id in _normalize_ref_id(m.get("subject", {}).get("reference", "")).lower()
    ]
    allergies = [
        a for a in FHIR_STORE["AllergyIntolerance"]
        if norm_id in _normalize_ref_id(a.get("patient", {}).get("reference", "")).lower()
    ]
    observations = [
        o for o in FHIR_STORE["Observation"]
        if norm_id in _normalize_ref_id(o.get("subject", {}).get("reference", "")).lower()
    ]

    has_extraction = any("extraction" in p.description.lower() or p.code in ["D7140", "D7210"] for p in dental_procedures)
    has_invasive_scaling = any("scaling" in p.description.lower() or p.code in ["D4341", "D1110"] for p in dental_procedures)

    # 1. Anticoagulation (Warfarin / Bleeding Hazard)
    is_on_anticoagulant = any("warfarin" in (m.get("medicationCodeableConcept", {}).get("text", "")).lower() for m in medications)
    has_afib = any("atrial fibrillation" in (c.get("code", {}).get("text", "")).lower() for c in conditions)
    if is_on_anticoagulant or has_afib:
        alerts.append({
            "alert_type": "critical",
            "category": "coagulation",
            "title": "CRITICAL: Anticoagulation / Hemorrhage Risk (Warfarin Therapy)",
            "details": (
                "Patient is actively prescribed Warfarin Sodium 5 MG for Atrial Fibrillation. "
                "Planned dental surgical extraction carries substantial postoperative hemorrhage risk. "
                "Verify recent INR (<3.5 within 24-48 hours) and prepare local hemostatic agents (Surgicel, tranexamic acid rinse)."
            ),
            "action_required": "Confirm INR level and deploy local hemostatic measures.",
        })

    # 2. Penicillin Allergy Manifestation (Anaphylaxis)
    has_penicillin_allergy = any("penicillin" in (a.get("code", {}).get("text", "")).lower() for a in allergies)
    if has_penicillin_allergy:
        alerts.append({
            "alert_type": "critical",
            "category": "allergy",
            "title": "CRITICAL: Severe Penicillin Allergy (Anaphylaxis Risk)",
            "details": "Patient has documented Type 1 anaphylactic hypersensitivity to Penicillin. Strict contraindication for Amoxicillin/Penicillin V. Prescribe Clindamycin or Azithromycin if antibiotic indicated.",
            "action_required": "Avoid all beta-lactam antibiotics. Use Clindamycin or Azithromycin alternative.",
        })

    # 3. Prosthetic Heart Valve / Infective Endocarditis Prophylaxis
    has_valve = any(
        "prosthetic" in (c.get("code", {}).get("text", "")).lower() or "endocarditis" in (c.get("code", {}).get("text", "")).lower()
        for c in conditions
    )
    if has_valve and (has_extraction or has_invasive_scaling):
        alerts.append({
            "alert_type": "critical",
            "category": "cardiac",
            "title": "CRITICAL: AHA Antibiotic Prophylaxis Mandatory (Prosthetic Valve)",
            "details": (
                "Patient has a prosthetic mechanical/bioprosthetic cardiac valve. Dental manipulation involving gingival tissue or periapical region "
                "requires American Heart Association (AHA) antibiotic premedication 30-60 minutes prior to procedure to prevent Infective Endocarditis."
            ),
            "action_required": "Administer prophylactic antibiotic 30-60 minutes before procedure.",
        })

    # 4. Uncontrolled Diabetes (HbA1c > 8.0%)
    hba1c_obs = next((o for o in observations if "hba1c" in (o.get("code", {}).get("text", "")).lower()), None)
    hba1c_val = None
    if hba1c_obs and hba1c_obs.get("valueQuantity"):
        hba1c_val = hba1c_obs["valueQuantity"].get("value")

    has_t2d = any("diabetes" in (c.get("code", {}).get("text", "")).lower() for c in conditions)
    if (has_t2d or hba1c_val) and (hba1c_val and hba1c_val >= 8.0):
        alerts.append({
            "alert_type": "warning",
            "category": "metabolic",
            "title": f"WARNING: Poor Glycemic Control (HbA1c {hba1c_val}%) — Impaired Healing Risk",
            "details": (
                f"Most recent HbA1c is {hba1c_val}%. Hyperglycemia significantly impairs neutrophil phagocytosis, "
                "delays post-surgical socket epithelialization, and predisposes to secondary alveolar osteitis and infection."
            ),
            "action_required": "Schedule morning appointments; monitor post-op healing closely.",
        })

    # 5. Bisphosphonates & Osteoporosis (MRONJ)
    has_osteo = any("osteoporosis" in (c.get("code", {}).get("text", "")).lower() for c in conditions)
    if has_osteo and has_extraction:
        alerts.append({
            "alert_type": "critical",
            "category": "pharmacology",
            "title": "CRITICAL: High MRONJ Risk (Bisphosphonate Therapy)",
            "details": "Patient on antiresorptive therapy for Osteoporosis. High risk of Medication-Related Osteonecrosis of the Jaw with extraction.",
            "action_required": "Obtain oncologist clearance or consider conservative endodontic approach.",
        })

    return alerts


@router.post("/webhook", tags=["MDIN Interoperability"])
async def carestack_webhook(event: CareStackWebhookEvent):
    """
    CareStack appointment creation or patient check-in webhook.
    1. Extracts patient demographics from CareStack PMS.
    2. Queries simulated FHIR EHR node via exact/probabilistic demographic matching.
    3. Caches synchronized clinical context in-memory.
    4. Evaluates cross-specialty clinical safety alerts and posts high-priority flags to patient's chart.
    """
    demographics = event.patient
    matched_result = _match_ehr_patient(demographics)

    if not matched_result:
        return {
            "status": "unmatched",
            "message": f"No corresponding Medical EHR record identified for patient {demographics.first_name} {demographics.last_name} (DOB: {demographics.birth_date}).",
            "carestack_patient_id": demographics.id,
            "match_confidence": 0.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    ehr_patient = matched_result["patient"]
    confidence = matched_result["confidence"]
    ehr_id = ehr_patient["id"]

    # Gather full clinical context
    norm_id = _normalize_ref_id(ehr_id).lower()
    conditions = [c for c in FHIR_STORE["Condition"] if norm_id in _normalize_ref_id(c.get("subject", {}).get("reference", "")).lower()]
    medications = [m for m in FHIR_STORE["MedicationRequest"] if norm_id in _normalize_ref_id(m.get("subject", {}).get("reference", "")).lower()]
    allergies = [a for a in FHIR_STORE["AllergyIntolerance"] if norm_id in _normalize_ref_id(a.get("patient", {}).get("reference", "")).lower()]
    observations = [o for o in FHIR_STORE["Observation"] if norm_id in _normalize_ref_id(o.get("subject", {}).get("reference", "")).lower()]

    # Procedures from appointment or active treatment plan
    procedures = []
    if event.appointment and event.appointment.procedures:
        procedures = event.appointment.procedures
    else:
        for p in MOCK_PATIENTS:
            if p.id == demographics.id or p.mrn == demographics.mrn:
                procedures = p.active_treatment_plan
                break

    # Evaluate clinical alerts
    evaluated_alerts = _evaluate_clinical_flags(ehr_id, procedures)

    # Cache synchronized context in memory
    cached_context = {
        "carestack_patient_id": demographics.id,
        "ehr_patient_id": ehr_id,
        "matched_at": datetime.now(timezone.utc).isoformat(),
        "confidence": confidence,
        "match_type": matched_result["match_type"],
        "demographics": {
            "first_name": demographics.first_name,
            "last_name": demographics.last_name,
            "birth_date": demographics.birth_date,
            "gender": demographics.gender,
        },
        "clinical_summary": {
            "active_conditions_count": len(conditions),
            "active_medications_count": len(medications),
            "allergies_count": len(allergies),
            "observations_count": len(observations),
        },
        "conditions": conditions,
        "medications": medications,
        "allergies": allergies,
        "observations": observations,
        "alerts": evaluated_alerts,
    }
    SYNCED_CLINICAL_CACHE[demographics.id] = cached_context
    alias_cache_keys = [demographics.id]
    if ehr_id:
        alias_cache_keys.append(ehr_id)
        if ehr_id in ("patient-001", "pat-1"):
            alias_cache_keys.extend(["pat-1", "patient-001", "CS-2001"])
        elif ehr_id in ("patient-002", "pat-2"):
            alias_cache_keys.extend(["pat-2", "patient-002", "CS-2002"])
        elif ehr_id in ("patient-003", "pat-3"):
            alias_cache_keys.extend(["pat-3", "patient-003", "CS-2003"])
    for key in set(alias_cache_keys):
        SYNCED_CLINICAL_CACHE[key] = cached_context

    # Automatically write high-priority alerts to patient's chart
    if demographics.id not in PATIENT_MEDICAL_ALERTS:
        PATIENT_MEDICAL_ALERTS[demographics.id] = []

    for alert in evaluated_alerts:
        alert_record = {
            "alert_id": f"ALT-{uuid.uuid4().hex[:6].upper()}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active_in_chart",
            **alert,
        }
        if not any(a.get("title") == alert["title"] for a in PATIENT_MEDICAL_ALERTS[demographics.id]):
            PATIENT_MEDICAL_ALERTS[demographics.id].append(alert_record)

    return {
        "status": "synchronized",
        "message": f"Patient {demographics.first_name} {demographics.last_name} successfully resolved and synchronized with Medical EHR ({ehr_id}).",
        "carestack_patient_id": demographics.id,
        "matched_ehr_patient_id": ehr_id,
        "match_confidence": confidence,
        "match_type": matched_result["match_type"],
        "cached": True,
        "alerts_generated": len(evaluated_alerts),
        "alerts": evaluated_alerts,
        "synchronized_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/patients", response_model=List[CareStackPatient], tags=["MDIN Interoperability - Patients"])
async def list_carestack_patients(
    search: Optional[str] = Query(None, description="Search by name, CareStack ID, or MRN"),
):
    """
    Returns dental patients registered in the CareStack PMS, complete with active treatment plans.
    Dual compatible with existing frontend and tests.
    """
    if not search:
        return MOCK_PATIENTS

    search_lower = search.lower().strip()
    return [
        p
        for p in MOCK_PATIENTS
        if search_lower in p.first_name.lower()
        or search_lower in p.last_name.lower()
        or search_lower in p.mrn.lower()
        or search_lower in p.id.lower()
    ]


@router.post("/patients/{patient_id}/medical-alerts", tags=["MDIN Interoperability - Alerts"])
async def write_medical_alert(
    patient_id: str,
    alert: MedicalAlertCreate,
):
    """
    Writes high-priority medical flags back to CareStack's chart.
    Simulates bidirectional push of critical clinical contraindications from MDIN to CareStack PMS.
    """
    canonical_id = CARESTACK_PATIENT_ALIASES.get(patient_id.lower(), patient_id)
    patient = None
    for p in MOCK_PATIENTS:
        if p.id == patient_id or p.mrn == patient_id or p.id == canonical_id or p.mrn == canonical_id:
            patient = p
            break

    if not patient:
        raise HTTPException(status_code=404, detail=f"CareStack patient '{patient_id}' not found")

    alert_id = f"ALT-{uuid.uuid4().hex[:6].upper()}"
    alert_record = {
        "alert_id": alert_id,
        "patient_id": patient.id,
        "mrn": patient.mrn,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "alert_type": alert.alert_type,
        "category": alert.category,
        "title": alert.title,
        "details": alert.details,
        "source": alert.source,
        "action_required": alert.action_required,
        "status": "posted_to_chart",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    for key in {patient.id, patient_id, canonical_id}:
        if key not in PATIENT_MEDICAL_ALERTS:
            PATIENT_MEDICAL_ALERTS[key] = []
        if not any(a["alert_id"] == alert_id for a in PATIENT_MEDICAL_ALERTS[key]):
            PATIENT_MEDICAL_ALERTS[key].append(alert_record)

    return {
        "success": True,
        "message": f"Medical alert '{alert.title}' successfully written back to CareStack chart for {patient.first_name} {patient.last_name}.",
        "alert": alert_record,
    }


@router.get("/patients/{patient_id}/medical-alerts", tags=["MDIN Interoperability - Alerts"])
async def get_patient_medical_alerts(patient_id: str):
    """Retrieve all high-priority medical alerts written to CareStack chart for a patient."""
    canonical_id = CARESTACK_PATIENT_ALIASES.get(patient_id.lower(), patient_id)
    alerts = PATIENT_MEDICAL_ALERTS.get(patient_id, []) or PATIENT_MEDICAL_ALERTS.get(canonical_id, [])
    if not alerts:
        for p in MOCK_PATIENTS:
            if p.mrn == patient_id or p.id == canonical_id or p.mrn == canonical_id:
                alerts = PATIENT_MEDICAL_ALERTS.get(p.id, [])
                break
    return {
        "patient_id": patient_id,
        "alert_count": len(alerts),
        "alerts": alerts,
    }


@router.get("/cache/{patient_id}", tags=["MDIN Interoperability - Cache"])
async def get_cached_context(patient_id: str):
    """Inspect in-memory synchronized clinical context cache for a given CareStack patient."""
    canonical_id = CARESTACK_PATIENT_ALIASES.get(patient_id.lower(), patient_id)
    cached = SYNCED_CLINICAL_CACHE.get(patient_id) or SYNCED_CLINICAL_CACHE.get(canonical_id)
    if not cached:
        raise HTTPException(status_code=404, detail=f"No cached clinical context for patient '{patient_id}'.")
    return cached


@router.get("/status", response_model=SyncStatusResponse, tags=["MDIN Interoperability - Status"])
async def get_carestack_status():
    """Check connectivity and synchronization status with CareStack PMS."""
    return SyncStatusResponse(
        status="connected",
        message="CareStack Interoperability Node is operational and synchronized with CareStack Web API V1.",
        synced_patients=len(MOCK_PATIENTS),
        last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
        carestack_connection=f"Active ({settings.CARESTACK_BASE_URL}) [Auth: VendorKey+AccountKey+AccountId]",
        ehr_connection=f"Active ({settings.FHIR_SERVER_URL})",
    )


@router.post("/sync", tags=["MDIN Interoperability - Sync"])
async def trigger_sync(sync_req: CareStackSyncRequest):
    """
    Trigger bi-directional reconciliation between CareStack PMS and Medical EHR.
    Synchronizes dental alerts to medical chart and medical alerts to dental chair.
    """
    for p in MOCK_PATIENTS:
        if p.id == sync_req.patient_id or p.mrn == sync_req.patient_id:
            return {
                "success": True,
                "synced_patient_id": p.id,
                "mrn": p.mrn,
                "sync_direction": sync_req.sync_direction,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {
                    "carestack_treatment_plan_count": len(p.active_treatment_plan),
                    "cross_specialty_flags_updated": True,
                },
            }

    raise HTTPException(status_code=404, detail=f"Patient {sync_req.patient_id} not found")
