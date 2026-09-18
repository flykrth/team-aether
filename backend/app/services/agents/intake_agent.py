"""
MAO Intake Agent (Step 15).

Autonomy trigger: appointment booking or annual recall event.

1. Checks whether the patient has a linked external patient portal / medical EHR record.
2. If linked, pulls the FHIR record. If unlinked (or the record is empty), runs the conversational
   extraction routine over the patient's free-text intake responses.
3. Normalizes everything into coded clinical concepts (ICD-10-CM / RxNorm).
4. Writes the normalized medical record into MAOState and hands off to the Risk agent.

The narrative extractor is a deterministic lexicon matcher, not an LLM: every concept it emits is
traceable to a lexicon entry, so it cannot hallucinate a diagnosis.
"""

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from ...models.agent_state import MAOState, make_agent_log
from .base import ICD10_SYSTEM, RXNORM_SYSTEM, SNOMED_SYSTEM, clearance_service

# Synthetic conversational intake responses for patients without a linked portal
SYNTHETIC_INTAKE_RESPONSES: Dict[str, str] = {
    "cs-9922": "Patient reports taking Alendronate for 4 years, had a cardiac stent placed 8 months ago.",
    "walk-in-demo": "Patient reports taking Alendronate for 4 years, had a cardiac stent placed 8 months ago.",
}

# (regex, concept) - RxNorm codes are ingredient-level RxCUIs
NARRATIVE_LEXICON = [
    (r"\b(cardiac|coronary|heart)\s+stents?\b|\bstents?\s+(placed|placement|put in)\b|\bangioplasty\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "Z95.5",
      "display": "Presence of coronary angioplasty implant and graft (coronary stent)"}),
    (r"\batrial fibrillation\b|\ba-?fib\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "I48.91", "display": "Unspecified atrial fibrillation"}),
    (r"\bhigh blood pressure\b|\bhypertension\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "I10", "display": "Essential (primary) hypertension"}),
    (r"\bdiabet(es|ic)\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "E11.9",
      "display": "Type 2 diabetes mellitus without complications"}),
    (r"\bosteoporosis\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "M81.0",
      "display": "Age-related osteoporosis without current pathological fracture"}),
    (r"\balendronate\b|\bfosamax\b",
     {"type": "medication", "system": RXNORM_SYSTEM, "code": "46041", "display": "Alendronate (Fosamax)",
      "drug_class": "bisphosphonate"}),
    (r"\bzoledron(ic acid|ate)\b|\breclast\b|\bzometa\b",
     {"type": "medication", "system": RXNORM_SYSTEM, "code": "77655", "display": "Zoledronic acid (Reclast)",
      "drug_class": "bisphosphonate"}),
    (r"\bclopidogrel\b|\bplavix\b",
     {"type": "medication", "system": RXNORM_SYSTEM, "code": "32968", "display": "Clopidogrel (Plavix)",
      "drug_class": "antiplatelet"}),
    (r"\baspirin\b",
     {"type": "medication", "system": RXNORM_SYSTEM, "code": "1191", "display": "Aspirin",
      "drug_class": "antiplatelet"}),
    (r"\bwarfarin\b|\bcoumadin\b",
     {"type": "medication", "system": RXNORM_SYSTEM, "code": "11289", "display": "Warfarin (Coumadin)",
      "drug_class": "anticoagulant"}),
    (r"\bapixaban\b|\beliquis\b",
     {"type": "medication", "system": RXNORM_SYSTEM, "code": "1364430", "display": "Apixaban (Eliquis)",
      "drug_class": "anticoagulant"}),
    (r"\brivaroxaban\b|\bxarelto\b",
     {"type": "medication", "system": RXNORM_SYSTEM, "code": "1114195", "display": "Rivaroxaban (Xarelto)",
      "drug_class": "anticoagulant"}),
    (r"\bpenicillin\b.{0,20}\ballerg|\ballerg\w*\s+to\s+penicillin\b",
     {"type": "allergy", "system": SNOMED_SYSTEM, "code": "91936005", "display": "Allergy to penicillin"}),
]

DRUG_CLASS_KEYWORDS = {
    "bisphosphonate": ("alendron", "fosamax", "zoledron", "reclast", "zometa", "risedron", "ibandron"),
    "antiplatelet": ("clopidogrel", "plavix", "aspirin", "prasugrel", "ticagrelor"),
    "anticoagulant": ("warfarin", "coumadin", "apixaban", "eliquis", "rivaroxaban", "xarelto", "dabigatran"),
}

_DURATION = r"(\d+)\s*(day|week|month|year)s?"
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


def _pick_coding(concept: Dict[str, Any], preferred: tuple) -> Dict[str, Any]:
    codings = concept.get("coding") or []
    for system in preferred:
        for coding in codings:
            if coding.get("system") == system:
                return coding
    return codings[0] if codings else {}


def _drug_class(text: str) -> Optional[str]:
    lowered = text.lower()
    return next((cls for cls, keys in DRUG_CLASS_KEYWORDS.items() if any(k in lowered for k in keys)), None)


class IntakeAgent:
    name = "Intake Agent"
    icon = "clipboard-list"

    # -- FHIR normalization -------------------------------------------------

    def normalize_fhir(self, info: Dict[str, Any]) -> List[Dict[str, Any]]:
        concepts: List[Dict[str, Any]] = []
        for cond in info.get("conditions", []):
            coding = _pick_coding(cond.get("code") or {}, (ICD10_SYSTEM, SNOMED_SYSTEM))
            concepts.append({
                "type": "condition",
                "system": coding.get("system", ""),
                "code": coding.get("code", ""),
                "display": (cond.get("code") or {}).get("text") or coding.get("display", ""),
                "onset": (cond.get("onsetDateTime") or "")[:10],
                "source": "fhir",
            })
        for med in info.get("medications", []):
            concept = med.get("medicationCodeableConcept") or {}
            coding = _pick_coding(concept, (RXNORM_SYSTEM,))
            display = concept.get("text") or coding.get("display", "")
            concepts.append({
                "type": "medication",
                "system": coding.get("system", ""),
                "code": coding.get("code", ""),
                "display": display,
                "drug_class": _drug_class(f"{display} {coding.get('display', '')}"),
                "onset": (med.get("authoredOn") or "")[:10],
                "source": "fhir",
            })
        for allergy in info.get("allergies", []):
            coding = _pick_coding(allergy.get("code") or {}, (SNOMED_SYSTEM,))
            concepts.append({
                "type": "allergy",
                "system": coding.get("system", ""),
                "code": coding.get("code", ""),
                "display": (allergy.get("code") or {}).get("text") or coding.get("display", ""),
                "source": "fhir",
            })
        return concepts

    # -- conversational extraction -------------------------------------------

    def extract_from_narrative(self, narrative: str, today: Optional[date] = None) -> List[Dict[str, Any]]:
        """Normalizes a free-text intake response into coded concepts with onset/duration when stated."""
        today = today or date.today()
        concepts: List[Dict[str, Any]] = []
        # Evaluate clause by clause so "for 4 years" / "8 months ago" bind to the right concept
        for clause in re.split(r"[,.;]|\band\b", narrative):
            lowered = clause.lower()
            for pattern, template in NARRATIVE_LEXICON:
                if not re.search(pattern, lowered):
                    continue
                concept = dict(template, source="conversational", evidence=clause.strip())
                ago = re.search(_DURATION + r"\s+ago", lowered)
                duration = re.search(r"for\s+(?:the\s+(?:past|last)\s+)?" + _DURATION, lowered)
                span = ago or duration
                if span:
                    days = int(span.group(1)) * _UNIT_DAYS[span.group(2)]
                    concept["onset"] = (today - timedelta(days=days)).isoformat()
                    concept["duration_text"] = span.group(0).strip()
                concepts.append(concept)
        return concepts

    # -- node -----------------------------------------------------------------

    async def __call__(self, state: MAOState) -> Dict[str, Any]:
        patient_id = state["patient_id"]
        simulation = state.get("simulation") or {}
        info = clearance_service()._resolve_patient_info(patient_id)
        portal_linked = bool(info.get("fhir_patient"))
        logs = []

        concepts = self.normalize_fhir(info) if portal_linked else []
        narrative = simulation.get("intake_narrative") or SYNTHETIC_INTAKE_RESPONSES.get(patient_id.lower())

        if portal_linked and concepts:
            intake_status = "PORTAL_LINKED"
            logs.append(make_agent_log(
                self.name,
                "External patient portal linked",
                f"Matched {info.get('name')} to medical EHR record; pulled {len(concepts)} coded entries via FHIR R4.",
                self.icon,
            ))
        else:
            intake_status = "PENDING"
            logs.append(make_agent_log(
                self.name,
                "No linked patient portal",
                "No usable Epic MyChart / Cerner record for this patient; starting conversational intake.",
                self.icon,
            ))

        # Conversational extraction fills gaps; it never overrides coded EHR data
        if narrative and (intake_status == "PENDING" or simulation.get("intake_narrative")):
            known = {(c["system"], c["code"]) for c in concepts}
            extracted = [c for c in self.extract_from_narrative(narrative) if (c["system"], c["code"]) not in known]
            concepts.extend(extracted)
            if intake_status == "PENDING" and extracted:
                intake_status = "CONVERSATIONAL_EXTRACTED"
            logs.append(make_agent_log(
                self.name,
                "Conversational extraction",
                f'Analyzed intake response "{narrative}" -> '
                + (", ".join(f"{c['code']} ({c['display']})" for c in extracted) or "no new clinical concepts"),
                "message-square",
            ))

        def labels(kind: str) -> List[str]:
            return [f"{c['code']} {c['display']}".strip() for c in concepts if c["type"] == kind]

        logs.append(make_agent_log(
            self.name,
            "Normalized medical record",
            f"Conditions: {', '.join(labels('condition')) or 'none'}. "
            f"Medications: {', '.join(labels('medication')) or 'none'}. Routing to Clinical Risk Agent.",
            "arrow-right",
        ))

        entries = [{"resource": r} for key in ("conditions", "medications", "allergies") for r in info.get(key, [])]
        if info.get("fhir_patient"):
            entries.insert(0, {"resource": info["fhir_patient"]})
        found = bool(info.get("cs_patient") or info.get("fhir_patient"))

        return {
            "patient_name": state.get("patient_name") or (info.get("name") if found else "") or "",
            "dob": state.get("dob") or (info.get("dob") if found else "") or "",
            "medical_records": {
                "normalized_concepts": concepts,
                "conditions": labels("condition"),
                "medications": labels("medication"),
                "allergies": labels("allergy"),
                "raw_fhir_bundle": {"resourceType": "Bundle", "type": "collection", "entry": entries},
            },
            "intake_status": intake_status,
            "agent_logs": logs,
        }
