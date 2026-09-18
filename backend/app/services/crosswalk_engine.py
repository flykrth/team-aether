"""
Administrative Decision Support & Medical Cross-Coding Engine for MDIN.
Step 8: Translates dental CDT procedure codes to medical CPT codes, validates qualifying
ICD-10 medical necessity criteria, and pre-populates standard CMS-1500 and 837P claims.
"""

import os
import json
import re
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone

from ..models.claims import (
    CMS1500Claim,
    ClaimServiceLine,
    BillingProvider,
    DiagnosisCode,
    CrossCodingOpportunity,
)
from .concept_map import DATA_DIR, TERMINOLOGY_MAP_FILE


class AdministrativeCrossCodingEngine:
    """
    Administrative Decision Support engine that evaluates dental procedures (CDT)
    against patient systemic and maxillofacial medical diagnoses (ICD-10) to discover
    primary medical billing cross-coding opportunities (CPT) and generate CMS-1500 forms.
    """

    def __init__(self, terminology_map_path: Optional[str] = None):
        self.map_file = terminology_map_path or TERMINOLOGY_MAP_FILE
        self.crosswalk_rules: Dict[str, List[Dict[str, Any]]] = {}
        self.concept_map_metadata: Dict[str, Any] = {}
        self.load_crosswalk_rules()

    def load_crosswalk_rules(self) -> None:
        """Load and index the cdt-to-cpt-crosswalk ConceptMap from terminology_maps.json."""
        self.crosswalk_rules = {}
        if not os.path.exists(self.map_file):
            return

        with open(self.map_file, "r", encoding="utf-8") as f:
            raw = json.load(f)

        crosswalk_map = None
        if isinstance(raw, list):
            for item in raw:
                if item.get("id") == "cdt-to-cpt-crosswalk":
                    crosswalk_map = item
                    break
        elif isinstance(raw, dict):
            if raw.get("id") == "cdt-to-cpt-crosswalk":
                crosswalk_map = raw

        if not crosswalk_map:
            return

        self.concept_map_metadata = {
            "id": crosswalk_map.get("id"),
            "url": crosswalk_map.get("url"),
            "version": crosswalk_map.get("version"),
            "title": crosswalk_map.get("title"),
            "description": crosswalk_map.get("description"),
            "status": crosswalk_map.get("status"),
        }

        # Index elements by CDT code
        for group in crosswalk_map.get("group", []):
            for element in group.get("element", []):
                cdt_code = element.get("code", "").upper().strip()
                cdt_display = element.get("display", "")
                targets = []
                for tgt in element.get("target", []):
                    cpt_code = tgt.get("code", "")
                    cpt_display = tgt.get("display", "")
                    qualifying_icd10 = tgt.get("qualifying_icd10", [])
                    details = tgt.get("qualifying_icd10_details", [])
                    est_cov = float(tgt.get("estimated_coverage", 0.0))
                    est_min = float(tgt.get("estimated_coverage_min", est_cov))
                    est_max = float(tgt.get("estimated_coverage_max", est_cov))
                    category = tgt.get("reimbursement_category", "Medical cross-coding eligible")

                    targets.append({
                        "code": cpt_code,
                        "display": cpt_display,
                        "equivalence": tgt.get("equivalence", "equivalent"),
                        "qualifying_icd10": qualifying_icd10,
                        "qualifying_icd10_details": details,
                        "estimated_coverage": est_cov,
                        "estimated_coverage_min": est_min,
                        "estimated_coverage_max": est_max,
                        "reimbursement_category": category,
                    })

                self.crosswalk_rules[cdt_code] = {
                    "cdt_code": cdt_code,
                    "cdt_display": cdt_display,
                    "targets": targets,
                }

    def get_rules(self) -> Dict[str, Any]:
        """Returns the loaded crosswalk rules and metadata."""
        return {
            "metadata": self.concept_map_metadata,
            "rules": self.crosswalk_rules,
        }

    def extract_icd10_codes(self, patient_conditions: List[Any]) -> List[Dict[str, str]]:
        """
        Extracts active ICD-10 diagnostic codes and displays from condition resources,
        dictionaries, or string codes.
        """
        extracted: List[Dict[str, str]] = []
        seen_codes = set()

        for cond in patient_conditions:
            if not cond:
                continue

            if isinstance(cond, str):
                code_clean = cond.strip().upper()
                if code_clean not in seen_codes:
                    seen_codes.add(code_clean)
                    extracted.append({"code": code_clean, "display": code_clean})
                continue

            if isinstance(cond, dict):
                # Check clinicalStatus for FHIR Condition
                clinical_status = cond.get("clinicalStatus")
                if isinstance(clinical_status, dict):
                    status_codings = clinical_status.get("coding", [])
                    if status_codings and status_codings[0].get("code") not in ("active", "recurrence", "relapse"):
                        continue

                # Check code.coding
                code_obj = cond.get("code")
                if isinstance(code_obj, dict):
                    codings = code_obj.get("coding", [])
                    found_icd = False
                    for c in codings:
                        sys = (c.get("system") or "").lower()
                        cd = (c.get("code") or "").strip().upper()
                        disp = c.get("display") or code_obj.get("text") or cd
                        if "icd-10" in sys:
                            if cd and cd not in seen_codes:
                                seen_codes.add(cd)
                                extracted.append({"code": cd, "display": disp})
                                found_icd = True
                    # If no system explicitly declared icd-10, check code format
                    if not found_icd:
                        for c in codings:
                            cd = (c.get("code") or "").strip().upper()
                            disp = c.get("display") or code_obj.get("text") or cd
                            if re.match(r"^[A-Z][0-9][0-9A-Z](\.[0-9A-Z]{1,4})?$", cd):
                                if cd not in seen_codes:
                                    seen_codes.add(cd)
                                    extracted.append({"code": cd, "display": disp})

                # Flat dictionary format { code, display }
                if "code" in cond and isinstance(cond["code"], str):
                    cd = cond["code"].strip().upper()
                    disp = cond.get("display") or cond.get("text") or cd
                    if cd not in seen_codes:
                        seen_codes.add(cd)
                        extracted.append({"code": cd, "display": disp})

        return extracted

    def evaluate_cross_coding(
        self,
        cdt_code: str,
        patient_conditions: List[Any],
        patient_demographics: Optional[Dict[str, Any]] = None,
    ) -> CrossCodingOpportunity:
        """
        Core cross-coding evaluation logic:
        1. Scans patient's active FHIR conditions for qualifying medical diagnoses.
        2. Matches procedural CDT to valid medical CPT.
        3. Synthesizes and pre-populates a valid CMS1500Claim schema instance with
           Box 1-33 data populated from CareStack patient demographics and FHIR diagnostic codes.
        """
        demographics = patient_demographics or {}
        code_norm = (cdt_code or "").strip().upper()

        if code_norm not in self.crosswalk_rules:
            return CrossCodingOpportunity(
                is_eligible=False,
                cdt_code=code_norm,
                suggested_cpt=None,
                justifying_icd10=[],
                estimated_coverage=0.0,
                claim_preview=None,
                reimbursement_category="Ineligible - No Crosswalk Rule",
                narrative_justification=(
                    f"Dental procedure CDT {code_norm} does not have an established medical cross-coding "
                    f"pathway under commercial or CMS medical billing standards."
                ),
            )

        rule = self.crosswalk_rules[code_norm]
        targets = rule.get("targets", [])
        if not targets:
            return CrossCodingOpportunity(
                is_eligible=False,
                cdt_code=code_norm,
                suggested_cpt=None,
                justifying_icd10=[],
                estimated_coverage=0.0,
                claim_preview=None,
                reimbursement_category="Ineligible - No Target Codes",
                narrative_justification=f"No target medical CPT codes configured for CDT {code_norm}.",
            )

        # Extract active patient ICD-10 diagnoses
        patient_diagnoses = self.extract_icd10_codes(patient_conditions)
        patient_dx_by_code = {d["code"]: d["display"] for d in patient_diagnoses}

        # Check if any target's qualifying ICD-10 criteria are met
        selected_target = None
        matched_qualifying_codes: List[str] = []

        for target in targets:
            qualifying = target.get("qualifying_icd10", [])
            matches = [q for q in qualifying if q in patient_dx_by_code]
            if matches:
                selected_target = target
                matched_qualifying_codes = matches
                break

        if not selected_target:
            # First target used for suggestion context
            suggested = targets[0]
            required_codes = ", ".join(suggested.get("qualifying_icd10", []))
            return CrossCodingOpportunity(
                is_eligible=False,
                cdt_code=code_norm,
                suggested_cpt=suggested["code"],
                justifying_icd10=[],
                estimated_coverage=0.0,
                claim_preview=None,
                reimbursement_category=suggested.get("reimbursement_category"),
                narrative_justification=(
                    f"Dental procedure CDT {code_norm} ({rule.get('cdt_display')}) has a potential medical "
                    f"cross-coding crosswalk to CPT {suggested['code']} ({suggested['display']}), but requires "
                    f"qualifying medical diagnoses [{required_codes}]. No qualifying systemic or maxillofacial "
                    f"diagnoses were found in the patient's active medical problem list."
                ),
            )

        # Patient qualifies! Synthesize CMS-1500 Claim form
        cpt_code = selected_target["code"]
        cpt_display = selected_target["display"]
        est_coverage = selected_target["estimated_coverage"]
        category = selected_target.get("reimbursement_category")

        # Compile diagnosis codes for Box 21 (up to 4 with pointers A-D)
        pointers = ["A", "B", "C", "D"]
        box21_diagnoses: List[DiagnosisCode] = []
        assigned_codes = set()

        # Add matched qualifying codes first
        for code in matched_qualifying_codes:
            if len(box21_diagnoses) < 4 and code not in assigned_codes:
                ptr = pointers[len(box21_diagnoses)]
                disp = patient_dx_by_code.get(code) or f"Diagnosis {code}"
                box21_diagnoses.append(DiagnosisCode(pointer=ptr, code=code, description=disp))
                assigned_codes.add(code)

        # Fill remaining pointers with other active patient medical conditions
        for d in patient_diagnoses:
            if len(box21_diagnoses) >= 4:
                break
            if d["code"] not in assigned_codes:
                ptr = pointers[len(box21_diagnoses)]
                box21_diagnoses.append(DiagnosisCode(pointer=ptr, code=d["code"], description=d["display"]))
                assigned_codes.add(d["code"])

        # Format patient demographics for Boxes 1-7
        patient_name = (
            demographics.get("patient_name")
            or f"{demographics.get('first_name', '')} {demographics.get('last_name', '')}".strip()
            or demographics.get("name")
            or "DOE, JOHN"
        )
        patient_dob = (
            demographics.get("patient_dob")
            or demographics.get("birth_date")
            or demographics.get("birthDate")
            or "1975-01-01"
        )
        patient_gender = (
            demographics.get("patient_gender")
            or demographics.get("gender")
            or "unknown"
        )
        patient_address = (
            demographics.get("patient_address")
            or demographics.get("address")
            or "100 Healthcare Blvd, Boston, MA 02115"
        )
        insured_id = (
            demographics.get("insured_id")
            or demographics.get("mrn")
            or f"MED-{demographics.get('id', '10001')}"
        )
        insurance_type = demographics.get("insurance_type") or "GROUP_HEALTH_PLAN"

        # Modifiers (e.g., 22 for complex bony impaction D7240)
        modifiers = ["22"] if code_norm == "D7240" else []
        dos = demographics.get("date_of_service") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        pos = demographics.get("place_of_service") or "11"

        service_lines = [
            ClaimServiceLine(
                date_of_service=dos,
                place_of_service=pos,
                cpt_code=cpt_code,
                modifiers=modifiers,
                diagnosis_pointer="A",
                charges=est_coverage,
                days_or_units=1,
            )
        ]

        billing_provider = BillingProvider(
            provider_npi="1928374650",
            clinic_name="CareStack Center for Advanced Dentistry - Surgical Suite",
            address="100 Healthcare Boulevard, Suite 400, Boston, MA 02115",
            taxonomy_code="1223S0112X",
            phone="(555) 019-2830",
        )

        claim_preview = CMS1500Claim(
            insurance_type=insurance_type,
            insured_id=insured_id,
            patient_name=patient_name,
            patient_dob=patient_dob,
            patient_gender=patient_gender,
            patient_address=patient_address,
            diagnosis_codes=box21_diagnoses,
            service_lines=service_lines,
            billing_provider=billing_provider,
            total_charge=est_coverage,
            amount_paid=0.0,
            balance_due=est_coverage,
        )

        qualifying_desc = ", ".join(
            f"{c} ({patient_dx_by_code.get(c, '')})" for c in matched_qualifying_codes
        )
        narrative = (
            f"QUALIFIED FOR MEDICAL CROSS-CODING: Dental procedure CDT {code_norm} qualifies for primary medical "
            f"reimbursement under CPT {cpt_code} ({cpt_display}). Justifying medical diagnosis: {qualifying_desc}. "
            f"Estimated reimbursement uplift: ${est_coverage:.2f} ({category}). Pre-populated CMS-1500 and "
            f"ANSI 837P electronic claim generated."
        )

        return CrossCodingOpportunity(
            is_eligible=True,
            cdt_code=code_norm,
            suggested_cpt=cpt_code,
            justifying_icd10=matched_qualifying_codes,
            estimated_coverage=est_coverage,
            claim_preview=claim_preview,
            reimbursement_category=category,
            narrative_justification=narrative,
        )

    def evaluate_patient(self, patient_id: str, cdt_code: str) -> CrossCodingOpportunity:
        """
        Resolves patient ID against CareStack PMS and FHIR EHR, extracts active clinical
        conditions and demographics, and evaluates the cross-coding opportunity.
        """
        from ..routers.carestack_mock import CARESTACK_PATIENT_ALIASES, MOCK_PATIENTS
        from ..routers.fhir_ehr_mock import FHIR_STORE, _normalize_ref_id

        # Normalize patient ID
        clean_id = patient_id.lower().strip()
        cs_id = CARESTACK_PATIENT_ALIASES.get(clean_id, clean_id.upper())

        # Retrieve CareStack patient demographics
        cs_patient = next((p for p in MOCK_PATIENTS if p.id.upper() == cs_id.upper()), None)
        demographics: Dict[str, Any] = {}
        if cs_patient:
            demographics = {
                "id": cs_patient.id,
                "mrn": cs_patient.mrn,
                "first_name": cs_patient.first_name,
                "last_name": cs_patient.last_name,
                "patient_name": f"{cs_patient.last_name}, {cs_patient.first_name}",
                "patient_dob": cs_patient.birth_date,
                "patient_gender": cs_patient.gender,
                "insured_id": f"MED-{cs_patient.mrn or cs_patient.id}",
                "insurance_type": "GROUP_HEALTH_PLAN",
            }
        else:
            # Fallback to FHIR Patient resource
            fhir_patient = next(
                (p for p in FHIR_STORE["Patient"] if _normalize_ref_id(p.get("id")) == clean_id), None
            )
            if fhir_patient:
                names = fhir_patient.get("name", [{}])[0]
                given = " ".join(names.get("given", []))
                family = names.get("family", "")
                demographics = {
                    "id": fhir_patient.get("id"),
                    "mrn": (fhir_patient.get("identifier", [{}])[0].get("value")),
                    "first_name": given,
                    "last_name": family,
                    "patient_name": f"{family}, {given}".strip(", "),
                    "patient_dob": fhir_patient.get("birthDate"),
                    "patient_gender": fhir_patient.get("gender"),
                    "insured_id": f"MED-{fhir_patient.get('id')}",
                    "insurance_type": "GROUP_HEALTH_PLAN",
                }

        # Retrieve patient conditions from FHIR EHR
        target_ids = {clean_id, cs_id.lower()}
        if demographics.get("id"):
            target_ids.add(demographics["id"].lower())
        if demographics.get("mrn"):
            target_ids.add(demographics["mrn"].lower())

        patient_conditions: List[Dict[str, Any]] = []
        for cond in FHIR_STORE["Condition"]:
            subj = cond.get("subject", {}).get("reference", "")
            subj_id = _normalize_ref_id(subj).lower()
            if subj_id in target_ids:
                patient_conditions.append(cond)

        return self.evaluate_cross_coding(
            cdt_code=cdt_code,
            patient_conditions=patient_conditions,
            patient_demographics=demographics,
        )


# Global singleton instance for use across routers and services
crosswalk_engine = AdministrativeCrossCodingEngine()
