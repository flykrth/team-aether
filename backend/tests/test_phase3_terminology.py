"""
Test suite for Phase 3 of the Medical-Dental Interoperability Node (MDIN).
Verifies:
1. terminology_maps.json FHIR R4 ConceptMap structure and the 5 required mapping groups.
2. FHIRTerminologyEngine.translate_concept() $translate semantics.
3. FHIRTerminologyEngine.synthesize_patient_risk() multi-factor synthesis logic.
4. POST /api/fhir/ConceptMap/$translate endpoint.
5. POST /api/fhir/Patient/{id}/$evaluate-risks endpoint (patient-001: AFib + Warfarin + Penicillin allergy).
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.concept_map import FHIRTerminologyEngine, ConceptMapResource

client = TestClient(app)


def test_terminology_maps_file_and_schema():
    """Verify terminology_maps.json exists and is a valid FHIR R4 ConceptMap with all 5 mappings."""
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "app", "data", "terminology_maps.json"
    )
    assert os.path.exists(data_path), "terminology_maps.json must exist"

    with open(data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    cm = ConceptMapResource.model_validate(raw)
    assert cm.resourceType == "ConceptMap"
    assert cm.id == "medical-to-dental-contraindications"
    assert cm.status == "active"
    assert cm.sourceUri == "http://hl7.org/fhir/sid/icd-10-cm-and-snomed"
    assert cm.targetUri == "http://carestack.com/fhir/ValueSet/dental-clinical-alerts"

    all_codes = {(el.code, t.code, t.equivalence) for g in cm.group for el in g.element for t in el.target}
    assert ("I48.91", "BLEED_RISK_ELEVATED", "relatedto") in all_codes
    assert ("855332", "ACTIVE_ANTICOAGULANT", "equivalent") in all_codes
    assert ("315215002", "AHA_PROPHYLAXIS_REQUIRED", "wider") in all_codes
    assert ("70618001", "CONTRAINDICATION_PENICILLIN", "equivalent") in all_codes
    assert ("73211009", "DELAYED_HEALING_RISK", "narrower") in all_codes


class TestTranslateConcept:
    def setup_method(self):
        self.engine = FHIRTerminologyEngine()

    def test_translate_known_icd10_code(self):
        result = self.engine.translate_concept("http://hl7.org/fhir/sid/icd-10-cm", "I48.91")
        assert result["result"] is True
        assert len(result["match"]) == 1
        assert result["match"][0]["concept"]["code"] == "BLEED_RISK_ELEVATED"
        assert result["match"][0]["equivalence"] == "relatedto"

    def test_translate_known_rxnorm_code(self):
        result = self.engine.translate_concept(
            "http://www.nlm.nih.gov/research/umls/rxnorm", "855332"
        )
        assert result["result"] is True
        assert result["match"][0]["concept"]["code"] == "ACTIVE_ANTICOAGULANT"

    def test_translate_known_snomed_codes(self):
        valve = self.engine.translate_concept("http://snomed.info/sct", "315215002")
        assert valve["match"][0]["concept"]["code"] == "AHA_PROPHYLAXIS_REQUIRED"

        penicillin = self.engine.translate_concept("http://snomed.info/sct", "70618001")
        assert penicillin["match"][0]["concept"]["code"] == "CONTRAINDICATION_PENICILLIN"

        diabetes = self.engine.translate_concept("http://snomed.info/sct", "73211009")
        assert diabetes["match"][0]["concept"]["code"] == "DELAYED_HEALING_RISK"

    def test_translate_unknown_code_returns_no_match(self):
        result = self.engine.translate_concept("http://snomed.info/sct", "00000000")
        assert result["result"] is False
        assert result["match"] == []


class TestSynthesizePatientRisk:
    def setup_method(self):
        self.engine = FHIRTerminologyEngine()

    def _condition(self, system, code, display, patient_id="patient-001"):
        return {
            "resourceType": "Condition",
            "id": f"cond-{code}",
            "code": {"coding": [{"system": system, "code": code, "display": display}]},
            "subject": {"reference": f"Patient/{patient_id}"},
        }

    def _medication(self, system, code, display, patient_id="patient-001"):
        return {
            "resourceType": "MedicationRequest",
            "id": f"med-{code}",
            "medicationCodeableConcept": {"coding": [{"system": system, "code": code, "display": display}]},
            "subject": {"reference": f"Patient/{patient_id}"},
        }

    def _allergy(self, system, code, display, patient_id="patient-001"):
        return {
            "resourceType": "AllergyIntolerance",
            "id": f"alg-{code}",
            "code": {"coding": [{"system": system, "code": code, "display": display}]},
            "patient": {"reference": f"Patient/{patient_id}"},
        }

    def test_critical_hemorrhage_hazard_escalation(self):
        conditions = [self._condition("http://hl7.org/fhir/sid/icd-10-cm", "I48.91", "AFib")]
        medications = [
            self._medication("http://www.nlm.nih.gov/research/umls/rxnorm", "855332", "Warfarin Sodium 5 MG")
        ]
        alerts = self.engine.synthesize_patient_risk(conditions, medications, [])

        critical = [a for a in alerts if a["code"] == "CRITICAL_HEMORRHAGE_HAZARD"]
        assert len(critical) == 1

        escalated = [a for a in alerts if a["priority"] == "CRITICAL_HEMORRHAGE_HAZARD"]
        escalated_codes = {a["code"] for a in escalated}
        assert "BLEED_RISK_ELEVATED" in escalated_codes
        assert "ACTIVE_ANTICOAGULANT" in escalated_codes

    def test_prophylaxis_penicillin_conflict_warning(self):
        conditions = [self._condition("http://snomed.info/sct", "315215002", "Prosthetic valve")]
        allergies = [self._allergy("http://snomed.info/sct", "70618001", "Penicillin allergy")]
        alerts = self.engine.synthesize_patient_risk(conditions, [], allergies)

        conflict = [a for a in alerts if a["code"] == "PROPHYLAXIS_PENICILLIN_CONFLICT"]
        assert len(conflict) == 1
        assert "AMOXICILLIN CONTRAINDICATED" in conflict[0]["warnings"][0]

        prophylaxis_alert = next(a for a in alerts if a["code"] == "AHA_PROPHYLAXIS_REQUIRED")
        assert any("AMOXICILLIN CONTRAINDICATED" in w for w in prophylaxis_alert["warnings"])

    def test_no_synthesis_without_matching_factors(self):
        conditions = [self._condition("http://snomed.info/sct", "73211009", "Diabetes")]
        alerts = self.engine.synthesize_patient_risk(conditions, [], [])
        codes = {a["code"] for a in alerts}
        assert "CRITICAL_HEMORRHAGE_HAZARD" not in codes
        assert "PROPHYLAXIS_PENICILLIN_CONFLICT" not in codes
        assert "DELAYED_HEALING_RISK" in codes


class TestTerminologyEndpoints:
    def test_translate_endpoint(self):
        resp = client.post(
            "/api/fhir/ConceptMap/$translate",
            json={"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "I48.91"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"] is True
        assert data["match"][0]["concept"]["code"] == "BLEED_RISK_ELEVATED"

    def test_translate_endpoint_unknown_code(self):
        resp = client.post(
            "/api/fhir/ConceptMap/$translate",
            json={"system": "http://snomed.info/sct", "code": "unknown-code"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] is False

    def test_evaluate_risks_patient_001_critical_hazard(self):
        """patient-001 (John Doe): AFib + Warfarin + Penicillin allergy -> critical hemorrhage hazard."""
        resp = client.post(
            "/api/fhir/Patient/patient-001/$evaluate-risks",
            json={"procedureCode": "D7140"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["patientId"] == "patient-001"
        assert data["procedure"] == {"system": "http://www.ada.org/cdt", "code": "D7140"}

        codes = {a["code"] for a in data["alerts"]}
        assert "CRITICAL_HEMORRHAGE_HAZARD" in codes
        assert "CONTRAINDICATION_PENICILLIN" in codes

    def test_evaluate_risks_no_body_still_works(self):
        resp = client.post("/api/fhir/Patient/patient-002/$evaluate-risks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["patientId"] == "patient-002"
        assert data["procedure"] is None

    def test_evaluate_risks_unknown_patient_404(self):
        resp = client.post("/api/fhir/Patient/not-a-real-patient/$evaluate-risks")
        assert resp.status_code == 404
