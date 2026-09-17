"""
FHIR Terminology Service for the Medical-Dental Interoperability Node (MDIN) - Phase 3.
Implements ConceptMap-driven semantic translation of medical codes (ICD-10-CM, SNOMED-CT,
RxNorm) into dental clinical decision support alerts, using $translate operation semantics,
plus multi-factor risk synthesis across a patient's conditions, medications, and allergies.
"""

import json
import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class FHIRBaseModel(BaseModel):
    """Base model allowing standard FHIR extensions and meta attributes."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# --- ConceptMap resource models -------------------------------------------------

class ConceptMapTarget(FHIRBaseModel):
    """A single target concept and its equivalence to the source concept."""
    code: str = Field(..., description="Target dental clinical alert code")
    display: Optional[str] = Field(None, description="Human readable target display text")
    equivalence: str = Field(
        "equivalent",
        description="relatedto | equivalent | equal | wider | subsumes | narrower | specializes | inexact | unmatched | disjoint",
    )


class ConceptMapElement(FHIRBaseModel):
    """A source concept and the target concept(s) it maps to."""
    code: str = Field(..., description="Source medical code (ICD-10-CM / SNOMED-CT / RxNorm)")
    display: Optional[str] = Field(None, description="Human readable source display text")
    target: List[ConceptMapTarget] = Field(default_factory=list, description="Target concept(s)")


class ConceptMapGroup(FHIRBaseModel):
    """A group of mappings sharing a common source and target terminology system."""
    source: Optional[str] = Field(None, description="Source terminology system URI")
    target: Optional[str] = Field(None, description="Target terminology system URI")
    element: List[ConceptMapElement] = Field(default_factory=list, description="Mappings for this group")


class ConceptMapResource(FHIRBaseModel):
    """HL7 FHIR R4 ConceptMap Resource."""
    resourceType: str = Field("ConceptMap", description="HL7 FHIR Resource Type")
    id: str = Field(..., description="Logical id of this artifact")
    status: str = Field("active", description="draft | active | retired | unknown")
    sourceUri: Optional[str] = Field(None, description="Source value set/system URI")
    targetUri: Optional[str] = Field(None, description="Target value set/system URI")
    group: List[ConceptMapGroup] = Field(default_factory=list, description="Mapping groups")


# --- $translate operation models -------------------------------------------------

class TranslateParameters(BaseModel):
    """Input parameters for the FHIR $translate operation."""
    system: str = Field(..., description="Source terminology system URI of the code to translate")
    code: str = Field(..., description="Source code to translate")
    target: Optional[str] = Field(None, description="Target value set/system URI to constrain the translation")


class TranslateMatch(BaseModel):
    """A single match returned by the $translate operation."""
    equivalence: str = Field(..., description="Degree of equivalence between source and target concepts")
    concept: Dict[str, Any] = Field(..., description="Target concept as a Coding {system, code, display}")
    source: Optional[str] = Field(None, description="ConceptMap id/url that produced this match")


class TranslateOutcome(BaseModel):
    """Output of the FHIR $translate operation, shaped as simplified FHIR Parameters."""
    resourceType: str = Field("Parameters", description="HL7 FHIR Resource Type")
    result: bool = Field(..., description="Whether a translation match was found")
    message: Optional[str] = Field(None, description="Additional information about the translation result")
    match: List[TranslateMatch] = Field(default_factory=list, description="Matches found for the source concept")


# --- Terminology engine -----------------------------------------------------------

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
TERMINOLOGY_MAP_FILE = os.path.join(DATA_DIR, "terminology_maps.json")

TARGET_SYSTEM = "http://carestack.com/fhir/ValueSet/dental-clinical-alerts"

ANTICOAGULANT_TARGET_CODES = {"ACTIVE_ANTICOAGULANT"}
CARDIOVASCULAR_TARGET_CODES = {"BLEED_RISK_ELEVATED", "AHA_PROPHYLAXIS_REQUIRED"}
PROPHYLAXIS_TARGET_CODES = {"AHA_PROPHYLAXIS_REQUIRED"}
PENICILLIN_ALLERGY_TARGET_CODES = {"CONTRAINDICATION_PENICILLIN"}


class FHIRTerminologyEngine:
    """
    Loads FHIR R4 ConceptMap resources and exposes $translate operation semantics
    plus multi-factor dental risk synthesis over a patient's clinical record.
    """

    def __init__(self):
        self.concept_maps: List[ConceptMapResource] = []
        self.load_concept_maps()

    def load_concept_maps(self) -> None:
        """Load all ConceptMap resources from the data/ directory."""
        self.concept_maps = []
        if not os.path.exists(TERMINOLOGY_MAP_FILE):
            return
        with open(TERMINOLOGY_MAP_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        self.concept_maps.append(ConceptMapResource.model_validate(raw))

    def _find_matches(self, source_system: str, source_code: str) -> List[TranslateMatch]:
        """Find all target matches for a given source system + code across loaded ConceptMaps."""
        matches: List[TranslateMatch] = []
        for cm in self.concept_maps:
            for group in cm.group:
                if group.source and group.source != source_system:
                    continue
                for element in group.element:
                    if element.code != source_code:
                        continue
                    for target in element.target:
                        matches.append(
                            TranslateMatch(
                                equivalence=target.equivalence,
                                concept={
                                    "system": group.target or TARGET_SYSTEM,
                                    "code": target.code,
                                    "display": target.display,
                                },
                                source=cm.id,
                            )
                        )
        return matches

    def translate_concept(self, source_system: str, source_code: str) -> Dict[str, Any]:
        """
        Translate a single medical code (system + code) into dental clinical alert
        concept(s), using FHIR ConceptMap $translate operation semantics.
        """
        matches = self._find_matches(source_system, source_code)
        outcome = TranslateOutcome(
            result=len(matches) > 0,
            message=(
                f"{len(matches)} match(es) found for {source_system}|{source_code}"
                if matches
                else f"No mapping found for {source_system}|{source_code}"
            ),
            match=matches,
        )
        return outcome.model_dump()

    def _extract_codings(self, resource: Dict[str, Any], concept_key: str) -> List[Dict[str, Optional[str]]]:
        """Extract {system, code, display} tuples from a resource's CodeableConcept field."""
        concept = resource.get(concept_key) or {}
        codings = concept.get("coding") or []
        return [{"system": c.get("system"), "code": c.get("code"), "display": c.get("display")} for c in codings]

    def synthesize_patient_risk(
        self,
        conditions: List[Dict[str, Any]],
        medications: List[Dict[str, Any]],
        allergies: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Translate every coded condition, medication, and allergy for a patient into
        dental clinical alerts, then apply multi-factor synthesis logic:

        - Anticoagulant therapy + cardiovascular diagnosis => escalate to
          CRITICAL_HEMORRHAGE_HAZARD priority.
        - AHA antibiotic prophylaxis required + penicillin allergy => attach an
          explicit contraindication warning.
        """
        alerts: List[Dict[str, Any]] = []
        target_codes_seen: set = set()

        def _translate_all(resources: List[Dict[str, Any]], concept_key: str, source_note: str):
            for res in resources:
                for coding in self._extract_codings(res, concept_key):
                    system, code = coding.get("system"), coding.get("code")
                    if not system or not code:
                        continue
                    outcome = self.translate_concept(system, code)
                    for match in outcome["match"]:
                        target_code = match["concept"]["code"]
                        target_codes_seen.add(target_code)
                        alerts.append(
                            {
                                "code": target_code,
                                "display": match["concept"].get("display"),
                                "equivalence": match["equivalence"],
                                "priority": "standard",
                                "source": {
                                    "type": source_note,
                                    "system": system,
                                    "code": code,
                                    "resourceId": res.get("id"),
                                },
                                "warnings": [],
                            }
                        )

        _translate_all(conditions, "code", "Condition")
        _translate_all(medications, "medicationCodeableConcept", "MedicationRequest")
        _translate_all(allergies, "code", "AllergyIntolerance")

        has_anticoagulant = bool(target_codes_seen & ANTICOAGULANT_TARGET_CODES)
        has_cardiovascular_dx = bool(target_codes_seen & CARDIOVASCULAR_TARGET_CODES)
        requires_prophylaxis = bool(target_codes_seen & PROPHYLAXIS_TARGET_CODES)
        has_penicillin_allergy = bool(target_codes_seen & PENICILLIN_ALLERGY_TARGET_CODES)

        if has_anticoagulant and has_cardiovascular_dx:
            for alert in alerts:
                if alert["code"] in (ANTICOAGULANT_TARGET_CODES | CARDIOVASCULAR_TARGET_CODES):
                    alert["priority"] = "CRITICAL_HEMORRHAGE_HAZARD"
            alerts.append(
                {
                    "code": "CRITICAL_HEMORRHAGE_HAZARD",
                    "display": "Active anticoagulant therapy combined with cardiovascular diagnosis - critical hemorrhage risk for invasive dental procedures",
                    "equivalence": "relatedto",
                    "priority": "CRITICAL_HEMORRHAGE_HAZARD",
                    "source": {"type": "synthesis", "rule": "anticoagulant+cardiovascular"},
                    "warnings": [],
                }
            )

        if requires_prophylaxis and has_penicillin_allergy:
            warning = "AMOXICILLIN CONTRAINDICATED. Recommend non-beta-lactam alternative."
            for alert in alerts:
                if alert["code"] in (PROPHYLAXIS_TARGET_CODES | PENICILLIN_ALLERGY_TARGET_CODES):
                    if warning not in alert["warnings"]:
                        alert["warnings"].append(warning)
            alerts.append(
                {
                    "code": "PROPHYLAXIS_PENICILLIN_CONFLICT",
                    "display": "AHA antibiotic prophylaxis required but patient has penicillin allergy",
                    "equivalence": "relatedto",
                    "priority": "high",
                    "source": {"type": "synthesis", "rule": "prophylaxis+penicillin_allergy"},
                    "warnings": [warning],
                }
            )

        return alerts


terminology_engine = FHIRTerminologyEngine()
