"""
MAO Clinical Risk Agent (Step 15).

Autonomy trigger: intake completion, or a CDT procedure added to the CareStack treatment plan.

Evaluates the scheduled procedure against the patient's systemic profile using a deterministic
rule knowledge base, appends a structured hazard object to `risk_evaluations`, decides whether
physician clearance is mandatory, and posts a sticky alert to the CareStack chart.
"""

import re
from datetime import date
from typing import Any, Dict, List, Optional

from ...models.agent_state import MAOState, make_agent_log, utc_now_iso
from .base import SURGICAL_EXTRACTION_CODES, carestack_services, find_concepts, is_invasive

HAZARD_ORDER = {"LOW": 0, "MODERATE": 1, "CRITICAL": 2}
RECENT_STENT_MONTHS = 12


def _months_since(onset: str, today: Optional[date] = None) -> Optional[int]:
    try:
        start = date.fromisoformat((onset or "")[:10])
    except ValueError:
        return None
    today = today or date.today()
    return (today.year - start.year) * 12 + (today.month - start.month) - (1 if today.day < start.day else 0)


class ClinicalRiskAgent:
    name = "Clinical Risk Agent"
    icon = "shield-alert"

    # -- knowledge base: each rule returns a finding dict or None -------------

    def _rule_coronary_stent(self, state: MAOState, cdt_code: str) -> Optional[Dict[str, Any]]:
        stents = find_concepts(state, codes=("Z95.5",), keywords=("stent",))
        if not stents:
            return None
        months = _months_since(stents[0].get("onset", ""))
        recent = months is None or months < RECENT_STENT_MONTHS  # unknown placement date is treated as recent
        antiplatelets = [c["display"] for c in find_concepts(state, keywords=("clopidogrel", "plavix", "aspirin",
                                                                              "prasugrel", "ticagrelor"))]
        when = f"{months} months ago" if months is not None else "on an unknown date"
        return {
            "rule_id": "CARDIAC_STENT_DAPT",
            "hazard_level": "CRITICAL" if recent and is_invasive(cdt_code) else "MODERATE",
            "contraindication": (
                f"Coronary stent (ICD-10 Z95.5) placed {when}: high ischemic / stent-thrombosis liability"
                + (f"; on antiplatelet therapy ({', '.join(antiplatelets)})" if antiplatelets else "")
            ),
            "recommendations": [
                "Mandatory dual antiplatelet therapy (DAPT) protocol review with the treating cardiologist; "
                "do not interrupt DAPT without cardiology sign-off.",
                "Strict epinephrine restriction: maximum 2 carpules of 1:100,000 epinephrine (0.036 mg).",
                "Plan local hemostatic measures (sutures, oxidized cellulose, tranexamic acid rinse).",
            ],
            "evidence": [c["display"] for c in stents] + antiplatelets,
        }

    def _rule_bisphosphonate(self, state: MAOState, cdt_code: str) -> Optional[Dict[str, Any]]:
        drugs = [
            c for c in find_concepts(state, keywords=("alendron", "fosamax", "zoledron", "reclast", "zometa",
                                                      "risedron", "ibandron", "denosumab", "prolia"))
            if c.get("type") == "medication"
        ]
        if not drugs:
            return None
        surgical = cdt_code in SURGICAL_EXTRACTION_CODES or is_invasive(cdt_code)
        months = _months_since(drugs[0].get("onset", ""))
        duration = f" for ~{months // 12} years" if months and months >= 12 else ""
        return {
            "rule_id": "BISPHOSPHONATE_MRONJ",
            "hazard_level": "CRITICAL" if surgical else "MODERATE",
            "contraindication": (
                f"Antiresorptive therapy ({drugs[0]['display']}{duration}): high risk of medication-related "
                f"osteonecrosis of the jaw (MRONJ) with surgical extraction"
            ),
            "recommendations": [
                "Confirm antiresorptive duration and route with the prescriber before any bone-invasive procedure.",
                "Consider conservative alternatives (endodontic therapy / coronectomy) to surgical extraction.",
                "If surgery proceeds: atraumatic technique, primary closure, chlorhexidine rinse protocol.",
            ],
            "evidence": [c["display"] for c in drugs],
        }

    def _rule_anticoagulant(self, state: MAOState, cdt_code: str) -> Optional[Dict[str, Any]]:
        drugs = find_concepts(state, keywords=("warfarin", "coumadin", "apixaban", "eliquis", "rivaroxaban",
                                                "xarelto", "dabigatran"))
        if not drugs:
            return None
        return {
            "rule_id": "ANTICOAGULANT_HEMORRHAGE",
            "hazard_level": "CRITICAL" if is_invasive(cdt_code) else "MODERATE",
            "contraindication": f"Active anticoagulant therapy ({drugs[0]['display']}): post-operative hemorrhage hazard",
            "recommendations": [
                "Obtain physician clearance and a current INR (within 72 hours for warfarin) before the procedure.",
                "Plan local hemostatic measures; avoid NSAIDs post-operatively.",
            ],
            "evidence": [c["display"] for c in drugs],
        }

    def _rule_systemic_modifiers(self, state: MAOState, cdt_code: str) -> Optional[Dict[str, Any]]:
        found = find_concepts(state, codes=("I10", "E11.9"), keywords=("hypertension", "diabetes"))
        if not found or not is_invasive(cdt_code):
            return None
        return {
            "rule_id": "SYSTEMIC_MODIFIERS",
            "hazard_level": "MODERATE",
            "contraindication": "Systemic comorbidity: " + ", ".join(c["display"] for c in found),
            "recommendations": [
                "Record pre-operative blood pressure; defer elective surgery if >= 180/110 mmHg.",
            ] + (["Verify recent HbA1c; schedule a morning appointment after a normal meal."]
                 if any("diabet" in c["display"].lower() or c.get("code") == "E11.9" for c in found) else []),
            "evidence": [c["display"] for c in found],
        }

    def _rule_endocarditis_prophylaxis(self, state: MAOState, cdt_code: str) -> Optional[Dict[str, Any]]:
        cardiac = find_concepts(state, codes=("I33.0", "Z95.2", "Z95.3", "Z95.4"),
                                keywords=("prosthetic", "heart valve", "cardiac valve", "endocarditis"))
        # AHA: procedures that manipulate gingival tissue or perforate mucosa (not exams / radiographs)
        if not cardiac or not re.match(r"D[1-7]", (cdt_code or "").upper()):
            return None
        penicillin = find_concepts(state, keywords=("penicillin", "amoxicillin"))
        penicillin = [c for c in penicillin if c.get("type") == "allergy"]
        return {
            "rule_id": "ENDOCARDITIS_PROPHYLAXIS",
            "hazard_level": "MODERATE",
            "contraindication": f"High-risk cardiac condition ({cardiac[0]['display']}): infective endocarditis prophylaxis indicated",
            "recommendations": [
                "Antibiotic prophylaxis 30-60 minutes before the procedure per AHA guidance"
                + (": patient is penicillin-allergic, so NOT amoxicillin; use an alternative such as azithromycin or "
                   "doxycycline per current guidance." if penicillin else " (amoxicillin 2 g orally for adults)."),
            ],
            "evidence": [c["display"] for c in cardiac],
        }

    def _rule_drug_allergy(self, state: MAOState, cdt_code: str) -> Optional[Dict[str, Any]]:
        allergies = [c for c in (state.get("medical_records") or {}).get("normalized_concepts") or [] if c.get("type") == "allergy"]
        if not allergies:
            return None
        names = " ".join((c.get("display") or "").lower() for c in allergies)
        recommendations = []
        if "penicillin" in names or "amoxicillin" in names:
            recommendations.append("Penicillin allergy: do not prescribe amoxicillin / penicillin VK for prophylaxis or post-operative infection.")
        if "latex" in names:
            recommendations.append("Latex allergy: latex-free gloves, dam and prophy cups; schedule as first patient of the day.")
        if "sulf" in names or "codeine" in names or "nsaid" in names or "aspirin" in names:
            recommendations.append("Check the post-operative analgesic / antibiotic plan against the recorded drug allergy.")
        return {
            "rule_id": "DRUG_ALLERGY",
            "hazard_level": "MODERATE",
            "contraindication": "Recorded allergy: " + ", ".join(c["display"] for c in allergies),
            "recommendations": recommendations or ["Review every planned drug and material against the recorded allergy."],
            "evidence": [c["display"] for c in allergies],
        }

    RULES = ("_rule_coronary_stent", "_rule_bisphosphonate", "_rule_anticoagulant", "_rule_endocarditis_prophylaxis",
             "_rule_drug_allergy", "_rule_systemic_modifiers")

    # -- node -----------------------------------------------------------------

    def evaluate(self, state: MAOState, cdt_code: str) -> Dict[str, Any]:
        findings = [f for f in (getattr(self, rule)(state, cdt_code) for rule in self.RULES) if f]
        hazard = max((f["hazard_level"] for f in findings), key=HAZARD_ORDER.get, default="LOW")
        return {
            "hazard_level": hazard,
            "contraindications": [f["contraindication"] for f in findings],
            "clinical_recommendations": [r for f in findings for r in f["recommendations"]],
            "cdt_code": cdt_code,
            "procedure_invasive": is_invasive(cdt_code),
            "triggered_rules": [f["rule_id"] for f in findings],
            "findings": findings,
            "evaluated_at": utc_now_iso(),
        }

    async def _post_sticky_alert(self, patient_id: str, evaluation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        carestack = carestack_services()
        alert = carestack.MedicalAlertCreate(
            title=f"CRITICAL: Medical clearance required before {evaluation['cdt_code']}",
            details=" | ".join(evaluation["contraindications"]),
            alert_type="critical",
            category="cardiac" if "CARDIAC_STENT_DAPT" in evaluation["triggered_rules"] else "pharmacology",
            source="MAO Clinical Risk Agent",
            action_required="HOLD procedure until physician clearance is on file. "
            + evaluation["clinical_recommendations"][0],
        )
        try:
            result = await carestack.write_medical_alert(patient_id, alert)
        except Exception:  # patient exists only in the EHR, not in the CareStack simulator
            return None
        return dict(result["alert"], sticky=True)

    async def __call__(self, state: MAOState) -> Dict[str, Any]:
        appointment = dict(state.get("appointment") or {})
        cdt_codes = appointment.get("cdt_codes") or [""]
        # Evaluate every scheduled procedure; the most hazardous one drives the handoff
        evaluation = max((self.evaluate(state, c) for c in cdt_codes), key=lambda e: HAZARD_ORDER[e["hazard_level"]])

        clearance_required = evaluation["hazard_level"] == "CRITICAL"
        logs: List[Dict[str, Any]] = [make_agent_log(
            self.name,
            f"Hazard level {evaluation['hazard_level']} for {evaluation['cdt_code'] or 'visit'}",
            "; ".join(evaluation["contraindications"]) or "No systemic contraindications for the scheduled care.",
            self.icon,
        )]

        if clearance_required:
            appointment["status"] = "REQUIRES_ACTION"
            alert = await self._post_sticky_alert(state["patient_id"], evaluation)
            evaluation["sticky_alert"] = alert
            logs.append(make_agent_log(
                self.name,
                "Physician clearance required",
                ("Sticky alert posted to the CareStack chart; " if alert else "")
                + "appointment flagged REQUIRES_ACTION. Routing to Medical Clearance Agent.",
                "alert-triangle",
            ))

        return {
            "risk_evaluations": [evaluation],
            "clearance_status": "REQUIRED_PENDING" if clearance_required else "NOT_REQUIRED",
            "appointment": appointment,
            "agent_logs": logs,
        }
