"""
Test Suite for Step 8: Administrative Decision Support & Medical Cross-Coding Engine.
DSOLVE 2026 - DRISHTI, College of Engineering Trivandrum (CET).

Verifies:
1. HL7 FHIR ConceptMap cdt-to-cpt-crosswalk resource in terminology_maps.json with all 3 mappings.
2. CMS-1500 & ANSI ASC X12N 837P Pydantic claims models.
3. AdministrativeCrossCodingEngine evaluation logic:
   - Mapping 1: Surgical Extraction (D7210 / D7240) + Maxillofacial/TMJ/Bone Pathology (M26.61, K01.1, M27.2)
   - Mapping 2: Periodontal Surgery / Deep Infection (D4260 / D4341) + Diabetes Mellitus (E11.9)
   - Mapping 3: Biopsy / Oral Lesion Removal (D7286) + Leukoplakia (K13.21)
   - Ineligible / Negative cases (missing qualifying diagnosis, unmapped CDT)
4. API Endpoints:
   - POST /api/billing/evaluate-claim (Patient ID resolution and custom conditions)
   - GET /api/billing/crosswalk-rules
   - POST /api/billing/generate-837p
   - POST /cds-services/evaluate-claim (CDS Hooks bridge alias)
"""

import os
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.concept_map import ConceptMapResource
from backend.app.services.crosswalk_engine import AdministrativeCrossCodingEngine, crosswalk_engine
from backend.app.models.claims import (
    CMS1500Claim,
    ClaimServiceLine,
    BillingProvider,
    DiagnosisCode,
    CrossCodingOpportunity,
)

client = TestClient(app)

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "data", "terminology_maps.json")


# ==============================================================================
# Tier 1: HL7 FHIR ConceptMap cdt-to-cpt-crosswalk Resource Tests
# ==============================================================================

def test_fhir_concept_map_crosswalk_structure():
    """Verify cdt-to-cpt-crosswalk ConceptMap exists and complies with HL7 FHIR R4 specifications."""
    assert os.path.exists(DATA_PATH), "terminology_maps.json must exist"

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    assert isinstance(raw, list), "terminology_maps.json should contain a collection of ConceptMaps"
    crosswalk_raw = next((item for item in raw if item.get("id") == "cdt-to-cpt-crosswalk"), None)
    assert crosswalk_raw is not None, "cdt-to-cpt-crosswalk ConceptMap must exist"

    cm = ConceptMapResource.model_validate(crosswalk_raw)
    assert cm.resourceType == "ConceptMap"
    assert cm.id == "cdt-to-cpt-crosswalk"
    assert cm.status == "active"
    assert cm.sourceUri == "http://www.ada.org/cdt"
    assert cm.targetUri == "http://www.ama-assn.org/go/cpt"

    elements = {el.code: el for g in cm.group for el in g.element}

    # Mapping 1: D7210 and D7240 (Surgical extraction with bone impaction)
    assert "D7210" in elements
    assert "D7240" in elements
    d7210_targets = {t.code: t for t in elements["D7210"].target}
    assert "41899" in d7210_targets or "21210" in d7210_targets
    t1 = d7210_targets.get("41899")
    assert "M26.61" in t1.qualifying_icd10
    assert "K01.1" in t1.qualifying_icd10
    assert "M27.2" in t1.qualifying_icd10
    assert t1.estimated_coverage_min == 650.0
    assert t1.estimated_coverage_max == 1200.0

    # Mapping 2: D4260 and D4341 (Periodontal surgery / scaling with systemic impact)
    assert "D4260" in elements
    assert "D4341" in elements
    d4341_targets = {t.code: t for t in elements["D4341"].target}
    assert "41874" in d4341_targets
    t2 = d4341_targets["41874"]
    assert "E11.9" in t2.qualifying_icd10
    assert t2.estimated_coverage_min == 400.0
    assert t2.estimated_coverage_max == 800.0

    # Mapping 3: D7286 (Biopsy / oral lesion removal)
    assert "D7286" in elements
    d7286_targets = {t.code: t for t in elements["D7286"].target}
    assert "40808" in d7286_targets
    t3 = d7286_targets["40808"]
    assert "K13.21" in t3.qualifying_icd10
    assert t3.estimated_coverage_min == 350.0
    assert t3.estimated_coverage_max == 600.0


# ==============================================================================
# Tier 2: CMS-1500 & Electronic 837P Claims Pydantic Models
# ==============================================================================

def test_cms1500_claim_model_instantiation_and_validation():
    """Verify CMS1500Claim model fields, Box 1-33 compliance, and 837P EDI formatting."""
    claim = CMS1500Claim(
        insurance_type="GROUP_HEALTH_PLAN",
        insured_id="MED-10003",
        patient_name="Taylor, Robert",
        patient_dob="1974-11-05",
        patient_gender="male",
        patient_address="45 Elm Street, Boston, MA 02115",
        diagnosis_codes=["E11.9"],  # String list normalized to DiagnosisCode with pointer 'A'
        service_lines=[
            ClaimServiceLine(
                date_of_service="2026-09-18",
                place_of_service="11",
                cpt_code="41874",
                modifiers=[],
                diagnosis_pointer="A",
                charges=600.0,
                days_or_units=1,
            )
        ],
        billing_provider=BillingProvider(
            provider_npi="1928374650",
            clinic_name="CareStack Center for Advanced Dentistry",
            address="100 Healthcare Boulevard, Suite 400, Boston, MA 02115",
            taxonomy_code="1223S0112X",
            phone="(555) 019-2830",
        ),
    )

    # Validate header demographics
    assert claim.insurance_type == "GROUP_HEALTH_PLAN"
    assert claim.insured_id == "MED-10003"
    assert claim.patient_name == "Taylor, Robert"
    assert claim.patient_dob == "1974-11-05"
    assert claim.patient_gender == "male"
    assert "02115" in claim.patient_address

    # Validate Box 21 diagnoses and automatic pointer normalization
    assert len(claim.diagnosis_codes) == 1
    assert claim.diagnosis_codes[0].pointer == "A"
    assert claim.diagnosis_codes[0].code == "E11.9"

    # Validate Box 24 line items and automatic totals computation
    assert len(claim.service_lines) == 1
    assert claim.service_lines[0].cpt_code == "41874"
    assert claim.service_lines[0].charges == 600.0
    assert claim.total_charge == 600.0
    assert claim.balance_due == 600.0

    # Validate Box 33 billing provider
    assert claim.billing_provider.provider_npi == "1928374650"
    assert claim.billing_provider.taxonomy_code == "1223S0112X"

    # Validate ANSI ASC X12N 837P EDI segment generation
    edi = claim.edi_837p_preview
    assert edi is not None
    assert "ISA*" in edi
    assert "GS*HC*" in edi
    assert "ST*837*" in edi
    assert "CLM*" in edi
    assert "HI*BK:E11.9" in edi
    assert "SV1*HC:41874*600.00" in edi
    assert "SE*" in edi


def test_cross_coding_opportunity_model():
    """Verify CrossCodingOpportunity model instantiation and serialization."""
    opp = CrossCodingOpportunity(
        is_eligible=True,
        cdt_code="D4341",
        suggested_cpt="41874",
        justifying_icd10=["E11.9"],
        estimated_coverage=600.0,
        reimbursement_category="Systemic complication linkage ($400 - $800 medical coverage)",
        narrative_justification="Patient qualified by Type 2 Diabetes Mellitus",
    )
    assert opp.is_eligible is True
    assert opp.cdt_code == "D4341"
    assert opp.suggested_cpt == "41874"
    assert opp.estimated_coverage == 600.0
    assert opp.justifying_icd10 == ["E11.9"]


# ==============================================================================
# Tier 3: AdministrativeCrossCodingEngine Unit Evaluation Tests
# ==============================================================================

class TestAdministrativeCrossCodingEngine:
    def setup_method(self):
        self.engine = AdministrativeCrossCodingEngine()

    def test_mapping_1_surgical_extraction_with_tmj(self):
        """Mapping 1: D7210 + M26.61 (TMJ arthralgia) -> CPT 41899, Eligible, $925.00."""
        conditions = [
            {
                "resourceType": "Condition",
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "M26.61", "display": "TMJ arthralgia"}]},
            }
        ]
        demographics = {
            "patient_name": "Chen, Marcus",
            "birth_date": "1985-06-14",
            "gender": "male",
            "mrn": "MRN-10004",
        }
        opp = self.engine.evaluate_cross_coding("D7210", conditions, demographics)
        assert opp.is_eligible is True
        assert opp.suggested_cpt == "41899"
        assert "M26.61" in opp.justifying_icd10
        assert opp.estimated_coverage == 925.0
        assert opp.claim_preview is not None
        assert opp.claim_preview.diagnosis_codes[0].code == "M26.61"
        assert opp.claim_preview.service_lines[0].cpt_code == "41899"

    def test_mapping_1_bony_impaction_with_cystic_degeneration(self):
        """Mapping 1: D7240 + K01.1 (Impacted teeth with cystic degeneration) -> CPT 41899, Modifier 22."""
        conditions = ["K01.1"]
        demographics = {"patient_name": "Test, Patient", "mrn": "12345"}
        opp = self.engine.evaluate_cross_coding("D7240", conditions, demographics)
        assert opp.is_eligible is True
        assert opp.suggested_cpt == "41899"
        assert "K01.1" in opp.justifying_icd10
        assert opp.claim_preview.service_lines[0].modifiers == ["22"]

    def test_mapping_2_periodontal_scaling_with_type_2_diabetes(self):
        """Mapping 2: D4341 + E11.9 (Type 2 Diabetes Mellitus) -> CPT 41874, $600.00."""
        conditions = [
            {
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E11.9"}]},
            }
        ]
        opp = self.engine.evaluate_cross_coding("D4341", conditions)
        assert opp.is_eligible is True
        assert opp.suggested_cpt == "41874"
        assert "E11.9" in opp.justifying_icd10
        assert opp.estimated_coverage == 600.0
        assert opp.claim_preview is not None
        assert opp.claim_preview.diagnosis_codes[0].code == "E11.9"

    def test_mapping_2_osseous_surgery_with_type_2_diabetes(self):
        """Mapping 2: D4260 + E11.9 -> CPT 41874."""
        opp = self.engine.evaluate_cross_coding("D4260", ["E11.9"])
        assert opp.is_eligible is True
        assert opp.suggested_cpt == "41874"
        assert opp.estimated_coverage == 600.0

    def test_mapping_3_incisional_biopsy_with_leukoplakia(self):
        """Mapping 3: D7286 + K13.21 (Leukoplakia of oral mucosa) -> CPT 40808, $475.00."""
        opp = self.engine.evaluate_cross_coding("D7286", ["K13.21"])
        assert opp.is_eligible is True
        assert opp.suggested_cpt == "40808"
        assert "K13.21" in opp.justifying_icd10
        assert opp.estimated_coverage == 475.0
        assert opp.claim_preview is not None
        assert opp.claim_preview.service_lines[0].cpt_code == "40808"

    def test_ineligible_scaling_without_diabetes(self):
        """Negative: D4341 with AFib (I48.91) only -> Ineligible, claim_preview is None."""
        opp = self.engine.evaluate_cross_coding("D4341", ["I48.91"])
        assert opp.is_eligible is False
        assert opp.claim_preview is None
        assert opp.suggested_cpt == "41874"
        assert opp.justifying_icd10 == []
        assert opp.estimated_coverage == 0.0
        assert "requires qualifying medical diagnoses" in opp.narrative_justification

    def test_unmapped_procedure_code(self):
        """Negative: D0120 has no crosswalk rule."""
        opp = self.engine.evaluate_cross_coding("D0120", ["E11.9", "M26.61"])
        assert opp.is_eligible is False
        assert opp.suggested_cpt is None
        assert opp.claim_preview is None
        assert opp.estimated_coverage == 0.0


# ==============================================================================
# Tier 4: FastAPI REST Endpoints Tests
# ==============================================================================

def test_api_evaluate_claim_patient_robert_taylor():
    """Test POST /api/billing/evaluate-claim for synthetic patient Robert Taylor (patient-003 with E11.9)."""
    resp = client.post(
        "/api/billing/evaluate-claim",
        json={"patient_id": "patient-003", "cdt_code": "D4341"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["is_eligible"] is True
    assert data["cdt_code"] == "D4341"
    assert data["suggested_cpt"] == "41874"
    assert "E11.9" in data["justifying_icd10"]
    assert data["estimated_coverage"] == 600.0

    # Verify complete CMS-1500 JSON payload
    claim = data["claim_preview"]
    assert claim is not None
    assert "Taylor" in claim["patient_name"] or "Robert" in claim["patient_name"]
    assert claim["patient_gender"] == "male"
    assert len(claim["diagnosis_codes"]) >= 1
    assert claim["diagnosis_codes"][0]["code"] == "E11.9"
    assert claim["diagnosis_codes"][0]["pointer"] == "A"
    assert claim["service_lines"][0]["cpt_code"] == "41874"
    assert claim["service_lines"][0]["charges"] == 600.0
    assert claim["billing_provider"]["provider_npi"] == "1928374650"
    assert claim["billing_provider"]["taxonomy_code"] == "1223S0112X"
    assert "ISA*" in claim["edi_837p_preview"]
    assert "SV1*HC:41874" in claim["edi_837p_preview"]


def test_api_evaluate_claim_with_custom_conditions():
    """Test POST /api/billing/evaluate-claim with explicitly provided conditions payload."""
    resp = client.post(
        "/api/billing/evaluate-claim",
        json={
            "patient_id": "CS-2001",
            "cdt_code": "D7210",
            "conditions": ["M26.61"],
            "demographics": {
                "patient_name": "DOE, JOHN",
                "patient_dob": "1968-04-12",
                "patient_gender": "male",
                "patient_address": "100 Main St, Boston, MA 02115",
            },
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_eligible"] is True
    assert data["suggested_cpt"] == "41899"
    assert data["justifying_icd10"] == ["M26.61"]
    assert data["estimated_coverage"] == 925.0
    assert data["claim_preview"]["patient_name"] == "DOE, JOHN"


def test_api_evaluate_claim_ineligible():
    """Test POST /api/billing/evaluate-claim for ineligible patient without qualifying diagnoses."""
    resp = client.post(
        "/api/billing/evaluate-claim",
        json={"patient_id": "patient-001", "cdt_code": "D4341"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_eligible"] is False
    assert data["claim_preview"] is None
    assert data["estimated_coverage"] == 0.0


def test_api_get_crosswalk_rules():
    """Test GET /api/billing/crosswalk-rules returns active rules metadata and groups."""
    resp = client.get("/api/billing/crosswalk-rules")
    assert resp.status_code == 200
    data = resp.json()
    assert "metadata" in data
    assert data["metadata"]["id"] == "cdt-to-cpt-crosswalk"
    assert "rules" in data
    assert "D7210" in data["rules"]
    assert "D4341" in data["rules"]
    assert "D7286" in data["rules"]


def test_api_generate_837p_endpoint():
    """Test POST /api/billing/generate-837p converts CMS1500Claim to EDI 837P string."""
    claim_payload = {
        "insurance_type": "GROUP_HEALTH_PLAN",
        "insured_id": "MED-9999",
        "patient_name": "Smith, Alice",
        "patient_dob": "1980-01-01",
        "patient_gender": "female",
        "patient_address": "10 Main St, Boston, MA",
        "diagnosis_codes": ["K13.21"],
        "service_lines": [
            {
                "date_of_service": "2026-09-18",
                "place_of_service": "11",
                "cpt_code": "40808",
                "modifiers": [],
                "diagnosis_pointer": "A",
                "charges": 475.0,
                "days_or_units": 1,
            }
        ],
    }
    resp = client.post("/api/billing/generate-837p", json=claim_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "ISA*" in data["edi_content"]
    assert "SV1*HC:40808*475.00" in data["edi_content"]


def test_cds_bridge_evaluate_claim():
    """Test POST /cds-services/evaluate-claim bridge endpoint."""
    resp = client.post(
        "/cds-services/evaluate-claim",
        json={"patient_id": "patient-003", "cdt_code": "D4341"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_eligible"] is True
    assert data["suggested_cpt"] == "41874"
    assert data["claim_preview"] is not None
