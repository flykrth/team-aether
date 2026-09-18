"""
MAO Commercial Billing Agent (Step 15).

Autonomy trigger: treatment plan confirmed and clinically verified by the Risk agent.

1. Evaluates CDT -> CPT medical cross-billing rules against the patient's coded diagnoses.
2. Auto-populates the CMS-1500 claim schema (Boxes 1-33).
3. Synthesizes a Letter of Medical Necessity (LOMN) from the Risk and Clearance agents' findings.
4. Sets `cross_bill_eligible`, estimates the dental annual-maximum savings and uploads the LOMN
   to the CareStack patient chart.

NOTE: the systemic-justification rules below are demo heuristics for the MDIN simulator. Real payer
medical-necessity policy varies by plan and must be confirmed before a claim is submitted.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...models.agent_state import MAOState, make_agent_log
from ...models.claims import BillingProvider, ClaimServiceLine, CMS1500Claim, DiagnosisCode
from .base import ICD10_SYSTEM, carestack_services, primary_cdt

# Surgical extractions billable to medical when a systemic diagnosis makes the surgery medically complex.
# Extends (does not replace) the ConceptMap crosswalk in terminology_maps.json.
SYSTEMIC_CROSS_BILL_RULES: Dict[str, Dict[str, Any]] = {
    code: {
        "cpt_code": "41899",
        "cpt_display": "Unlisted procedure, dentoalveolar structures",
        "alternate_cpt": {"code": "21210", "display": "Graft, bone; nasal, maxillary or malar areas"},
        "qualifying_icd10": ["M26.61", "Z95.5", "E11.9"],
        "estimated_savings": 1200.0,
    }
    for code in ("D7210", "D7240")
}


class CommercialBillingAgent:
    name = "Commercial Billing Agent"
    icon = "receipt"

    def _diagnoses(self, state: MAOState) -> List[Dict[str, str]]:
        concepts = (state.get("medical_records") or {}).get("normalized_concepts") or []
        return [
            {"code": c["code"], "display": c.get("display", "")}
            for c in concepts
            if c.get("type") == "condition" and c.get("system") == ICD10_SYSTEM and c.get("code")
        ]

    def evaluate_cross_billing(self, state: MAOState, cdt_code: str) -> Optional[Dict[str, Any]]:
        """Returns the matched cross-billing rule, preferring the ConceptMap crosswalk over agent heuristics."""
        from ..crosswalk_engine import crosswalk_engine

        carestack_services()
        diagnoses = self._diagnoses(state)
        base = crosswalk_engine.evaluate_cross_coding(cdt_code, [d["code"] for d in diagnoses])
        if base.is_eligible:
            rule = SYSTEMIC_CROSS_BILL_RULES.get(cdt_code, {})
            return {
                "source": "conceptmap-crosswalk",
                "cpt_code": base.suggested_cpt,
                "cpt_display": "",
                "alternate_cpt": rule.get("alternate_cpt"),
                "justifying_icd10": base.justifying_icd10,
                "estimated_savings": max(float(base.estimated_coverage), rule.get("estimated_savings", 0.0)),
            }

        rule = SYSTEMIC_CROSS_BILL_RULES.get(cdt_code)
        matched = [d["code"] for d in diagnoses if rule and d["code"] in rule["qualifying_icd10"]]
        if not matched:
            return None
        return dict(rule, source="systemic-justification", justifying_icd10=matched)

    def build_cms1500(self, state: MAOState, match: Dict[str, Any], charge: float) -> CMS1500Claim:
        """Populates CMS-1500 Boxes 1-33 from CareStack demographics and the coded diagnoses."""
        patient = carestack_services()._find_carestack_patient(state["patient_id"])
        diagnoses = self._diagnoses(state)
        ordered = [d for d in diagnoses if d["code"] in match["justifying_icd10"]]
        ordered += [d for d in diagnoses if d not in ordered]

        name = state.get("patient_name") or state["patient_id"]
        if patient:
            name = f"{patient.last_name}, {patient.first_name}"
        appointment_date = ((state.get("appointment") or {}).get("timestamp") or "")[:10]

        return CMS1500Claim(
            insurance_type="GROUP_HEALTH_PLAN",                                           # Box 1
            insured_id=f"MED-{patient.mrn if patient else state['patient_id']}",            # Box 1a
            patient_name=name,                                                            # Box 2
            patient_dob=state.get("dob") or (patient.birth_date if patient else "") or "unknown",  # Box 3
            patient_gender=(patient.gender if patient else "") or "unknown",              # Box 3
            patient_address="Address on file in CareStack",                               # Box 5
            diagnosis_codes=[                                                             # Box 21
                DiagnosisCode(pointer=ptr, code=d["code"], description=d["display"])
                for ptr, d in zip("ABCD", ordered)
            ],
            service_lines=[ClaimServiceLine(                                              # Box 24
                date_of_service=appointment_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                place_of_service="11",
                cpt_code=match["cpt_code"],
                modifiers=["22"] if primary_cdt(state) == "D7240" else [],
                diagnosis_pointer="".join("ABCD"[: max(1, len(match["justifying_icd10"]))]),
                charges=charge,
                days_or_units=1,
                rendering_provider_npi=BillingProvider().provider_npi,
            )],
            billing_provider=BillingProvider(),                                           # Box 33
            total_charge=charge,                                                          # Box 28
            amount_paid=0.0,                                                              # Box 29
            balance_due=charge,                                                           # Box 30
        )

    def synthesize_lomn(self, state: MAOState, cdt_code: str, match: Dict[str, Any]) -> Dict[str, Any]:
        """LOMN from the shared generator, extended with the Risk and Clearance agents' findings."""
        from ..document_generator import medical_necessity_generator

        concepts = (state.get("medical_records") or {}).get("normalized_concepts") or []
        letter = medical_necessity_generator.generate_letter_of_medical_necessity(
            patient_data={"patient_name": state.get("patient_name"), "dob": state.get("dob"), "id": state["patient_id"]},
            clinical_findings={
                "conditions": [{"code": c["code"], "display": c["display"]} for c in concepts if c["type"] == "condition"],
                "medications": [c["display"] for c in concepts if c["type"] == "medication"],
            },
            crosswalk_data={
                "cdt_code": cdt_code,
                "suggested_cpt": match["cpt_code"],
                "cpt_display": match.get("cpt_display") or None,
                "justifying_icd10": match["justifying_icd10"],
                "estimated_coverage": match["estimated_savings"],
            },
        )

        risk = next((e for e in reversed(state.get("risk_evaluations") or [])), {})
        protocol = state.get("clearance_protocol") or {}
        physician = state.get("assigned_medical_md") or {}
        addendum = ["", "## Multi-Agent Clinical Findings", "", f"**Clinical Risk Agent - hazard level {risk.get('hazard_level', 'N/A')}**"]
        addendum += [f"- {c}" for c in risk.get("contraindications", [])] or ["- No systemic contraindications recorded."]
        addendum += ["", "**Medical Clearance Agent**"]
        if protocol.get("signed_by"):
            addendum.append(f"- Clearance {protocol.get('decision', '')} by {protocol['signed_by']}"
                            + (f" ({physician.get('facility')})" if physician.get("facility") else "") + ".")
            addendum += [f"- Physician-ordered restriction: {r}" for r in protocol.get("restrictions", [])]
        elif state.get("clearance_status") in ("REQUIRED_PENDING", "TRANSMITTED_TO_EHR"):
            addendum.append("- Physician medical clearance has been requested for this procedure and is pending; "
                            "the requirement for physician co-management supports medical necessity.")
        else:
            addendum.append("- Physician clearance not required for this procedure.")

        letter["content_markdown"] = letter["content_markdown"].rstrip() + "\n" + "\n".join(addendum) + "\n"
        return letter

    async def __call__(self, state: MAOState) -> Dict[str, Any]:
        cdt_code = primary_cdt(state)
        match = self.evaluate_cross_billing(state, cdt_code) if cdt_code else None
        if not match:
            return {
                "cross_bill_eligible": False,
                "agent_logs": [make_agent_log(
                    self.name,
                    "No medical cross-billing opportunity",
                    f"No qualifying ICD-10 justification on record for {cdt_code or 'the scheduled visit'}; "
                    "claim stays with the dental carrier.",
                    self.icon,
                )],
            }

        carestack = carestack_services()
        patient = carestack._find_carestack_patient(state["patient_id"])
        planned = next((p for p in (patient.active_treatment_plan if patient else []) if p.code == cdt_code), None)
        charge = float(planned.cost) if planned and planned.cost else match["estimated_savings"]

        claim = self.build_cms1500(state, match, charge)
        letter = self.synthesize_lomn(state, cdt_code, match)
        logs = [
            make_agent_log(
                self.name,
                f"Cross-billing rule matched: {cdt_code} -> CPT {match['cpt_code']}",
                f"Medical justification {', '.join(match['justifying_icd10'])} ({match['source']})."
                + (f" Alternate CPT {match['alternate_cpt']['code']} if bone grafting is performed." if match.get("alternate_cpt") else ""),
                self.icon,
            ),
            make_agent_log(self.name, "CMS-1500 populated", f"Boxes 1-33 completed; Box 21 diagnoses "
                           f"{', '.join(d.code for d in claim.diagnosis_codes)}; Box 24D CPT {match['cpt_code']}.", "file-text"),
        ]

        document_id = None
        try:
            record = carestack.save_patient_document(
                patient_id=state["patient_id"],
                document_type="Letter of Medical Necessity",
                title=f"LOMN - {cdt_code} / CPT {match['cpt_code']} (MAO Billing Agent)",
                file_content=letter["content_markdown"],
                metadata={"cdt_code": cdt_code, "cpt_code": match["cpt_code"], "icd10": match["justifying_icd10"],
                          "generated_by": "MAO Commercial Billing Agent"},
            )
            document_id = record.get("document_id")
        except Exception:  # patient not registered in the CareStack simulator
            pass
        logs.append(make_agent_log(
            self.name,
            "Letter of Medical Necessity synthesized",
            (f"Uploaded to CareStack chart as {document_id}. " if document_id else "CareStack upload skipped (patient not in PMS). ")
            + f"Estimated ${match['estimated_savings']:,.0f} of the patient's dental annual maximum preserved.",
            "piggy-bank",
        ))

        return {
            "cross_bill_eligible": True,
            "commercial_claims": {
                "suggested_cpt": match["cpt_code"],
                "alternate_cpt": (match.get("alternate_cpt") or {}).get("code"),
                "justifying_icd10": match["justifying_icd10"],
                "estimated_savings": float(match["estimated_savings"]),
                "cms1500_ready": True,
                "lomn_attached": document_id is not None,
                "lomn_document_id": document_id,
                "lomn_title": letter.get("title"),
                "rule_source": match["source"],
                "cms1500": claim.model_dump(mode="json"),
            },
            "agent_logs": logs,
        }
