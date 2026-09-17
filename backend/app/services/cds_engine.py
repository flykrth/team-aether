"""
Clinical Decision Support (CDS) Engine for MDIN - Phase 4.
Evaluates CDS Hooks v1.0/v2.0 requests against the FHIR Terminology Service
and simulated EHR records to produce real-time, actionable decision support cards.
"""

import re
from typing import List, Optional, Dict, Any, Tuple, Set

from ..models.cds_hooks import (
    CDSRequest,
    CDSResponse,
    CDSCard,
    CDSSource,
    CDSSuggestion,
    CDSSuggestionAction,
    CDSLink,
)
from .concept_map import terminology_engine


def _normalize_ref_id(ref_or_id: str) -> str:
    """Extract clean resource ID from reference string like 'Patient/patient-001' or 'patient-001'."""
    if not ref_or_id:
        return ""
    if "/" in str(ref_or_id):
        return str(ref_or_id).split("/")[-1].strip()
    return str(ref_or_id).strip()


# CDT Dental Procedure Code Classifications
EXTRACTION_CODES: Set[str] = {
    "D7140",  # Extraction, erupted tooth or exposed root
    "D7210",  # Surgical removal of erupted tooth
    "D7220",  # Removal of impacted tooth - soft tissue
    "D7230",  # Removal of impacted tooth - partially bony
    "D7240",  # Removal of impacted tooth - completely bony
    "D7250",  # Surgical removal of residual tooth roots
}

DEEP_SCALING_CODES: Set[str] = {
    "D4341",  # Periodontal scaling and root planing - 4+ teeth per quadrant
    "D4342",  # Periodontal scaling and root planing - 1 to 3 teeth
    "D4346",  # Scaling in presence of generalized moderate/severe gingival inflammation
    "D4355",  # Full mouth debridement to enable comprehensive oral evaluation
}

MUCOSAL_BLEEDING_PROPHYLAXIS_CODES: Set[str] = EXTRACTION_CODES | DEEP_SCALING_CODES | {
    "D1110",  # Prophylaxis - adult (dental cleaning / scaling)
    "D4910",  # Periodontal maintenance
    "D4210",  # Gingivectomy or gingivoplasty - 4+ teeth
    "D4240",  # Gingival flap procedure
    "D4260",  # Osseous surgery
}

LOW_RISK_CODES: Set[str] = {
    "D0120",  # Periodic oral evaluation
    "D0140",  # Limited oral evaluation - problem focused
    "D0150",  # Comprehensive oral evaluation
    "D0210",  # Intraoral - comprehensive series of radiographic images
    "D0220",  # Intraoral - periapical first radiographic image
    "D0272",  # Bitewings - two radiographic images
    "D0274",  # Bitewings - four radiographic images
    "D1206",  # Topical application of fluoride varnish
    "D1351",  # Sealant - per tooth
}


class CDSEngine:
    """
    Evaluates CDS Hooks requests (patient-view and order-select) against patient records,
    semantic terminology mappings, and clinical safety rules.
    """

    def __init__(self):
        self.terminology = terminology_engine

    # --- Prefetch Extraction and Fallback Lookup ---

    def _extract_resource_list(self, obj: Any) -> List[Dict[str, Any]]:
        """Extract a list of FHIR resources from a prefetch entry (Bundle, list, or single resource)."""
        if not obj:
            return []
        if isinstance(obj, dict):
            if obj.get("resourceType") == "Bundle":
                return [
                    entry.get("resource")
                    for entry in obj.get("entry", [])
                    if isinstance(entry, dict) and entry.get("resource")
                ]
            if "resourceType" in obj:
                return [obj]
            return []
        if isinstance(obj, list):
            extracted = []
            for item in obj:
                if isinstance(item, dict):
                    if "resource" in item and isinstance(item["resource"], dict):
                        extracted.append(item["resource"])
                    elif "resourceType" in item:
                        extracted.append(item)
            return extracted
        return []

    def resolve_patient_records(
        self, request: CDSRequest
    ) -> Tuple[
        Optional[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:
        """
        Extracts patient, conditions, medications, allergies, and observations.
        Prioritizes prefetch payloads to eliminate round-trip latency; falls back
        to simulated FHIR EHR store when prefetch is missing or incomplete.
        """
        prefetch = request.prefetch or {}
        context = request.context or {}
        patient_id = (
            context.get("patientId")
            or context.get("patient")
            or context.get("patient_id")
            or ""
        )
        norm_patient_id = _normalize_ref_id(str(patient_id)).lower()

        # 1. Try to extract from prefetch directly
        patient: Optional[Dict[str, Any]] = None
        conditions: List[Dict[str, Any]] = []
        medications: List[Dict[str, Any]] = []
        allergies: List[Dict[str, Any]] = []
        observations: List[Dict[str, Any]] = []

        if prefetch:
            # Patient
            raw_pt = prefetch.get("patient") or prefetch.get("Patient")
            pt_list = self._extract_resource_list(raw_pt)
            if pt_list:
                patient = pt_list[0]

            # Conditions
            raw_cond = prefetch.get("conditions") or prefetch.get("condition") or prefetch.get("Condition")
            conditions = self._extract_resource_list(raw_cond)

            # Medications
            raw_meds = (
                prefetch.get("medications")
                or prefetch.get("medication")
                or prefetch.get("medicationRequests")
                or prefetch.get("MedicationRequest")
            )
            medications = self._extract_resource_list(raw_meds)

            # Allergies
            raw_algs = (
                prefetch.get("allergies")
                or prefetch.get("allergy")
                or prefetch.get("allergyIntolerances")
                or prefetch.get("AllergyIntolerance")
            )
            allergies = self._extract_resource_list(raw_algs)

            # Observations
            raw_obs = prefetch.get("observations") or prefetch.get("observation") or prefetch.get("Observation")
            observations = self._extract_resource_list(raw_obs)

        # 2. Fallback to simulated FHIR EHR store if prefetch is missing or incomplete
        from ..routers.fhir_ehr_mock import FHIR_STORE

        matching_keys = [norm_patient_id] if norm_patient_id else []

        if not patient and norm_patient_id:
            for p in FHIR_STORE["Patient"]:
                pid = p.get("id", "").lower()
                mrns = [ident.get("value", "").lower() for ident in p.get("identifier", [])]
                if norm_patient_id == pid or norm_patient_id in mrns or any(norm_patient_id in m for m in mrns) or (norm_patient_id and norm_patient_id in pid):
                    patient = p
                    matching_keys.append(pid)
                    matching_keys.extend(mrns)
                    break

        def _matches_subject(ref_str: str) -> bool:
            if not ref_str:
                return False
            clean = _normalize_ref_id(ref_str).lower()
            return any(k == clean or (k and k in clean) or (clean and clean in k) for k in matching_keys)

        if not conditions and matching_keys:
            conditions = [
                c for c in FHIR_STORE["Condition"]
                if _matches_subject(c.get("subject", {}).get("reference", ""))
            ]

        if not medications and matching_keys:
            medications = [
                m for m in FHIR_STORE["MedicationRequest"]
                if _matches_subject(m.get("subject", {}).get("reference", ""))
            ]

        if not allergies and matching_keys:
            allergies = [
                a for a in FHIR_STORE["AllergyIntolerance"]
                if _matches_subject(a.get("patient", {}).get("reference", ""))
            ]

        if not observations and matching_keys:
            observations = [
                o for o in FHIR_STORE["Observation"]
                if _matches_subject(o.get("subject", {}).get("reference", ""))
            ]

        return patient, conditions, medications, allergies, observations

    # --- Procedure Extraction ---

    def extract_procedure_codes(self, request: CDSRequest) -> Set[str]:
        """Extracts dental procedure codes (e.g. D7140) from the hook context."""
        context = request.context or {}
        codes: Set[str] = set()

        # Check 'selections' (CDS Hooks standard list)
        selections = context.get("selections") or []
        if isinstance(selections, list):
            for s in selections:
                if isinstance(s, str):
                    clean = s.strip().upper()
                    # Extract any CDT-like token (D followed by 4 digits) or use whole string
                    cdt_match = re.search(r"D\d{4}", clean)
                    if cdt_match:
                        codes.add(cdt_match.group(0))
                    else:
                        codes.add(clean)
                elif isinstance(s, dict):
                    code_val = s.get("code") or s.get("id")
                    if code_val:
                        codes.add(str(code_val).strip().upper())

        # Check 'procedureCode' or 'procedure'
        direct_proc = context.get("procedureCode") or context.get("procedure")
        if direct_proc:
            if isinstance(direct_proc, str):
                cdt_match = re.search(r"D\d{4}", direct_proc.strip().upper())
                if cdt_match:
                    codes.add(cdt_match.group(0))
                else:
                    codes.add(direct_proc.strip().upper())
            elif isinstance(direct_proc, dict):
                code_val = direct_proc.get("code")
                if code_val:
                    codes.add(str(code_val).strip().upper())

        # Check 'draftOrders' Bundle
        draft_orders = context.get("draftOrders")
        if isinstance(draft_orders, dict):
            for entry in draft_orders.get("entry", []):
                res = entry.get("resource", {})
                # ServiceRequest, ProcedureRequest, or DeviceRequest
                code_obj = res.get("code", {})
                for coding in code_obj.get("coding", []):
                    c = coding.get("code")
                    if c:
                        codes.add(str(c).strip().upper())

        # Check 'procedures' list
        procedures = context.get("procedures") or []
        if isinstance(procedures, list):
            for p in procedures:
                if isinstance(p, dict) and p.get("code"):
                    codes.add(str(p["code"]).strip().upper())
                elif isinstance(p, str):
                    codes.add(p.strip().upper())

        return codes

    # --- Service 1: Patient-View Hook Evaluation ---

    def evaluate_patient_view(self, request: CDSRequest) -> CDSResponse:
        """
        Service 1: patient-view-service (patient-view-alert)
        Trigger: Opening patient chart in CareStack.
        Logic: Checks translated conditions/medications. If high-risk systemic conditions exist
        (e.g., diabetes, valve replacement, chronic kidney disease, osteoporosis/bisphosphonate),
        returns an info or warning summary card highlighting key systemic health alerts.
        """
        patient, conditions, medications, allergies, observations = self.resolve_patient_records(request)

        # Synthesize alerts using FHIRTerminologyEngine
        synthesized_alerts = self.terminology.synthesize_patient_risk(conditions, medications, allergies)
        alert_codes: Set[str] = {a.get("code") for a in synthesized_alerts if a.get("code")}

        cards: List[CDSCard] = []

        # Helper to inspect text and codings directly for broad coverage
        all_condition_texts = [
            (c.get("code", {}).get("text") or "").lower() for c in conditions
        ]
        all_condition_codes = {
            coding.get("code")
            for c in conditions
            for coding in c.get("code", {}).get("coding", [])
            if coding.get("code")
        }

        all_med_texts = [
            (m.get("medicationCodeableConcept", {}).get("text") or "").lower() for m in medications
        ]
        all_med_codes = {
            coding.get("code")
            for m in medications
            for coding in m.get("medicationCodeableConcept", {}).get("coding", [])
            if coding.get("code")
        }

        all_allergy_texts = [
            (a.get("code", {}).get("text") or "").lower() for a in allergies
        ]
        all_allergy_codes = {
            coding.get("code")
            for a in allergies
            for coding in a.get("code", {}).get("coding", [])
            if coding.get("code")
        }

        # 1. Diabetes Alert (Type 2 Diabetes Mellitus / Glycemic Control)
        has_diabetes = bool(
            "DELAYED_HEALING_RISK" in alert_codes
            or {"73211009", "44054006", "E11.9", "E11"} & all_condition_codes
            or any("diabetes" in t for t in all_condition_texts)
        )

        if has_diabetes:
            # Look for recent HbA1c observation
            hba1c_val: Optional[float] = None
            for obs in observations:
                obs_codings = obs.get("code", {}).get("coding", [])
                obs_text = (obs.get("code", {}).get("text") or "").lower()
                if any(c.get("code") == "4548-4" for c in obs_codings) or "hba1c" in obs_text or "hemoglobin a1c" in obs_text:
                    vq = obs.get("valueQuantity", {})
                    if "value" in vq:
                        hba1c_val = float(vq["value"])
                        break

            if hba1c_val and hba1c_val >= 8.0:
                cards.append(
                    CDSCard(
                        summary=f"WARNING: Severe Glycemic Dysregulation (HbA1c {hba1c_val}%) — Delayed Surgical Healing",
                        indicator="warning",
                        detail=(
                            f"Most recent HbA1c is {hba1c_val}% (LOINC: 4548-4). Markedly elevated glycemia severely "
                            "impairs collagen synthesis, neutrophil chemotaxis, and angiogenesis, causing significant "
                            "post-extraction socket healing delays, susceptibility to alveolar osteitis, and heightened "
                            "periodontal breakdown. Recommend morning appointment scheduling and post-op chlorhexidine rinse."
                        ),
                        source=CDSSource(
                            label="Endocrine-Dental Correlation Module",
                            url="https://diabetes.org",
                        ),
                        suggestions=[
                            CDSSuggestion(
                                label="Order Chlorhexidine 0.12% post-op rinse and morning surgery scheduling",
                                uuid="sugg-dm-001",
                                actions=[
                                    CDSSuggestionAction(
                                        type="create",
                                        description="Add antimicrobial mouthrinse protocol to CareStack chart",
                                    )
                                ],
                            )
                        ],
                    )
                )
            else:
                cards.append(
                    CDSCard(
                        summary="Systemic Alert: Type 2 Diabetes Mellitus (Delayed Healing Risk)",
                        indicator="warning",
                        detail=(
                            "Patient has documented Type 2 Diabetes Mellitus. Elevated blood glucose impairs wound healing "
                            "and increases risk of periodontal breakdown and post-restorative infection. "
                            "Recommend verifying latest HbA1c and considering morning scheduling for extensive procedures."
                        ),
                        source=CDSSource(
                            label="Endocrine-Dental Correlation Module",
                            url="https://diabetes.org",
                        ),
                    )
                )

        # 2. Anticoagulant Therapy Alert (Warfarin / Bleeding Risk)
        has_anticoagulant = bool(
            "ACTIVE_ANTICOAGULANT" in alert_codes
            or "CRITICAL_HEMORRHAGE_HAZARD" in alert_codes
            or "855332" in all_med_codes
            or any("warfarin" in t for t in all_med_texts)
        )

        if has_anticoagulant:
            cards.append(
                CDSCard(
                    summary="Systemic Alert: Active Anticoagulant Therapy (Warfarin Sodium)",
                    indicator="warning",
                    detail=(
                        "Patient is actively prescribed Warfarin Sodium 5 MG (RxNorm: 855332) for Atrial Fibrillation. "
                        "Carries substantial bleeding hazard during invasive surgical or deep periodontal procedures. "
                        "Verify current INR (<3.0 within 24-72 hours) and ensure local hemostatic agents are readily prepared."
                    ),
                    source=CDSSource(
                        label="MDIN Hematology Surveillance Node",
                        url="https://www.heart.org",
                    ),
                    links=[
                        CDSLink(
                            label="ADA Anticoagulant Management",
                            url="https://www.ada.org",
                            type="absolute",
                        )
                    ],
                )
            )

        # 3. Prosthetic Cardiac Valve / Infective Endocarditis
        has_valve = bool(
            "AHA_PROPHYLAXIS_REQUIRED" in alert_codes
            or "PROPHYLAXIS_PENICILLIN_CONFLICT" in alert_codes
            or {"315215002", "I33.0"} & all_condition_codes
            or any("prosthetic" in t or "valve" in t or "endocarditis" in t for t in all_condition_texts)
        )

        has_penicillin_allergy = bool(
            "CONTRAINDICATION_PENICILLIN" in alert_codes
            or "PROPHYLAXIS_PENICILLIN_CONFLICT" in alert_codes
            or "70618001" in all_allergy_codes
            or any("penicillin" in t for t in all_allergy_texts)
        )

        if has_valve:
            if has_penicillin_allergy:
                cards.append(
                    CDSCard(
                        summary="Systemic Alert: Prosthetic Valve with Penicillin Allergy (AHA Prophylaxis)",
                        indicator="warning",
                        detail=(
                            "Patient has documented Prosthetic Cardiac Valve (SNOMED: 315215002) and severe Penicillin allergy. "
                            "AHA Guidelines mandate prophylactic antibiotic premedication 30-60 minutes prior to invasive dental "
                            "manipulation. Beta-lactams are strictly contraindicated. Prescribe Clindamycin 600mg or Azithromycin 500mg PO."
                        ),
                        source=CDSSource(
                            label="AHA Dental Antibiotic Prophylaxis Protocol",
                            url="https://www.heart.org",
                        ),
                        suggestions=[
                            CDSSuggestion(
                                label="Prescribe Clindamycin 600mg PO 1 Hour Pre-Op",
                                uuid="sugg-clinda-pv-001",
                                actions=[
                                    CDSSuggestionAction(
                                        type="create",
                                        description="Add non-beta-lactam AHA Prophylaxis regimen to CareStack Rx",
                                    )
                                ],
                            )
                        ],
                    )
                )
            else:
                cards.append(
                    CDSCard(
                        summary="Systemic Alert: Prosthetic Heart Valve (AHA Antibiotic Prophylaxis Required)",
                        indicator="warning",
                        detail=(
                            "Patient has documented Prosthetic Cardiac Valve (SNOMED: 315215002). AHA Guidelines mandate "
                            "prophylactic antibiotic premedication (Amoxicillin 2g PO 30-60 minutes prior) for dental "
                            "procedures involving mucosal bleeding or manipulation of gingival tissue."
                        ),
                        source=CDSSource(
                            label="AHA Dental Antibiotic Prophylaxis Protocol",
                            url="https://www.heart.org",
                        ),
                        suggestions=[
                            CDSSuggestion(
                                label="Prescribe Amoxicillin 2g PO 1 Hour Pre-Op",
                                uuid="sugg-amox-pv-001",
                                actions=[
                                    CDSSuggestionAction(
                                        type="create",
                                        description="Add AHA Prophylaxis regimen to CareStack Rx",
                                    )
                                ],
                            )
                        ],
                    )
                )

        # 4. Bisphosphonate Therapy / MRONJ Risk
        has_bisphosphonate = bool(
            "MRONJ_RISK_ELEVATED" in alert_codes
            or {"64859006", "M81.0"} & all_condition_codes
            or any("bisphosphonate" in t or "osteoporosis" in t or "zoledronic" in t or "mronj" in t for t in all_condition_texts)
            or any("bisphosphonate" in t or "zoledronic" in t for t in all_med_texts)
        )

        if has_bisphosphonate:
            cards.append(
                CDSCard(
                    summary="CRITICAL: Medication-Related Osteonecrosis of the Jaw (MRONJ) Risk",
                    indicator="critical",
                    detail=(
                        "Patient is currently receiving IV Bisphosphonate therapy (Zoledronic Acid) for Osteoporosis. "
                        "High risk of osteonecrosis of the jaw post-extraction. Recommend conservative endodontic therapy "
                        "or mandatory medical oncology clearance with chlorhexidine pre-rinse."
                    ),
                    source=CDSSource(
                        label="MDIN Clinical Safety Engine",
                        url="https://www.aaoms.org/practice-resources/clinical-resources/mronj",
                    ),
                    suggestions=[
                        CDSSuggestion(
                            label="Request Physician Clearance & Modify Plan to Endodontic Preservation",
                            uuid="sugg-mronj-pv-001",
                            actions=[
                                CDSSuggestionAction(
                                    type="create",
                                    description="Consultation note sent to treating oncologist via FHIR CommunicationRequest",
                                )
                            ],
                        )
                    ],
                    links=[
                        CDSLink(
                            label="AAOMS MRONJ Guidelines",
                            url="https://www.aaoms.org",
                            type="absolute",
                        )
                    ],
                )
            )

        # 5. Severe Latex Allergy
        has_latex_allergy = bool(
            "ALERT_LATEX_ALLERGY" in alert_codes
            or "300916003" in all_allergy_codes
            or any("latex" in t for t in all_allergy_texts)
        )

        if has_latex_allergy:
            cards.append(
                CDSCard(
                    summary="ALERT: Documented Severe Latex Allergy",
                    indicator="warning",
                    detail="Patient has documented anaphylactic hypersensitivity to Natural Rubber Latex. Ensure latex-free dental dams, gloves, and prophylaxis cups.",
                    source=CDSSource(label="EHR Allergy Intolerance Sync"),
                )
            )

        # 6. Chronic Kidney Disease
        has_ckd = bool(
            {"N18.9", "N18.3", "N18", "709044004"} & all_condition_codes
            or any("kidney disease" in t or "renal disease" in t or "renal failure" in t for t in all_condition_texts)
        )

        if has_ckd:
            cards.append(
                CDSCard(
                    summary="Systemic Alert: Chronic Kidney Disease - Renal Dosing Precautions",
                    indicator="warning",
                    detail=(
                        "Patient has documented Chronic Kidney Disease. Adjust dosage of renally eliminated medications "
                        "(e.g., amoxicillin, cephalosporins). Strictly avoid NSAIDs; acetaminophen is preferred for mild-to-moderate dental analgesia."
                    ),
                    source=CDSSource(label="MDIN Nephrology Advisor", url="https://www.kidney.org"),
                )
            )

        # 7. Penicillin Allergy Standalone (if not already reported with valve)
        if has_penicillin_allergy and not has_valve:
            cards.append(
                CDSCard(
                    summary="CRITICAL: Severe Penicillin Allergy (Anaphylaxis Risk)",
                    indicator="critical",
                    detail=(
                        "Patient has documented severe allergy to Penicillin (SNOMED: 70618001) with manifestation of Anaphylaxis. "
                        "Strict contraindication for all beta-lactams (Amoxicillin, Penicillin V). "
                        "Prescribe Clindamycin 600mg or Azithromycin 500mg if antibiotic required."
                    ),
                    source=CDSSource(label="FHIR AllergyIntolerance Stream"),
                )
            )

        # Return empty list [] if clean / low risk to prevent clinical alert fatigue
        return CDSResponse(cards=cards)

    # --- Service 2: Order-Select Hook Evaluation ---

    def evaluate_order_select(self, request: CDSRequest) -> CDSResponse:
        """
        Service 2: order-select-service (order-select-contraindication)
        Trigger: Dentist selects or drafts a dental procedure (e.g., CDT code D7140, D7210, D4341).
        Logic:
          a) High Hemorrhage Check: If procedure involves bleeding (Extraction/Deep Scaling)
             AND patient is on Warfarin/anticoagulant therapy:
             - Generate a critical card.
             - Summary: "High Bleeding Hazard: Patient on Anticoagulant (Warfarin)".
             - Detail: Clinical guidance citing AHA/ADA guidelines: Verify latest INR (target 2.0-3.0
               before invasive dental surgery). Prepare local hemostatic agents.
             - Suggestion: Add action to order INR Lab Verification or request MD consult.
          b) Antibiotic Prophylaxis Check: If procedure involves mucosal bleeding AND patient has Prosthetic Heart Valve:
             - If allergic to Penicillin: return warning or critical card specifying:
               "AHA Prophylaxis Alert: Requires Clindamycin 600mg or Azithromycin 500mg PO 1h prior. Penicillin/Amoxicillin contraindicated."
             - If non-allergic: return card indicating standard Amoxicillin prophylaxis protocol.
          c) Low Risk / Clean: Return empty cards list [] to prevent clinical alert fatigue.
        """
        procedure_codes = self.extract_procedure_codes(request)
        patient, conditions, medications, allergies, observations = self.resolve_patient_records(request)

        # If no explicit procedure code is found in context, check for scheduled procedures in appointment/context
        if not procedure_codes:
            context = request.context or {}
            appointment = context.get("appointment") or {}
            for p in appointment.get("procedures", []):
                if isinstance(p, dict) and p.get("code"):
                    procedure_codes.add(str(p["code"]).strip().upper())

        # Synthesize patient risk
        synthesized_alerts = self.terminology.synthesize_patient_risk(conditions, medications, allergies)
        alert_codes: Set[str] = {a.get("code") for a in synthesized_alerts if a.get("code")}

        all_med_texts = [(m.get("medicationCodeableConcept", {}).get("text") or "").lower() for m in medications]
        all_med_codes = {
            coding.get("code")
            for m in medications
            for coding in m.get("medicationCodeableConcept", {}).get("coding", [])
            if coding.get("code")
        }

        all_condition_texts = [(c.get("code", {}).get("text") or "").lower() for c in conditions]
        all_condition_codes = {
            coding.get("code")
            for c in conditions
            for coding in c.get("code", {}).get("coding", [])
            if coding.get("code")
        }

        all_allergy_texts = [(a.get("code", {}).get("text") or "").lower() for a in allergies]
        all_allergy_codes = {
            coding.get("code")
            for a in allergies
            for coding in a.get("code", {}).get("coding", [])
            if coding.get("code")
        }

        # Check procedure categories
        is_extraction = bool(procedure_codes & EXTRACTION_CODES or any(c.startswith("D7") for c in procedure_codes))
        is_deep_scaling = bool(procedure_codes & DEEP_SCALING_CODES)
        is_bleeding_procedure = is_extraction or is_deep_scaling
        is_mucosal_bleeding = is_bleeding_procedure or bool(procedure_codes & MUCOSAL_BLEEDING_PROPHYLAXIS_CODES)

        # Patient clinical status flags
        has_anticoagulant = bool(
            "ACTIVE_ANTICOAGULANT" in alert_codes
            or "CRITICAL_HEMORRHAGE_HAZARD" in alert_codes
            or "855332" in all_med_codes
            or any("warfarin" in t for t in all_med_texts)
        )

        has_prosthetic_valve = bool(
            "AHA_PROPHYLAXIS_REQUIRED" in alert_codes
            or "PROPHYLAXIS_PENICILLIN_CONFLICT" in alert_codes
            or {"315215002", "I33.0"} & all_condition_codes
            or any("prosthetic" in t or "valve" in t or "endocarditis" in t for t in all_condition_texts)
        )

        has_penicillin_allergy = bool(
            "CONTRAINDICATION_PENICILLIN" in alert_codes
            or "PROPHYLAXIS_PENICILLIN_CONFLICT" in alert_codes
            or "70618001" in all_allergy_codes
            or any("penicillin" in t for t in all_allergy_texts)
        )

        has_bisphosphonate = bool(
            "MRONJ_RISK_ELEVATED" in alert_codes
            or {"64859006", "M81.0"} & all_condition_codes
            or any("bisphosphonate" in t or "zoledronic" in t or "mronj" in t for t in all_condition_texts)
            or any("bisphosphonate" in t or "zoledronic" in t for t in all_med_texts)
        )

        cards: List[CDSCard] = []

        # --- Rule a: High Hemorrhage Check ---
        if is_bleeding_procedure and has_anticoagulant:
            cards.append(
                CDSCard(
                    summary="High Bleeding Hazard: Patient on Anticoagulant (Warfarin)",
                    indicator="critical",
                    detail=(
                        "Clinical guidance citing AHA/ADA guidelines: Verify latest INR (target 2.0-3.0 before "
                        "invasive dental surgery). Prepare local hemostatic agents (e.g., absorbable gelatin sponge, "
                        "sutures, 4.8% tranexamic acid mouthwash). Routine anticoagulant cessation is not recommended "
                        "for minor oral surgery without consulting the prescribing physician."
                    ),
                    source=CDSSource(
                        label="MDIN Hematology Surveillance Node",
                        url="https://www.heart.org",
                    ),
                    suggestions=[
                        CDSSuggestion(
                            label="Order Pre-Op INR Lab Verification & MD Consult",
                            uuid="sugg-inr-001",
                            actions=[
                                CDSSuggestionAction(
                                    type="create",
                                    description="Order INR Lab Verification or request MD consult",
                                    resource={
                                        "resourceType": "ServiceRequest",
                                        "code": {
                                            "coding": [
                                                {
                                                    "system": "http://loinc.org",
                                                    "code": "6301-6",
                                                    "display": "INR in Blood",
                                                }
                                            ]
                                        },
                                    },
                                )
                            ],
                        )
                    ],
                    links=[
                        CDSLink(
                            label="ADA Anticoagulant Guidelines",
                            url="https://www.ada.org",
                            type="absolute",
                        )
                    ],
                )
            )

        # --- Rule b: Antibiotic Prophylaxis Check ---
        if is_mucosal_bleeding and has_prosthetic_valve:
            if has_penicillin_allergy:
                cards.append(
                    CDSCard(
                        summary="AHA Prophylaxis Alert: Requires Clindamycin 600mg or Azithromycin 500mg PO 1h prior. Penicillin/Amoxicillin contraindicated.",
                        indicator="critical",
                        detail=(
                            "Patient has a prosthetic cardiac valve requiring AHA endocarditis prophylaxis prior to invasive "
                            "dental manipulation, but has a documented severe allergy to Penicillin. Beta-lactams (Amoxicillin, "
                            "Penicillin V) are contraindicated. Recommended non-beta-lactam alternative: Clindamycin 600mg PO "
                            "or Azithromycin 500mg PO administered 30 to 60 minutes prior to procedure."
                        ),
                        source=CDSSource(
                            label="AHA Dental Antibiotic Prophylaxis Protocol",
                            url="https://www.heart.org",
                        ),
                        suggestions=[
                            CDSSuggestion(
                                label="Prescribe Clindamycin 600mg PO 1 Hour Pre-Op",
                                uuid="sugg-clinda-order-001",
                                actions=[
                                    CDSSuggestionAction(
                                        type="create",
                                        description="Add Clindamycin 600mg premedication to CareStack Rx",
                                        resource={
                                            "resourceType": "MedicationRequest",
                                            "medicationCodeableConcept": {
                                                "coding": [
                                                    {
                                                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                                        "code": "284215",
                                                        "display": "Clindamycin 600 MG Oral Capsule",
                                                    }
                                                ]
                                            },
                                        },
                                    )
                                ],
                            )
                        ],
                    )
                )
            else:
                cards.append(
                    CDSCard(
                        summary="AHA Antibiotic Prophylaxis Required: Prosthetic Heart Valve",
                        indicator="warning",
                        detail=(
                            "Patient has documented Prosthetic Cardiac Valve (SNOMED: 315215002). AHA Guidelines mandate "
                            "prophylactic antibiotic premedication 30-60 minutes prior to invasive dental manipulation "
                            "involving mucosal bleeding. Standard regimen: Amoxicillin 2g PO 1 hour prior to procedure."
                        ),
                        source=CDSSource(
                            label="AHA Dental Antibiotic Prophylaxis Protocol",
                            url="https://www.heart.org",
                        ),
                        suggestions=[
                            CDSSuggestion(
                                label="Prescribe Amoxicillin 2g PO 1 Hour Pre-Op",
                                uuid="sugg-amox-order-001",
                                actions=[
                                    CDSSuggestionAction(
                                        type="create",
                                        description="Add Amoxicillin 2g premedication to CareStack Rx",
                                        resource={
                                            "resourceType": "MedicationRequest",
                                            "medicationCodeableConcept": {
                                                "coding": [
                                                    {
                                                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                                        "code": "213269",
                                                        "display": "Amoxicillin 2000 MG Oral Powder",
                                                    }
                                                ]
                                            },
                                        },
                                    )
                                ],
                            )
                        ],
                    )
                )

        # --- Rule c: MRONJ Extraction Check ---
        if is_extraction and has_bisphosphonate:
            cards.append(
                CDSCard(
                    summary="CRITICAL: Medication-Related Osteonecrosis of the Jaw (MRONJ) Risk",
                    indicator="critical",
                    detail=(
                        "Patient is currently receiving IV Bisphosphonate therapy (Zoledronic Acid) for Osteoporosis. "
                        "Planned surgical extraction carries high risk of osteonecrosis of the jaw post-extraction. "
                        "Recommend conservative endodontic therapy or mandatory medical oncology clearance with chlorhexidine pre-rinse."
                    ),
                    source=CDSSource(
                        label="MDIN Clinical Safety Engine",
                        url="https://www.aaoms.org/practice-resources/clinical-resources/mronj",
                    ),
                    suggestions=[
                        CDSSuggestion(
                            label="Request Physician Clearance & Modify Plan to Endodontic Preservation",
                            uuid="sugg-mronj-order-001",
                            actions=[
                                CDSSuggestionAction(
                                    type="create",
                                    description="Consultation note sent to treating oncologist via FHIR CommunicationRequest",
                                )
                            ],
                        )
                    ],
                    links=[
                        CDSLink(
                            label="AAOMS MRONJ Guidelines",
                            url="https://www.aaoms.org",
                            type="absolute",
                        )
                    ],
                )
            )

        # --- Rule d: Low Risk / Clean ---
        # Returns empty cards list [] to prevent clinical alert fatigue
        return CDSResponse(cards=cards)


cds_engine = CDSEngine()
