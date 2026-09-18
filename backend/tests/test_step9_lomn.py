"""
Test Suite for Step 9: Automated Letter of Medical Necessity (LOMN) Generation & Mock CareStack Document Ingestion.
DSOLVE 2026 - DRISHTI, College of Engineering Trivandrum (CET).

Verifies:
1. MedicalNecessityGenerator:
   - Clinical justifications formatted for major medical payers (Aetna, Delta Dental, UnitedHealthcare).
   - Patient Details (Full Name, DOB, MRN, CareStack Account ID).
   - Referring / Attending Clinician (Dr. Sarah Jenkins, DDS, NPI: 1982736450).
   - Clinical Indications & Systemic Nexus:
     * Links systemic diagnoses (E11.9 Diabetes, I48.91 Atrial Fibrillation, M26.61 TMJ, K13.21 Leukoplakia) to dental procedures (D4341 / CPT 41874, D7210 / CPT 41899, D7286 / CPT 40808).
     * Highlights systemic risks if left untreated (glycemic instability, uncontrolled infection, osteomyelitis).
   - Recommended Medical Coding Cross-Walk (Primary ICD-10, Secondary ICD-10, CPT).
   - Formal Attestation & Signature Block.
   - Dual output generation: Clean JSON, Markdown, and styled HTML document.
2. CareStack Document Management Mock Endpoints:
   - POST /api/carestack/patients/{patient_id}/documents (JSON & multipart/form-data).
   - GET /api/carestack/patients/{patient_id}/documents.
   - Persists documents in patient's attached_documents array.
   - SHA-256 verification hash and unique document_id generation.
3. Billing Router Orchestration Endpoint:
   - POST /api/billing/generate-and-attach-lomn:
     * Demographic resolution from CareStack mock.
     * Active condition & medication resolution from FHIR mock.
     * Crosswalk evaluation via AdministrativeCrossCodingEngine.
     * LOMN generation via MedicalNecessityGenerator.
     * Automatic ingestion into CareStack patient documents.
"""

import hashlib
import json
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.document_generator import (
    MedicalNecessityGenerator,
    medical_necessity_generator,
    CLINICIAN_SARAH_JENKINS,
)
from backend.app.routers.carestack_mock import (
    MOCK_PATIENTS,
    CARESTACK_PATIENT_DOCUMENTS,
    save_patient_document,
)
from backend.app.services.carestack_client import CareStackClient

client = TestClient(app)


# ==============================================================================
# Tier 1: MedicalNecessityGenerator Unit Tests
# ==============================================================================

class TestMedicalNecessityGenerator:
    """Unit tests for clinical Letter of Medical Necessity synthesis."""

    def setup_method(self):
        self.generator = MedicalNecessityGenerator()

    def test_clinician_details_default(self):
        """Verify referring / attending clinician is Dr. Sarah Jenkins, DDS with NPI: 1982736450."""
        clinician = self.generator.clinician
        assert clinician["name"] == "Dr. Sarah Jenkins, DDS"
        assert clinician["npi"] == "1982736450"
        assert "CareStack Center for Advanced Dentistry" in clinician["clinic_name"]
        assert "MA-DN884190" in clinician["state_license"]

    def test_lomn_diabetes_periodontal_nexus(self):
        """
        Verify LOMN for Type 2 Diabetes (E11.9) + Periodontal Scaling (D4341 -> CPT 41874):
        - Links diabetes to periodontal infection.
        - Highlights glycemic instability, uncontrolled infection, osteomyelitis.
        - Formulates primary ICD-10 E11.9, proposed CPT 41874.
        """
        patient_data = {
            "full_name": "Robert Taylor",
            "dob": "1974-11-05",
            "mrn": "MRN-10003",
            "account_id": "CS-2003",
            "gender": "Male",
            "address": "45 Elm Street, Boston, MA 02115",
        }
        clinical_findings = {
            "conditions": [
                {"code": "E11.9", "display": "Type 2 diabetes mellitus without complications"}
            ],
            "medications": ["Metformin 1000mg oral tablet", "Glipizide 5mg"],
            "observations": [
                {"code": {"text": "Hemoglobin A1c"}, "valueQuantity": {"value": 8.6, "unit": "%"}}
            ],
        }
        crosswalk_data = {
            "cdt_code": "D4341",
            "cdt_display": "Periodontal scaling and root planing - four or more teeth per quadrant",
            "suggested_cpt": "41874",
            "cpt_display": "Periodontal mucosal debridement / scaling",
            "estimated_coverage": 600.0,
            "reimbursement_category": "Medical Cross-Coding Eligible - Systemic Nexus",
        }

        result = self.generator.generate_letter_of_medical_necessity(
            patient_data=patient_data,
            clinical_findings=clinical_findings,
            crosswalk_data=crosswalk_data,
        )

        assert result["document_type"] == "Letter of Medical Necessity"
        assert "Robert Taylor" in result["title"]
        assert "D4341" in result["title"]
        assert "41874" in result["title"]

        # 1. Patient Details
        pt = result["patient_summary"]
        assert pt["full_name"] == "Robert Taylor"
        assert pt["dob"] == "1974-11-05"
        assert pt["mrn"] == "MRN-10003"
        assert pt["account_id"] == "CS-2003"

        # 2. Attending Clinician
        clin = result["clinician"]
        assert clin["name"] == "Dr. Sarah Jenkins, DDS"
        assert clin["npi"] == "1982736450"

        # 3. Clinical Indications & Systemic Nexus
        nexus = result["clinical_nexus"]
        assert nexus["primary_diagnosis"]["code"] == "E11.9"
        assert "diabetes" in nexus["primary_diagnosis"]["display"].lower()
        narrative = nexus["nexus_narrative"].lower()
        assert "diabetes" in narrative
        assert "periodontal" in narrative
        assert "insulin" in narrative or "glycemic" in narrative

        # Highlight systemic risks if left untreated
        risks = " ".join(nexus["untreated_risks"]).lower()
        assert "glycemic instability" in risks
        assert "uncontrolled infection" in risks
        assert "osteomyelitis" in risks

        # 4. Recommended Medical Coding Cross-Walk
        cw = result["coding_crosswalk"]
        assert cw["primary_icd10"]["code"] == "E11.9"
        assert cw["proposed_cpt"]["code"] == "41874"
        assert cw["proposed_cpt"]["equivalent_cdt"] == "D4341"
        assert cw["proposed_cpt"]["estimated_reimbursement"] == 600.0

        # 5. Attestation & Signature Block
        attestation = result["attestation"]
        assert "Dr. Sarah Jenkins, DDS" in attestation["statement"]
        assert "penalty of perjury" in attestation["statement"]
        assert attestation["signature"]["npi"] == "1982736450"

        # Formats: JSON, Markdown, HTML
        assert isinstance(result["content_json"], dict)
        assert "# FORMAL LETTER OF MEDICAL NECESSITY" in result["content_markdown"]
        assert "Robert Taylor" in result["content_markdown"]
        assert "1982736450" in result["content_markdown"]
        assert "<!DOCTYPE html>" in result["content_html"]
        assert "<html" in result["content_html"]
        assert "Letter of Medical Necessity" in result["content_html"]

    def test_lomn_tmj_bony_impaction_nexus(self):
        """
        Verify LOMN for TMJ / Bony Impaction (M26.61, K01.1) + Surgical Extraction (D7210 / D7240 -> CPT 41899).
        Highlights untreated risks: osteomyelitis, mandibular fracture, nerve injury.
        """
        patient_data = {
            "patient_name": "Marcus Chen",
            "birth_date": "1985-06-14",
            "mrn": "MRN-10004",
            "id": "CS-2004",
        }
        clinical_findings = {
            "conditions": ["M26.61", "K01.1"],
            "medications": ["Ibuprofen 800mg"],
        }
        crosswalk_data = {
            "cdt_code": "D7210",
            "suggested_cpt": "41899",
            "estimated_coverage": 925.0,
        }

        result = self.generator.generate_letter_of_medical_necessity(
            patient_data=patient_data,
            clinical_findings=clinical_findings,
            crosswalk_data=crosswalk_data,
        )

        nexus = result["clinical_nexus"]
        assert nexus["primary_diagnosis"]["code"] in ["M26.61", "K01.1"]
        risks = " ".join(nexus["untreated_risks"]).lower()
        assert "osteomyelitis" in risks
        assert "uncontrolled infection" in risks

    def test_lomn_oral_leukoplakia_biopsy_nexus(self):
        """
        Verify LOMN for Oral Leukoplakia (K13.21) + Biopsy (D7286 -> CPT 40808).
        Highlights risks of untreated dysplasia and malignant transformation.
        """
        patient_data = {
            "patient_name": "Sarah Jenkins",
            "birth_date": "1972-03-29",
            "mrn": "MRN-10005",
            "id": "CS-2005",
        }
        clinical_findings = {
            "conditions": [{"code": "K13.21", "display": "Leukoplakia of oral mucosa"}],
            "medications": [],
        }
        crosswalk_data = {
            "cdt_code": "D7286",
            "suggested_cpt": "40808",
            "estimated_coverage": 475.0,
        }

        result = self.generator.generate_letter_of_medical_necessity(
            patient_data=patient_data,
            clinical_findings=clinical_findings,
            crosswalk_data=crosswalk_data,
        )

        nexus = result["clinical_nexus"]
        assert nexus["primary_diagnosis"]["code"] == "K13.21"
        assert result["coding_crosswalk"]["proposed_cpt"]["code"] == "40808"
        risks = " ".join(nexus["untreated_risks"]).lower()
        assert "malignant transformation" in risks or "squamous cell carcinoma" in risks

    def test_lomn_atrial_fibrillation_cardiovascular_nexus(self):
        """
        Verify LOMN for Atrial Fibrillation (I48.91) + Surgical Extraction (D7210 -> CPT 41899).
        Highlights untreated risks of bacteremia predisposing to endocarditis and uncontrolled infection.
        """
        patient_data = {
            "patient_name": "Jane Smith",
            "birth_date": "1980-09-23",
            "mrn": "MRN-10002",
            "id": "CS-2002",
        }
        clinical_findings = {
            "conditions": [{"code": "I48.91", "display": "Atrial fibrillation, unspecified"}],
            "medications": ["Warfarin Sodium 5mg", "Metoprolol Succinate 50mg"],
        }
        crosswalk_data = {
            "cdt_code": "D7210",
            "suggested_cpt": "41899",
            "estimated_coverage": 925.0,
        }

        result = self.generator.generate_letter_of_medical_necessity(
            patient_data=patient_data,
            clinical_findings=clinical_findings,
            crosswalk_data=crosswalk_data,
        )

        nexus = result["clinical_nexus"]
        assert nexus["primary_diagnosis"]["code"] == "I48.91"
        assert "atrial fibrillation" in nexus["primary_diagnosis"]["display"].lower()
        risks = " ".join(nexus["untreated_risks"]).lower()
        assert "uncontrolled infection" in risks
        assert "cardiovascular" in risks or "endocarditis" in risks or "osteomyelitis" in risks


# ==============================================================================
# Tier 2: CareStack Document Management Mock API Tests
# ==============================================================================

class TestCareStackDocumentAPI:
    """Tests for CareStack mock document upload and retrieval endpoints."""

    def test_get_initial_patient_documents(self):
        """Verify GET /api/carestack/patients/{id}/documents returns pre-seeded documents."""
        # Query CS-2001
        res = client.get("/api/carestack/patients/CS-2001/documents")
        assert res.status_code == 200
        docs = res.json()
        assert isinstance(docs, list)
        assert len(docs) >= 1
        assert docs[0]["document_type"] == "Insurance Pre-Authorization"
        assert "Delta Dental" in docs[0]["title"]

        # Query CS-2003 via alias 'patient-003'
        res_alias = client.get("/api/carestack/patients/patient-003/documents")
        assert res_alias.status_code == 200
        docs_alias = res_alias.json()
        assert isinstance(docs_alias, list)
        assert len(docs_alias) >= 1
        assert any("Periodontal" in d["title"] for d in docs_alias)

    def test_get_patient_documents_wrapped_format(self):
        """Verify GET /api/carestack/patients/{id}/documents?wrapped=true returns structured dictionary."""
        res = client.get("/api/carestack/patients/CS-2003/documents?wrapped=true")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, dict)
        assert data["patient_id"] == "CS-2003"
        assert data["document_count"] >= 1
        assert isinstance(data["documents"], list)

    def test_post_document_json_payload(self):
        """Verify POST /api/carestack/patients/{id}/documents persists document with SHA-256 hash."""
        payload = {
            "document_type": "Letter of Medical Necessity",
            "title": "Clinical Justification - Scaling and Root Planing",
            "file_content": "Detailed clinical narrative proving medical necessity of CPT 41874.",
            "metadata": {"cdt_code": "D4341", "cpt_code": "41874", "payer": "Aetna Medical"},
        }
        res = client.post("/api/carestack/patients/CS-2002/documents", json=payload)
        assert res.status_code == 201
        data = res.json()

        assert data["status"] == "success"
        assert data["document_id"].startswith("DOC-")
        assert data["upload_timestamp"] is not None

        expected_hash = hashlib.sha256(payload["file_content"].encode("utf-8")).hexdigest()
        assert data["verification_hash"] == expected_hash

        # Verify document is attached in patient chart
        get_res = client.get("/api/carestack/patients/CS-2002/documents")
        assert get_res.status_code == 200
        docs = get_res.json()
        matching = next((d for d in docs if d["document_id"] == data["document_id"]), None)
        assert matching is not None
        assert matching["title"] == payload["title"]
        assert matching["verification_hash"] == expected_hash

    def test_post_document_multipart_form_data(self):
        """Verify POST /api/carestack/patients/{id}/documents accepts multipart/form-data."""
        form_data = {
            "document_type": "Letter of Medical Necessity",
            "title": "Multipart LOMN Upload - Tooth Sectioning",
            "file_content": "# Medical Justification for Surgical Ostectomy\nPatient requires CPT 41899.",
            "metadata": json.dumps({"cdt_code": "D7240", "cpt_code": "41899"}),
        }
        res = client.post("/api/carestack/patients/CS-2004/documents", data=form_data)
        assert res.status_code == 201
        data = res.json()

        assert data["status"] == "success"
        assert data["document_id"].startswith("DOC-")
        expected_hash = hashlib.sha256(form_data["file_content"].encode("utf-8")).hexdigest()
        assert data["verification_hash"] == expected_hash

    def test_document_patient_not_found(self):
        """Verify 404 error when attaching or querying documents for unknown patient."""
        get_res = client.get("/api/carestack/patients/NON-EXISTENT-9999/documents")
        assert get_res.status_code == 404

        post_res = client.post(
            "/api/carestack/patients/NON-EXISTENT-9999/documents",
            json={"title": "Test", "file_content": "Test content"},
        )
        assert post_res.status_code == 404


# ==============================================================================
# Tier 3: Billing Orchestration End-to-End Tests
# ==============================================================================

class TestBillingLOMNOrchestration:
    """Tests for POST /api/billing/generate-and-attach-lomn end-to-end flow."""

    def test_generate_and_attach_lomn_patient_003_diabetes_d4341(self):
        """
        Orchestration test for patient-003 (Robert Taylor) with D4341:
        1. Resolves demographics from CareStack.
        2. Resolves active Type 2 Diabetes condition from FHIR mock.
        3. Evaluates crosswalk: D4341 -> CPT 41874 ($600).
        4. Synthesizes LOMN with Dr. Sarah Jenkins attestation & systemic risks.
        5. Automatically ingests into CareStack mock Document API.
        """
        payload = {
            "patient_id": "patient-003",
            "cdt_code": "D4341",
        }
        res = client.post("/api/billing/generate-and-attach-lomn", json=payload)
        assert res.status_code == 200
        data = res.json()

        # Check top-level contract
        assert data["status"] == "success"
        assert data["document_id"].startswith("DOC-")
        assert isinstance(data["preview_content"], str)
        assert isinstance(data["claim_opportunity"], dict)

        # Check cross-coding evaluation results
        opp = data["claim_opportunity"]
        assert opp["is_eligible"] is True
        assert opp["suggested_cpt"] == "41874"
        assert "E11.9" in opp["justifying_icd10"]
        assert opp["estimated_coverage"] == 600.0

        # Check generated preview content
        preview = data["preview_content"]
        assert "LETTER OF MEDICAL NECESSITY" in preview
        assert "Robert Taylor" in preview
        assert "Dr. Sarah Jenkins, DDS" in preview
        assert "1982736450" in preview
        assert "E11.9" in preview
        assert "41874" in preview
        assert "glycemic instability" in preview.lower()
        assert "uncontrolled infection" in preview.lower()
        assert "osteomyelitis" in preview.lower()

        # Step 5 verification: Confirm document is immediately present in CareStack
        docs_res = client.get("/api/carestack/patients/CS-2003/documents")
        assert docs_res.status_code == 200
        attached_docs = docs_res.json()
        doc_match = next((d for d in attached_docs if d["document_id"] == data["document_id"]), None)
        assert doc_match is not None, "Synthesized LOMN must be queryable in CareStack chart"
        assert doc_match["document_type"] == "Letter of Medical Necessity"
        assert doc_match["metadata"]["cdt_code"] == "D4341"
        assert doc_match["metadata"]["cpt_code"] == "41874"
        assert doc_match["verification_hash"] == data["verification_hash"]

    def test_generate_and_attach_lomn_cs_2004_tmj_d7210(self):
        """
        Orchestration test for CS-2004 (Marcus Chen) with D7210 (Surgical Extraction + TMJ/Impaction):
        Crosswalk resolves to CPT 41899 ($925), drafts LOMN, and persists in CareStack.
        """
        payload = {
            "patient_id": "CS-2004",
            "cdt_code": "D7210",
        }
        res = client.post("/api/billing/generate-and-attach-lomn", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "success"
        opp = data["claim_opportunity"]
        assert opp["is_eligible"] is True
        assert opp["suggested_cpt"] == "41899"
        assert opp["estimated_coverage"] == 925.0

        # Check CareStack chart attachment
        docs_res = client.get("/api/carestack/patients/CS-2004/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        assert any(d["document_id"] == data["document_id"] for d in docs)

    def test_generate_and_attach_lomn_cs_2005_leukoplakia_d7286(self):
        """
        Orchestration test for CS-2005 (Sarah Jenkins) with D7286 (Biopsy + Leukoplakia):
        Crosswalk resolves to CPT 40808 ($475), drafts LOMN, and persists in CareStack.
        """
        payload = {
            "patient_id": "CS-2005",
            "cdt_code": "D7286",
        }
        res = client.post("/api/billing/generate-and-attach-lomn", json=payload)
        assert res.status_code == 200
        data = res.json()

        assert data["status"] == "success"
        opp = data["claim_opportunity"]
        assert opp["is_eligible"] is True
        assert opp["suggested_cpt"] == "40808"
        assert opp["estimated_coverage"] == 475.0

        # Check CareStack chart attachment
        docs_res = client.get("/api/carestack/patients/CS-2005/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        assert any(d["document_id"] == data["document_id"] for d in docs)

    def test_generate_and_attach_lomn_patient_not_found(self):
        """Verify 404 response when attempting LOMN generation for unknown patient."""
        payload = {
            "patient_id": "UNKNOWN-9999",
            "cdt_code": "D4341",
        }
        res = client.post("/api/billing/generate-and-attach-lomn", json=payload)
        assert res.status_code == 404


# ==============================================================================
# Tier 4: CareStackClient Async Document Methods
# ==============================================================================

@pytest.mark.anyio
async def test_carestack_client_document_methods():
    """Verify CareStackClient.attach_patient_document and get_patient_documents."""
    carestack_client = CareStackClient(app=app)

    # Attach document via async client
    doc = await carestack_client.attach_patient_document(
        patient_id="CS-2001",
        document_type="Letter of Medical Necessity",
        title="Async Client Attached LOMN",
        file_content="Content generated by client test.",
        metadata={"test": True},
    )
    assert doc["status"] == "success"
    assert doc["document_id"].startswith("DOC-")

    # Retrieve documents via async client
    docs = await carestack_client.get_patient_documents("CS-2001")
    assert isinstance(docs, list)
    assert any(d["document_id"] == doc["document_id"] for d in docs)
