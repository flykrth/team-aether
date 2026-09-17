"""
CareStack Dental Practice Management System (PMS) Mock Router mounted at /api/carestack.
Simulates CareStack appointment & check-in webhooks, demographic resolution against FHIR EHR,
in-memory clinical context caching, dental patient registration, and chart medical-alert writebacks.
"""

import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, Body, BackgroundTasks
from pydantic import BaseModel, Field

from ..schemas.carestack import (
    CareStackPatient,
    DentalProcedure,
    CareStackSyncRequest,
    SyncStatusResponse,
)
from ..config import settings
from .fhir_ehr_mock import FHIR_STORE, _calculate_similarity, _normalize_ref_id

router = APIRouter()

# In-memory synchronized clinical context cache
# Key: CareStack Patient ID -> Clinical Context & FHIR Bundle
SYNCED_CLINICAL_CACHE: Dict[str, Dict[str, Any]] = {}

# In-memory medical alerts chart write-back store
# Key: CareStack Patient ID -> List of Medical Alerts
PATIENT_MEDICAL_ALERTS: Dict[str, List[Dict[str, Any]]] = {}


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
    """Simulated CareStack Webhook payload for appointment creation or patient check-in."""
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


# Seed CareStack dental patients aligned with FHIR EHR personas
MOCK_PATIENTS: List[CareStackPatient] = [
    # Patient 1: John Doe (Warfarin / AFib / Penicillin Anaphylaxis) -> Planned Surgical Extraction
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
    # Patient 2: Jane Smith (Prosthetic Valve / Endocarditis Prophylaxis) -> Dental Cleaning & Crown
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
    # Patient 3: Robert Taylor (Type 2 Diabetes Mellitus / HbA1c 9.2%) -> Surgical Extraction
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
    # Legacy Phase 1 Patients (Preserved for compatibility)
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
]


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
            # DOB mismatch heavily penalizes
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

    # Find patient's conditions, medications, allergies, and observations
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


@router.post("/webhook")
async def carestack_webhook(event: CareStackWebhookEvent):
    """
    Simulates CareStack appointment creation or patient check-in webhook.
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
        # Avoid duplicate titles
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


@router.get("/patients", response_model=List[CareStackPatient])
async def list_carestack_patients(
    search: Optional[str] = Query(None, description="Search by name, CareStack ID, or MRN"),
):
    """
    Returns dental patients registered in the CareStack PMS, complete with active treatment plans.
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


@router.get("/patients/{patient_id}", response_model=CareStackPatient)
async def get_carestack_patient(patient_id: str):
    """Retrieve detailed dental record and treatment plan for a specific CareStack patient."""
    for p in MOCK_PATIENTS:
        if p.id == patient_id or p.mrn == patient_id:
            return p
    raise HTTPException(status_code=404, detail=f"CareStack patient '{patient_id}' not found")


@router.post("/patients/{patient_id}/medical-alerts")
async def write_medical_alert(
    patient_id: str,
    alert: MedicalAlertCreate,
):
    """
    Mock endpoint for writing high-priority medical flags back to CareStack's chart.
    Simulates bidirectional push of critical clinical contraindications from MDIN to CareStack PMS.
    """
    # Verify patient exists
    patient = None
    for p in MOCK_PATIENTS:
        if p.id == patient_id or p.mrn == patient_id:
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

    if patient.id not in PATIENT_MEDICAL_ALERTS:
        PATIENT_MEDICAL_ALERTS[patient.id] = []

    PATIENT_MEDICAL_ALERTS[patient.id].append(alert_record)

    return {
        "success": True,
        "message": f"Medical alert '{alert.title}' successfully written back to CareStack chart for {patient.first_name} {patient.last_name}.",
        "alert": alert_record,
    }


@router.get("/patients/{patient_id}/medical-alerts")
async def get_patient_medical_alerts(patient_id: str):
    """Retrieve all high-priority medical alerts written to CareStack chart for a patient."""
    alerts = PATIENT_MEDICAL_ALERTS.get(patient_id, [])
    # Also check if query is MRN
    if not alerts:
        for p in MOCK_PATIENTS:
            if p.mrn == patient_id:
                alerts = PATIENT_MEDICAL_ALERTS.get(p.id, [])
                break
    return {
        "patient_id": patient_id,
        "alert_count": len(alerts),
        "alerts": alerts,
    }


@router.get("/cache/{patient_id}")
async def get_cached_context(patient_id: str):
    """Inspect in-memory synchronized clinical context cache for a given CareStack patient."""
    if patient_id not in SYNCED_CLINICAL_CACHE:
        raise HTTPException(status_code=404, detail=f"No cached clinical context for patient '{patient_id}'.")
    return SYNCED_CLINICAL_CACHE[patient_id]


@router.get("/status", response_model=SyncStatusResponse)
async def get_carestack_status():
    """Check connectivity and synchronization status with CareStack PMS."""
    return SyncStatusResponse(
        status="connected",
        message="CareStack Interoperability Node is operational and synchronized.",
        synced_patients=len(MOCK_PATIENTS),
        last_sync_timestamp=datetime.now(timezone.utc).isoformat(),
        carestack_connection=f"Active ({settings.CARESTACK_BASE_URL})",
        ehr_connection=f"Active ({settings.FHIR_SERVER_URL})",
    )


@router.post("/sync")
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
