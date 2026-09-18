"""
Medical Clearance Service (The Digital Clearance Passport) - MDIN Step 11.
Orchestrates pre-screening automated medical-clearance requests between CareStack PMS
and HL7 FHIR R4 Medical EHR systems.
Adheres to HL7 FHIR R4 Task and CommunicationRequest resources.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
import httpx

from ..models.clearance import (
    AttendingPhysician,
    ClearanceDecision,
    ClearanceDecisionType,
    ClearanceRequestPayload,
    ClearanceStatus,
)
from ..services.concept_map import terminology_engine
from ..services.fhir_client import fhir_client, resolve_patient_aliases, normalize_ref_id
from ..services.document_generator import CLINICIAN_SARAH_JENKINS
from ..routers.carestack_mock import (
    MOCK_PATIENTS,
    MOCK_PROCEDURE_CODES,
    CARESTACK_PATIENT_ALIASES,
    PATIENT_MEDICAL_CLEARANCE_STATUS,
    PATIENT_MEDICAL_ALERTS,
    _find_carestack_patient,
)
from ..config import settings


# In-memory clearance passport registry cache
CLEARANCE_REGISTRY: Dict[str, ClearanceRequestPayload] = {}

# Known CDT descriptions and bleeding risk categories
CDT_CATALOG: Dict[str, Dict[str, str]] = {
    "D7140": {
        "description": "Extraction, erupted tooth or exposed root",
        "category": "Oral and Maxillofacial Surgery",
        "risk_level": "High Hemorrhage Hazard",
    },
    "D7210": {
        "description": "Extraction, erupted tooth requiring removal of bone and/or sectioning of tooth",
        "category": "Oral and Maxillofacial Surgery",
        "risk_level": "High Hemorrhage Hazard",
    },
    "D4341": {
        "description": "Periodontal scaling and root planing - four or more teeth per quadrant",
        "category": "Periodontics",
        "risk_level": "Moderate Hemorrhage Hazard",
    },
    "D1110": {
        "description": "Prophylaxis - adult (scaling/polishing, induces bacteremia)",
        "category": "Preventive",
        "risk_level": "Bacteremia / Low Bleeding Hazard",
    },
    "D2740": {
        "description": "Crown - porcelain/ceramic substrate",
        "category": "Restorative",
        "risk_level": "Low Bleeding Hazard",
    },
}

# Standard Synthetic Attending Physicians
PHYSICIAN_KENNETH_VANCE = AttendingPhysician(
    npi="1092837465",
    name="Dr. Kenneth Vance, MD",
    specialty="Cardiology",
    facility_name="Metropolitan Heart Center",
    fhir_endpoint="https://fhir.metroheart.org/r4",
    direct_email="k.vance@metroheart.org",
)

PHYSICIAN_ROBERT_VANCE = AttendingPhysician(
    npi="1774928103",
    name="Dr. Robert Vance, MD",
    specialty="Endocrinology & Rheumatology",
    facility_name="Metropolitan Bone & Joint Center",
    fhir_endpoint="https://fhir.metroheart.org/r4",
    direct_email="r.vance@metrohealth.org",
)

PHYSICIAN_ELENA_ROSTOVA = AttendingPhysician(
    npi="1841392019",
    name="Dr. Elena Rostova, MD",
    specialty="Internal Medicine",
    facility_name="Boston Metropolitan Medical Center",
    fhir_endpoint="https://fhir.metroheart.org/r4",
    direct_email="e.rostova@metrohealth.org",
)


class MedicalClearanceService:
    """
    Automates synthesis, dispatch, and decision recording for digital clearance passports.
    Integrates with ConceptMap terminology engine to detect clinical hazards and
    generates standards-compliant HL7 FHIR R4 Task and CommunicationRequest resources.
    """

    def __init__(self):
        self.registry = CLEARANCE_REGISTRY

    def _resolve_patient_info(
        self,
        patient_id: str,
        carestack_data: Optional[Dict[str, Any]] = None,
        ehr_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resolves unified demographics, conditions, and medications for the patient."""
        norm_id = normalize_ref_id(patient_id).lower()
        alias_keys = resolve_patient_aliases(norm_id) if norm_id else []

        # 1. Search CareStack
        cs_patient = None
        if carestack_data and carestack_data.get("id"):
            cs_patient = carestack_data
        else:
            for p in MOCK_PATIENTS:
                if (
                    p.id.lower() == norm_id
                    or p.mrn.lower() == norm_id
                    or any(k == p.id.lower() or k == p.mrn.lower() for k in alias_keys)
                ):
                    cs_patient = p
                    break

        # 2. Search FHIR Local Cache
        fhir_patient = None
        if ehr_data and ehr_data.get("resourceType") == "Patient":
            fhir_patient = ehr_data
        else:
            for p in fhir_client._local_cache.get("Patient", []):
                pid = p.get("id", "").lower()
                mrns = [i.get("value", "").lower() for i in p.get("identifier", [])]
                if (
                    pid == norm_id
                    or any(k == pid or k in mrns for k in alias_keys)
                ):
                    fhir_patient = p
                    break

        # Demographics synthesis
        name = "Unknown Patient"
        dob = "1970-01-01"
        mrn = "MRN-UNKNOWN"
        gender = "unknown"
        phone = "555-0100"
        dentist = CLINICIAN_SARAH_JENKINS["name"]

        if cs_patient:
            if hasattr(cs_patient, "first_name"):
                name = f"{cs_patient.first_name} {cs_patient.last_name}"
                dob = cs_patient.birth_date or dob
                mrn = cs_patient.mrn or mrn
                gender = cs_patient.gender or gender
                phone = cs_patient.phone or phone
                dentist = cs_patient.primary_dentist or dentist
            elif isinstance(cs_patient, dict):
                name = (
                    cs_patient.get("name")
                    or f"{cs_patient.get('first_name', '')} {cs_patient.get('last_name', '')}".strip()
                    or name
                )
                dob = cs_patient.get("birth_date") or cs_patient.get("dob") or dob
                mrn = cs_patient.get("mrn") or mrn
                gender = cs_patient.get("gender") or gender
                phone = cs_patient.get("phone") or phone
                dentist = cs_patient.get("primary_dentist") or dentist

        if fhir_patient and name == "Unknown Patient":
            names = fhir_patient.get("name", [])
            if names and isinstance(names[0], dict):
                given = " ".join(names[0].get("given", []))
                family = names[0].get("family", "")
                name = f"{given} {family}".strip()
            dob = fhir_patient.get("birthDate") or dob
            gender = fhir_patient.get("gender") or gender
            for ident in fhir_patient.get("identifier", []):
                if ident.get("value"):
                    mrn = ident.get("value")
                    break

        # Gather FHIR clinical records
        def _matches(ref_str: str) -> bool:
            if not ref_str:
                return False
            clean = normalize_ref_id(ref_str).lower()
            return clean == norm_id or any(k == clean for k in alias_keys)

        conditions = [
            c for c in fhir_client._local_cache.get("Condition", [])
            if _matches(c.get("subject", {}).get("reference", ""))
        ]
        medications = [
            m for m in fhir_client._local_cache.get("MedicationRequest", [])
            if _matches(m.get("subject", {}).get("reference", ""))
        ]
        allergies = [
            a for a in fhir_client._local_cache.get("AllergyIntolerance", [])
            if _matches(a.get("patient", {}).get("reference", ""))
        ]

        return {
            "name": name,
            "dob": dob,
            "mrn": mrn,
            "gender": gender,
            "phone": phone,
            "dentist": dentist,
            "conditions": conditions,
            "medications": medications,
            "allergies": allergies,
            "cs_patient": cs_patient,
            "fhir_patient": fhir_patient,
        }

    def _locate_attending_physician(
        self,
        conditions: List[Dict[str, Any]],
        medications: List[Dict[str, Any]],
        custom_physician: Optional[Dict[str, Any]] = None,
    ) -> AttendingPhysician:
        """
        Locates the patient's primary care provider or cardiologist from the synthetic FHIR record.
        Prioritizes cardiology for cardiovascular/anticoagulant profiles.
        """
        if custom_physician:
            return AttendingPhysician(**custom_physician)

        # Check conditions & medications
        all_condition_texts = [
            (c.get("code", {}).get("text") or "").lower()
            for c in conditions
        ]
        all_med_texts = [
            (m.get("medicationCodeableConcept", {}).get("text") or "").lower()
            for m in medications
        ]

        has_cardio = any(
            "atrial fibrillation" in t or "heart" in t or "valve" in t or "cardio" in t
            for t in all_condition_texts
        ) or any("warfarin" in t or "anticoagulant" in t or "coumadin" in t for t in all_med_texts)

        has_bone = any(
            "osteoporosis" in t or "mronj" in t or "bisphosphonate" in t
            for t in all_condition_texts
        ) or any("zoledronic" in t or "alendronate" in t for t in all_med_texts)

        if has_cardio:
            return PHYSICIAN_KENNETH_VANCE
        elif has_bone:
            return PHYSICIAN_ROBERT_VANCE
        else:
            return PHYSICIAN_KENNETH_VANCE

    def _synthesize_clinical_rationale(
        self,
        patient_name: str,
        cdt_code: str,
        proc_details: Dict[str, str],
        conditions: List[Dict[str, Any]],
        medications: List[Dict[str, Any]],
        allergies: List[Dict[str, Any]],
    ) -> str:
        """
        Automatically maps clinical rationale from the ConceptMap risk engine.
        Identifies active Warfarin, Atrial Fibrillation, and high bleeding hazard.
        """
        alerts = terminology_engine.synthesize_patient_risk(conditions, medications, allergies)
        alert_codes = {a.get("code") for a in alerts if a.get("code")}

        condition_labels = []
        for c in conditions:
            c_text = c.get("code", {}).get("text") or ""
            if not c_text and c.get("code", {}).get("coding"):
                c_text = c["code"]["coding"][0].get("display", "")
            if c_text:
                condition_labels.append(c_text)

        medication_labels = []
        for m in medications:
            m_text = m.get("medicationCodeableConcept", {}).get("text") or ""
            if not m_text and m.get("medicationCodeableConcept", {}).get("coding"):
                m_text = m["medicationCodeableConcept"]["coding"][0].get("display", "")
            if m_text:
                medication_labels.append(m_text)

        # Check for active anticoagulant & AFib
        is_warfarin = any("warfarin" in m.lower() for m in medication_labels) or "ACTIVE_ANTICOAGULANT" in alert_codes
        is_afib = any("atrial fibrillation" in c.lower() for c in condition_labels) or any(
            coding.get("code") in ("I48.91", "49436004")
            for c in conditions
            for coding in c.get("code", {}).get("coding", [])
        )
        is_hemorrhage_hazard = "CRITICAL_HEMORRHAGE_HAZARD" in alert_codes or (is_warfarin and is_afib)

        proc_name = proc_details.get("description", "Dental Procedure")
        risk_level = proc_details.get("risk_level", "Hemorrhage Hazard")

        if is_warfarin and is_afib:
            justification = (
                f"Patient {patient_name} has documented Atrial Fibrillation (ICD-10 I48.91) and is actively "
                f"prescribed Warfarin Sodium anticoagulant therapy (RxNorm 855332). Scheduled invasive surgical dental "
                f"procedure (CDT {cdt_code}: {proc_name}) presents a {risk_level} with substantial risk of uncontrolled "
                f"peri-operative hemorrhage. Formal medical clearance is requested to review anticoagulation protocol, "
                f"specify acceptable target INR threshold (standard: 2.0-2.5 prior to extraction), and provide directives "
                f"on temporary cessation or local hemostatic measures."
            )
        elif is_warfarin:
            justification = (
                f"Patient {patient_name} is on active Warfarin anticoagulant therapy. Scheduled invasive procedure "
                f"(CDT {cdt_code}: {proc_name}) presents elevated bleeding risk. Medical clearance requested to confirm "
                f"pre-operative INR safety range and local hemostatic guidance."
            )
        else:
            dx_str = ", ".join(condition_labels[:2]) if condition_labels else "systemic medical history"
            med_str = ", ".join(medication_labels[:2]) if medication_labels else "active pharmacotherapy"
            justification = (
                f"Patient {patient_name} with documented {dx_str} on {med_str} is scheduled for dental procedure "
                f"(CDT {cdt_code}: {proc_name}). Medical clearance is requested to evaluate hemodynamic tolerance, "
                f"pre-operative parameters, and safe clinical execution."
            )

        return justification

    def _generate_fhir_interop_resources(
        self,
        request_id: uuid.UUID,
        patient_id: str,
        patient_name: str,
        dentist_name: str,
        dentist_npi: str,
        physician: AttendingPhysician,
        cdt_code: str,
        clinical_justification: str,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Generates an interoperable FHIR Task (code: medical-clearance-request)
        linked to a FHIR CommunicationRequest.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        comm_req_id = f"comm-req-{request_id}"
        task_id = f"task-clearance-{request_id}"

        # HL7 FHIR R4 CommunicationRequest Resource
        communication_request = {
            "resourceType": "CommunicationRequest",
            "id": comm_req_id,
            "status": "active",
            "subject": {
                "reference": f"Patient/{patient_id}",
                "display": patient_name,
            },
            "sender": {
                "reference": f"Practitioner/{dentist_npi}",
                "display": dentist_name,
            },
            "recipient": [
                {
                    "reference": f"Practitioner/{physician.npi}",
                    "display": physician.name,
                }
            ],
            "payload": [
                {
                    "contentString": clinical_justification,
                }
            ],
            "reasonCode": [
                {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/sid/icd-10-cm",
                            "code": "I48.91",
                            "display": "Atrial Fibrillation",
                        }
                    ],
                    "text": "Atrial Fibrillation with active anticoagulation bleeding hazard",
                }
            ],
            "authoredOn": now_iso,
        }

        # HL7 FHIR R4 Task Resource (code: medical-clearance-request)
        fhir_task = {
            "resourceType": "Task",
            "id": task_id,
            "status": "requested",
            "intent": "order",
            "code": {
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/CodeSystem/task-code",
                        "code": "medical-clearance-request",
                        "display": "Pre-Operative Medical Clearance Request",
                    }
                ],
                "text": "Pre-Operative Medical Clearance Request",
            },
            "description": f"Pre-operative medical clearance evaluation for {patient_name} scheduled for CDT {cdt_code}",
            "focus": {
                "reference": f"CommunicationRequest/{comm_req_id}",
                "display": "Medical Clearance Justification & Directives",
            },
            "for": {
                "reference": f"Patient/{patient_id}",
                "display": patient_name,
            },
            "requester": {
                "reference": f"Practitioner/{dentist_npi}",
                "display": dentist_name,
            },
            "owner": {
                "reference": f"Practitioner/{physician.npi}",
                "display": physician.name,
            },
            "authoredOn": now_iso,
            "lastModified": now_iso,
        }

        return fhir_task, communication_request

    def create_clearance_passport(
        self,
        patient_id: str,
        cdt_code: str,
        carestack_data: Optional[Dict[str, Any]] = None,
        ehr_data: Optional[Dict[str, Any]] = None,
    ) -> ClearanceRequestPayload:
        """
        Creates and registers a Digital Clearance Passport:
        - Resolves demographics and clinical data.
        - Locates attending physician / cardiologist (e.g. Dr. Kenneth Vance, MD).
        - Synthesizes ConceptMap clinical rationale (Warfarin + AFib + bleeding risk).
        - Generates linked FHIR Task and CommunicationRequest resources.
        - Stores record as TRANSMITTED_TO_INBOX.
        """
        clean_cdt = (cdt_code or "D7140").upper().strip()
        proc_details = CDT_CATALOG.get(
            clean_cdt,
            {
                "description": "Dental Surgical / Invasive Procedure",
                "category": "Oral Surgery",
                "risk_level": "High Hemorrhage Hazard",
            },
        )

        patient_info = self._resolve_patient_info(patient_id, carestack_data, ehr_data)
        physician = self._locate_attending_physician(
            patient_info["conditions"],
            patient_info["medications"],
            custom_physician=ehr_data.get("physician") if ehr_data else None,
        )

        clinical_justification = self._synthesize_clinical_rationale(
            patient_name=patient_info["name"],
            cdt_code=clean_cdt,
            proc_details=proc_details,
            conditions=patient_info["conditions"],
            medications=patient_info["medications"],
            allergies=patient_info["allergies"],
        )

        # Dentist & Practice Info
        dentist_name = patient_info.get("dentist") or CLINICIAN_SARAH_JENKINS["name"]
        carestack_provider = {
            "dentist_name": dentist_name,
            "npi": CLINICIAN_SARAH_JENKINS["npi"],
            "practice_name": CLINICIAN_SARAH_JENKINS["clinic_name"],
            "phone": CLINICIAN_SARAH_JENKINS["phone"],
            "direct_email": CLINICIAN_SARAH_JENKINS["email"],
        }

        # Proposed procedures list
        scheduled_time = "2026-09-22T09:30:00Z"
        if patient_info["cs_patient"]:
            if hasattr(patient_info["cs_patient"], "next_appointment"):
                scheduled_time = patient_info["cs_patient"].next_appointment or scheduled_time
            elif isinstance(patient_info["cs_patient"], dict):
                scheduled_time = patient_info["cs_patient"].get("next_appointment") or scheduled_time

        proposed_procedures = [
            {
                "cdt_code": clean_cdt,
                "description": proc_details["description"],
                "category": proc_details["category"],
                "risk_level": proc_details["risk_level"],
                "scheduled_appointment": scheduled_time,
                "tooth_number": "30" if clean_cdt == "D7140" else "General",
            }
        ]

        requested_actions = [
            "Review coagulation protocol",
            "Specify target INR threshold",
            "Authorize temporary cessation of anticoagulant if applicable",
            "Confirm safe pre-procedural hemodynamic tolerance",
        ]

        request_uuid = uuid.uuid4()
        fhir_task, fhir_comm = self._generate_fhir_interop_resources(
            request_id=request_uuid,
            patient_id=patient_id,
            patient_name=patient_info["name"],
            dentist_name=dentist_name,
            dentist_npi=CLINICIAN_SARAH_JENKINS["npi"],
            physician=physician,
            cdt_code=clean_cdt,
            clinical_justification=clinical_justification,
        )

        passport = ClearanceRequestPayload(
            request_id=request_uuid,
            patient_id=patient_id,
            patient_demographics={
                "name": patient_info["name"],
                "dob": patient_info["dob"],
                "mrn": patient_info["mrn"],
                "gender": patient_info["gender"],
                "phone": patient_info["phone"],
            },
            carestack_provider=carestack_provider,
            physician=physician,
            proposed_procedures=proposed_procedures,
            clinical_justification=clinical_justification,
            requested_actions=requested_actions,
            status=ClearanceStatus.TRANSMITTED_TO_INBOX.value,
            conditions_or_notes=None,
            updated_at=datetime.now(timezone.utc),
            decision=None,
            fhir_task=fhir_task,
            fhir_communication_request=fhir_comm,
        )

        # Store in registry
        self.registry[str(request_uuid)] = passport
        return passport

    def get_clearance_by_id(self, request_id: str) -> Optional[ClearanceRequestPayload]:
        """Retrieves a single clearance passport request by its UUID string."""
        return self.registry.get(str(request_id).strip())

    def get_clearance_by_patient(self, patient_id: str) -> List[ClearanceRequestPayload]:
        """Retrieves all clearance requests associated with a patient, matching aliases."""
        clean_id = normalize_ref_id(patient_id).lower()
        alias_keys = set(resolve_patient_aliases(clean_id)) if clean_id else {clean_id}
        alias_keys.add(clean_id)

        matching = []
        for req in self.registry.values():
            req_pid = normalize_ref_id(req.patient_id).lower()
            req_mrn = normalize_ref_id(req.patient_demographics.get("mrn", "")).lower()
            if (
                req_pid in alias_keys
                or req_mrn in alias_keys
                or any(k == req_pid or k == req_mrn for k in alias_keys)
            ):
                matching.append(req)

        return matching

    def record_physician_decision(
        self,
        decision: ClearanceDecision,
    ) -> ClearanceRequestPayload:
        """
        Records attending physician sign-off decision on a clearance passport.
        Updates request status, notes, coagulation parameters, and timestamps.
        If APPROVED or APPROVED_WITH_CONDITIONS, triggers the mock CareStack
        notification webhook: POST /api/carestack/patients/{id}/medical-clearance-status.
        """
        req_id = str(decision.request_id).strip()
        request = self.get_clearance_by_id(req_id)
        if not request:
            raise KeyError(f"Clearance request '{decision.request_id}' not found in registry")

        # Update status and decision
        request.status = decision.decision
        request.decision = decision
        request.conditions_or_notes = decision.physician_notes
        request.updated_at = datetime.now(timezone.utc)

        # Update FHIR task status
        if request.fhir_task:
            if decision.decision in (ClearanceDecisionType.APPROVED.value, ClearanceDecisionType.APPROVED_WITH_CONDITIONS.value):
                request.fhir_task["status"] = "completed"
            elif decision.decision == ClearanceDecisionType.REJECTED.value:
                request.fhir_task["status"] = "rejected"
            request.fhir_task["lastModified"] = datetime.now(timezone.utc).isoformat()

        # Update CareStack Mock stores directly in-process
        canonical_id = CARESTACK_PATIENT_ALIASES.get(
            request.patient_id.lower(), request.patient_id
        )
        patient = _find_carestack_patient(request.patient_id)
        if patient:
            canonical_id = patient.id

        is_cleared = decision.decision in (ClearanceDecisionType.APPROVED.value, ClearanceDecisionType.APPROVED_WITH_CONDITIONS.value)
        coag = decision.coagulation_parameters or {}
        inr_range = coag.get("target_inr_range", "2.0-2.5")

        medical_clearance_record = {
            "request_id": str(request.request_id),
            "status": decision.decision,
            "decision": decision.decision,
            "is_cleared_for_surgery": is_cleared,
            "physician_notes": decision.physician_notes,
            "coagulation_parameters": coag,
            "signed_by": decision.signed_by,
            "timestamp": decision.timestamp.isoformat(),
        }
        if patient:
            setattr(patient, "medical_clearance", medical_clearance_record)

        webhook_payload = {
            "request_id": str(request.request_id),
            "decision": decision.decision,
            "status": decision.decision,
            "physician_name": decision.signed_by,
            "signed_by": decision.signed_by,
            "physician_notes": decision.physician_notes,
            "coagulation_parameters": decision.coagulation_parameters,
            "clearance_passport_url": f"/api/clearance/{request.request_id}",
            "timestamp": decision.timestamp.isoformat(),
            "medical_clearance": medical_clearance_record,
        }

        webhook_record = {
            **webhook_payload,
            "patient_id": request.patient_id,
            "canonical_patient_id": canonical_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }

        # Persist in PATIENT_MEDICAL_CLEARANCE_STATUS
        for k in {request.patient_id, canonical_id}:
            if k:
                if k not in PATIENT_MEDICAL_CLEARANCE_STATUS:
                    PATIENT_MEDICAL_CLEARANCE_STATUS[k] = []
                PATIENT_MEDICAL_CLEARANCE_STATUS[k].append(webhook_record)

        # Persist in PATIENT_MEDICAL_ALERTS: "Cardiology Clearance Received: Target INR 2.0-2.5. Approved by Dr. Vance."
        if is_cleared:
            alert_title = f"MEDICAL CLEARANCE — Cardiology Clearance Received: Target INR {inr_range}. Approved by Dr. Vance."
        else:
            alert_title = f"MEDICAL CLEARANCE — Cardiology Clearance Rejected: Denied by Dr. Vance."

        alert_record = {
            "alert_id": f"ALT-CLR-{uuid.uuid4().hex[:6].upper()}",
            "patient_id": canonical_id,
            "patient_name": request.patient_demographics.get("name", "Patient"),
            "alert_type": "info" if decision.decision == "APPROVED" else "warning" if is_cleared else "critical",
            "category": "clearance",
            "title": alert_title,
            "details": f"Clearance sign-off by {decision.signed_by}. Directive: {decision.physician_notes}",
            "source": "Digital Clearance Passport Engine",
            "action_required": not is_cleared,
            "status": "posted_to_chart",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        for k in {request.patient_id, canonical_id}:
            if k:
                if k not in PATIENT_MEDICAL_ALERTS:
                    PATIENT_MEDICAL_ALERTS[k] = []
                PATIENT_MEDICAL_ALERTS[k].append(alert_record)

        return request


medical_clearance_service = MedicalClearanceService()
