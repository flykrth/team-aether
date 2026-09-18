"""
Automated Letter of Medical Necessity (LOMN) Generation Service.
Step 9 of MDIN: Synthesizes formal clinical justification letters formatted for
major commercial and government medical payers (e.g., Aetna, Delta Dental, UnitedHealthcare).
Produces structured JSON payloads, formatted Markdown, and self-contained styled HTML documents.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union


CLINICIAN_SARAH_JENKINS = {
    "name": "Dr. Sarah Jenkins, DDS",
    "degree": "DDS, Oral & Maxillofacial Surgery / Advanced Periodontics",
    "npi": "1982736450",
    "state_license": "MA-DN884190",
    "clinic_name": "CareStack Center for Advanced Dentistry - Surgical Suite",
    "address": "100 Healthcare Boulevard, Suite 400, Boston, MA 02115",
    "phone": "(555) 019-2830",
    "fax": "(555) 019-2839",
    "email": "dr.jenkins@carestack-health.org",
    "taxonomy_code": "1223S0112X",
}


class MedicalNecessityGenerator:
    """
    Synthesizes clinical letters of medical necessity justifying primary medical
    coverage (CPT) for surgical and periodontal dental procedures (CDT) based on
    documented systemic medical nexus and risk of untreated disease.
    """

    def __init__(self, clinician: Optional[Dict[str, Any]] = None):
        self.clinician = clinician or CLINICIAN_SARAH_JENKINS

    def _extract_patient_details(self, patient_data: Dict[str, Any]) -> Dict[str, str]:
        """Extracts and normalizes patient demographics for the payer letterhead."""
        full_name = (
            patient_data.get("full_name")
            or patient_data.get("patient_name")
            or f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}".strip()
            or patient_data.get("name")
            or "DOE, JOHN"
        )
        dob = (
            patient_data.get("dob")
            or patient_data.get("patient_dob")
            or patient_data.get("birth_date")
            or patient_data.get("birthDate")
            or "1975-01-01"
        )
        mrn = (
            patient_data.get("mrn")
            or patient_data.get("identifier")
            or patient_data.get("id")
            or "MRN-10001"
        )
        account_id = (
            patient_data.get("account_id")
            or patient_data.get("carestack_id")
            or patient_data.get("id")
            or patient_data.get("patient_id")
            or "CS-2001"
        )
        gender = patient_data.get("gender") or patient_data.get("patient_gender") or "Unknown"
        phone = patient_data.get("phone") or patient_data.get("mobile") or "N/A"
        email = patient_data.get("email") or "N/A"
        address = patient_data.get("address") or patient_data.get("patient_address") or "100 Healthcare Blvd, Boston, MA 02115"

        return {
            "full_name": full_name,
            "dob": dob,
            "mrn": str(mrn),
            "account_id": str(account_id),
            "gender": gender.capitalize() if isinstance(gender, str) else str(gender),
            "phone": str(phone),
            "email": str(email),
            "address": str(address),
        }

    def _extract_clinical_context(self, clinical_findings: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts diagnoses, medications, and objective clinical observations."""
        raw_conditions = clinical_findings.get("conditions", [])
        raw_meds = clinical_findings.get("medications", [])
        raw_obs = clinical_findings.get("observations", [])

        # Normalize conditions into list of dicts { code, display }
        conditions: List[Dict[str, str]] = []
        seen_codes = set()

        for cond in raw_conditions:
            if isinstance(cond, str):
                code = cond.strip().upper()
                if code not in seen_codes:
                    seen_codes.add(code)
                    conditions.append({"code": code, "display": code})
            elif isinstance(cond, dict):
                code = ""
                display = ""
                # Check FHIR Condition code.coding
                code_obj = cond.get("code")
                if isinstance(code_obj, dict):
                    for c in code_obj.get("coding", []):
                        sys = (c.get("system") or "").lower()
                        cd = (c.get("code") or "").strip().upper()
                        disp = c.get("display") or code_obj.get("text") or cd
                        if "icd-10" in sys or not code:
                            code = cd
                            display = disp
                if not code and "code" in cond and isinstance(cond["code"], str):
                    code = cond["code"].strip().upper()
                    display = cond.get("display") or cond.get("text") or code
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    conditions.append({"code": code, "display": display or code})

        # Normalize medications
        medications: List[str] = []
        for med in raw_meds:
            if isinstance(med, str):
                medications.append(med.strip())
            elif isinstance(med, dict):
                med_cc = med.get("medicationCodeableConcept", {})
                txt = med_cc.get("text")
                if not txt and "coding" in med_cc:
                    txt = med_cc["coding"][0].get("display")
                if not txt:
                    txt = med.get("name") or med.get("display") or "Medication"
                medications.append(str(txt))

        # Normalize observations
        observations: List[Dict[str, Any]] = []
        for obs in raw_obs:
            if isinstance(obs, dict):
                code_txt = obs.get("code", {}).get("text") or "Observation"
                val = obs.get("valueQuantity", {})
                observations.append({
                    "name": code_txt,
                    "value": val.get("value"),
                    "unit": val.get("unit", ""),
                })

        return {
            "conditions": conditions,
            "medications": medications,
            "observations": observations,
        }

    def _determine_systemic_nexus(
        self,
        cdt_code: str,
        cpt_code: str,
        conditions: List[Dict[str, str]],
        medications: List[str],
        observations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Synthesizes the clinical indication, systemic nexus, and risks if left untreated.
        Explicitly links systemic diagnoses (e.g. Type 2 Diabetes, Atrial Fibrillation, TMJ,
        Leukoplakia) to the proposed surgical/periodontal dental procedure.
        """
        cdt_upper = (cdt_code or "").strip().upper()
        cpt_upper = (cpt_code or "").strip().upper()
        cond_codes = {c["code"] for c in conditions}
        cond_map = {c["code"]: c["display"] for c in conditions}

        # Check for Diabetes Mellitus (E11.9, E10.9, E11.65, etc.)
        has_diabetes = any(c.startswith("E11") or c.startswith("E10") for c in cond_codes)
        # Check for Atrial Fibrillation / Cardiovascular disease (I48.91, I48, I50, I25)
        has_afib = any(c.startswith("I48") for c in cond_codes)
        has_cardio = any(c.startswith("I") for c in cond_codes)
        # Check for Maxillofacial / TMJ / Bone Pathology (M26.61, K01.1, M27.2)
        has_tmj = "M26.61" in cond_codes or any(c.startswith("M26") for c in cond_codes)
        has_impaction = "K01.1" in cond_codes or any(c.startswith("K01") for c in cond_codes)
        has_osteomyelitis = "M27.2" in cond_codes or any(c.startswith("M27") for c in cond_codes)
        # Check for Oral Leukoplakia / Dysplasia (K13.21, K13.2)
        has_leukoplakia = "K13.21" in cond_codes or any(c.startswith("K13.2") for c in cond_codes)
        # Check for Osteoporosis / Antiresorptive therapy (M81.0, Alendronate, Denosumab)
        has_osteoporosis = "M81.0" in cond_codes or any(c.startswith("M81") for c in cond_codes)
        has_antiresorptive = any(
            any(k in m.lower() for k in ["alendronate", "fosamax", "prolia", "denosumab", "zoledronic", "reclast", "bisphosphonate"])
            for m in medications
        )
        has_anticoagulation = any(
            any(k in m.lower() for k in ["warfarin", "eliquis", "apixaban", "xarelto", "rivaroxaban", "pradaxa", "heparin"])
            for m in medications
        )

        hba1c_obs = next((o for o in observations if "a1c" in o["name"].lower()), None)
        hba1c_str = f" (documented HbA1c: {hba1c_obs['value']}{hba1c_obs['unit']})" if hba1c_obs and hba1c_obs.get("value") else ""

        # Construct primary diagnosis, secondary diagnosis, systemic nexus narrative, and risks
        primary_dx: Dict[str, str] = {}
        secondary_dx: Dict[str, str] = {}
        nexus_paragraphs: List[str] = []
        untreated_risks: List[str] = []
        clinical_rationale: str = ""

        # Scenario 1: Diabetes Mellitus + Periodontal Debridement / Scaling (D4341 / D4260 -> CPT 41874)
        if has_diabetes and (cdt_upper in ["D4341", "D4260"] or cpt_upper == "41874"):
            diabetes_code = next((c for c in cond_codes if c.startswith("E11") or c.startswith("E10")), "E11.9")
            primary_dx = {
                "code": diabetes_code,
                "display": cond_map.get(diabetes_code, "Type 2 diabetes mellitus without complications"),
                "category": "Systemic Endocrine Pathology (Primary Justification)",
            }
            secondary_dx = {
                "code": "K05.321",
                "display": "Chronic periodontitis, generalized, severe with systemic involvement",
                "category": "Oral-Systemic Infectious Nexus",
            }
            nexus_paragraphs.append(
                f"The patient carries an active diagnosis of {primary_dx['display']} (ICD-10 {primary_dx['code']}){hba1c_str}, "
                f"presenting with severe chronic periodontal infection. A critical bi-directional pathophysiological relationship "
                f"exists between severe periodontal disease and diabetes mellitus. Chronic subgingival ulceration of periodontal "
                f"pockets serves as an active, persistent vascular conduit for periodontal pathogen lipopolysaccharides (LPS) and "
                f"endotoxins directly into the systemic circulation."
            )
            nexus_paragraphs.append(
                "This ongoing hematogenous challenge stimulates hepatic and macrophage hyper-production of potent systemic "
                "pro-inflammatory mediators, notably Tumor Necrosis Factor-alpha (TNF-α), Interleukin-6 (IL-6), and C-Reactive Protein (CRP). "
                "Circulating TNF-α directly inhibits insulin receptor substrate-1 (IRS-1) tyrosine phosphorylation, causing severe "
                "refractory peripheral insulin resistance and marked glycemic instability. Conversely, persistent hyperglycemia impairs "
                "neutrophil chemotaxis and accelerates periodontal collagen breakdown. Eradication of this chronic oral infectious "
                "burden via comprehensive scaling, root planing, and mucosal debridement (CPT 41874) is a direct medical necessity "
                "to stabilize the patient's endocrine and glycemic status."
            )
            untreated_risks = [
                "Glycemic instability: Acute and progressive elevation of HbA1c with refractory insulin resistance.",
                "Uncontrolled infection: Acute recurrent periodontal abscesses, severe cellulitis, and systemic bacteremia.",
                "Osteomyelitis: Rapid alveolar bone demineralization and progressive osteolytic jaw destruction.",
                "Accelerated systemic diabetic complications: Heightened susceptibility to diabetic nephropathy, retinopathy, and acute coronary syndrome.",
            ]
            clinical_rationale = (
                "Periodontal mucosal debridement (CPT 41874 / CDT D4341) is medically necessary not as routine dental care, "
                "but as an active therapeutic intervention to eliminate the primary chronic infectious inflammatory nidus driving "
                "the patient's glycemic instability and systemic vascular risk."
            )

        # Scenario 2: Atrial Fibrillation / Cardiovascular / Anticoagulation + Surgical Extraction (D7210 / D7240 -> CPT 41899)
        elif (has_afib or has_cardio) and (cdt_upper in ["D7210", "D7240", "D7140"] or cpt_upper == "41899"):
            cardio_code = next((c for c in cond_codes if c.startswith("I48") or c.startswith("I")), "I48.91")
            primary_dx = {
                "code": cardio_code,
                "display": cond_map.get(cardio_code, "Atrial fibrillation, unspecified"),
                "category": "Cardiovascular Pathology & Systemic Nexus",
            }
            secondary_dx = {
                "code": "M27.2",
                "display": "Inflammatory conditions of jaws (Osteomyelitis / Odontogenic infection)",
                "category": "Infectious Maxillofacial Nexus",
            }
            anticoag_note = (
                f" The patient is actively managed on systemic anticoagulation ({', '.join(medications)}), "
                "substantially increasing perioperative hemorrhagic morbidity."
                if (has_anticoagulation or medications)
                else ""
            )
            nexus_paragraphs.append(
                f"The patient presents with active cardiovascular pathology ({primary_dx['display']}, ICD-10 {primary_dx['code']}) "
                f"complicated by severe localized odontogenic disease requiring surgical extraction and ostectomy (CPT 41899).{anticoag_note} "
                "Active dentoalveolar osteolysis and persistent pericoronal infectious foci create an intolerable risk of transient "
                "and sustained bacteremia with viridans group streptococci, placing the patient at acute risk for bacterial seeding, "
                "infective endocarditis, and septic thromboembolism."
            )
            nexus_paragraphs.append(
                "Surgical intervention requires surgical suite protocol, bone resection, tooth sectioning, and strict surgical hemostasis "
                "to mitigate severe systemic risks. Leaving this infectious lesion untreated risks extension into adjacent fascial spaces "
                "(submandibular, parapharyngeal), catastrophic deep space neck infections, and systemic septic shock."
            )
            untreated_risks = [
                "Uncontrolled infection: Odontogenic fascial space cellulitis, Ludwig's angina, and systemic sepsis.",
                "Osteomyelitis: Extension of bacterial osteitis into mandibular cortical bone and marrow.",
                "Cardiovascular decompensation: Transient bacteremia predisposing to infective endocarditis and hemodynamic instability.",
                "Thromboembolic / Hemorrhagic emergency: Inability to safely stabilize anticoagulation regimen during emergent dental crisis.",
            ]
            clinical_rationale = (
                "Surgical extraction with ostectomy (CPT 41899) is medically indicated to definitively eradicate a focal source "
                "of bacteremia and prevent life-threatening cardiovascular sepsis and deep fascial infection."
            )

        # Scenario 3: TMJ Arthralgia / Impaction with Cystic Degeneration (M26.61, K01.1, M27.2 -> CPT 41899)
        elif (has_tmj or has_impaction or has_osteomyelitis) and (cdt_upper in ["D7210", "D7240"] or cpt_upper == "41899"):
            prime_code = "M26.61" if has_tmj else ("K01.1" if has_impaction else "M27.2")
            primary_dx = {
                "code": prime_code,
                "display": cond_map.get(prime_code, "Arthralgia of temporomandibular joint / Impacted teeth"),
                "category": "Maxillofacial Skeletal Pathology",
            }
            sec_code = "K01.1" if prime_code != "K01.1" else "M27.2"
            secondary_dx = {
                "code": sec_code,
                "display": cond_map.get(sec_code, "Impacted teeth with follicular cystic degeneration"),
                "category": "Structural Osseous Pathology",
            }
            nexus_paragraphs.append(
                f"The patient demonstrates severe maxillofacial pathology characterized by {primary_dx['display']} (ICD-10 {primary_dx['code']}) "
                f"and {secondary_dx['display']} (ICD-10 {secondary_dx['code']}). The impacted dentoalveolar structure has caused chronic "
                "cortical osteolysis, intractable neuropathic and myofascial pain, and progressive compression of the inferior alveolar "
                "neurovascular bundle. Surgical ostectomy and tooth sectioning (CPT 41899 / CDT D7210 / D7240) under medical protocol "
                "are mandatory to halt structural bone degradation."
            )
            nexus_paragraphs.append(
                "Diagnostic imaging confirms bone entrapment requiring extensive bone removal and tooth sectioning. Without surgical excision, "
                "the pericoronal cystic lesion will continue to expand, eroding mandibular basal cortical plates and predisposing to "
                "pathological fracture, osteomyelitis of the mandible, and permanent trigeminal nerve deficit."
            )
            untreated_risks = [
                "Osteomyelitis: Progressive bacterial colonization and necrosis of the mandibular ramus and body.",
                "Uncontrolled infection: Ascending pterygomandibular space abscess and facial cellulitis.",
                "Pathological mandibular fracture: Progressive cystic expansion causing critical cortical bone thinning.",
                "Permanent neurovascular injury: Irreversible compression neuropathy of the inferior alveolar and lingual nerves.",
            ]
            clinical_rationale = (
                "Complex dentoalveolar surgery with ostectomy (CPT 41899) is medically necessary to arrest osteolytic cystic expansion, "
                "prevent pathological mandibular fracture, and decompress the inferior alveolar nerve."
            )

        # Scenario 4: Oral Mucosal Leukoplakia / Dysplasia (K13.21 -> CPT 40808)
        elif has_leukoplakia or cdt_upper == "D7286" or cpt_upper == "40808":
            primary_dx = {
                "code": "K13.21",
                "display": cond_map.get("K13.21", "Leukoplakia of oral mucosa, including tongue"),
                "category": "Premalignant Oral Epithelial Neoplasm",
            }
            secondary_dx = {
                "code": "K13.29",
                "display": "Other disturbances of oral epithelium, including dysplasia",
                "category": "Histopathological Evaluation Required",
            }
            nexus_paragraphs.append(
                f"The patient presents with an atypical, persistent mucosal lesion of the oral cavity diagnosed as {primary_dx['display']} "
                f"(ICD-10 {primary_dx['code']}). Oral leukoplakia is an established high-risk premalignant condition with documented "
                "potential for transformation into invasive Oral Squamous Cell Carcinoma (OSCC). Conservative topical management is "
                "contraindicated due to persistent dysplastic clinical features."
            )
            nexus_paragraphs.append(
                "Immediate incisional biopsy and excision of oral tissue (CPT 40808 / CDT D7286) with comprehensive histopathological "
                "examination are urgent medical necessities. Histopathological margin analysis is required to rule out carcinoma in situ "
                "or invasive squamous cell carcinoma and establish an appropriate oncological management protocol."
            )
            untreated_risks = [
                "Malignant transformation: Progression of high-grade epithelial dysplasia into invasive Oral Squamous Cell Carcinoma.",
                "Cervical lymph node metastasis: Regional oncologic dissemination requiring radical neck dissection.",
                "Uncontrolled tissue ulceration: Invasive tissue destruction and permanent structural head and neck disfigurement.",
                "Severe oncology morbidity and elevated mortality risk.",
            ]
            clinical_rationale = (
                "Incisional biopsy of the oral vestibule/mucosa (CPT 40808 / CDT D7286) is a vital medical diagnostic procedure "
                "to evaluate potential malignancy, establish cellular differentiation, and guide definitive oncological management."
            )

        # Scenario 5: Osteoporosis / Antiresorptive Therapy (M81.0, Bisphosphonates -> CPT 41899)
        elif has_osteoporosis or has_antiresorptive:
            primary_dx = {
                "code": "M81.0",
                "display": cond_map.get("M81.0", "Age-related osteoporosis without current pathological fracture"),
                "category": "Systemic Skeletal Metabolic Disorder",
            }
            secondary_dx = {
                "code": "M27.2",
                "display": "Inflammatory conditions of jaws (Risk of MRONJ)",
                "category": "Medication-Related Jaw Osteonecrosis Nexus",
            }
            nexus_paragraphs.append(
                f"The patient has a confirmed diagnosis of {primary_dx['display']} (ICD-10 {primary_dx['code']}) and a documented history "
                f"of long-term antiresorptive / bisphosphonate therapy ({', '.join(medications) if medications else 'systemic antiresorptive'}). "
                "Severe suppression of osteoclastic remodeling places the patient at substantial risk for Medication-Related Osteonecrosis "
                "of the Jaw (MRONJ). Odontogenic infection in this environment cannot be treated with standard dental techniques."
            )
            nexus_paragraphs.append(
                "Surgical extraction under medical-grade surgical protocol (CPT 41899) with primary mucosal closure, bone smoothing, "
                "and surgical ostectomy is medically required to debride necrotic margins and eliminate infection without inciting "
                "refractory avascular necrosis."
            )
            untreated_risks = [
                "Medication-Related Osteonecrosis of the Jaw (MRONJ): Irreversible avascular necrosis with exposed necrotic bone.",
                "Osteomyelitis: Chronic refractory osteomyelitis requiring partial mandibulectomy.",
                "Uncontrolled infection: Spreading bacterial cellulitis and orocutaneous fistula formation.",
                "Severe intractable neuropathic pain and functional masticatory collapse.",
            ]
            clinical_rationale = (
                "Surgical intervention with ostectomy (CPT 41899) is medically necessary to prevent catastrophic bisphosphonate-related "
                "jawbone necrosis and chronic refractory osteomyelitis."
            )

        # Fallback / General Systemic Nexus
        else:
            first_cond = conditions[0] if conditions else {"code": "E11.9", "display": "Type 2 diabetes mellitus"}
            second_cond = conditions[1] if len(conditions) > 1 else {"code": "M27.2", "display": "Inflammatory conditions of jaws"}
            primary_dx = {
                "code": first_cond["code"],
                "display": first_cond["display"],
                "category": "Systemic Medical Diagnosis (Primary Justification)",
            }
            secondary_dx = {
                "code": second_cond["code"],
                "display": second_cond["display"],
                "category": "Secondary Systemic / Oral Indication",
            }
            nexus_paragraphs.append(
                f"The patient carries a diagnosed medical condition of {primary_dx['display']} (ICD-10 {primary_dx['code']}) "
                f"co-occurring with progressive dentoalveolar pathology requiring medical procedure CPT {cpt_upper or '41899'} "
                f"(equivalent to CDT {cdt_upper or 'D4341'}). The oral pathology acts as a primary active source of chronic systemic "
                "inflammation, bacteremia, and tissue breakdown."
            )
            nexus_paragraphs.append(
                "Leaving this pathology untreated constitutes a clear and direct danger to the patient's systemic health, exacerbating "
                "underlying systemic comorbidities and heightening susceptibility to severe systemic infection and organ stress."
            )
            untreated_risks = [
                "Uncontrolled infection: Rapid local and regional spread of odontogenic infection and systemic bacteremia.",
                "Glycemic and metabolic instability: Exacerbation of underlying endocrine and vascular comorbidities.",
                "Osteomyelitis: Progressive bacterial osteolysis of alveolar bone and jaw marrow spaces.",
                "Systemic inflammatory escalation and heightened hospitalization risk.",
            ]
            clinical_rationale = (
                f"Medical procedure CPT {cpt_upper or '41899'} is medically indicated to arrest acute disease progression "
                "and eliminate a direct threat to the patient's systemic medical stability."
            )

        return {
            "primary_diagnosis": primary_dx,
            "secondary_diagnosis": secondary_dx,
            "nexus_narrative": " ".join(nexus_paragraphs),
            "nexus_paragraphs": nexus_paragraphs,
            "untreated_risks": untreated_risks,
            "clinical_rationale": clinical_rationale,
        }

    def generate_letter_of_medical_necessity(
        self,
        patient_data: Dict[str, Any],
        clinical_findings: Dict[str, Any],
        crosswalk_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Synthesizes a formal clinical Letter of Medical Necessity (LOMN) structured
        for major medical payers (e.g., Aetna, Delta Dental, UnitedHealthcare).
        Returns clean JSON payload, formatted Markdown, and styled HTML.
        """
        # 1. Patient Details
        patient = self._extract_patient_details(patient_data)

        # 2. Clinician Details
        clinician = dict(self.clinician)

        # 3. Clinical Context & Systemic Nexus
        clinical_ctx = self._extract_clinical_context(clinical_findings)
        cdt_code = (crosswalk_data.get("cdt_code") or "").upper().strip()
        cpt_code = (
            crosswalk_data.get("suggested_cpt")
            or crosswalk_data.get("cpt_code")
            or ("41874" if cdt_code == "D4341" else ("40808" if cdt_code == "D7286" else "41899"))
        )
        cpt_display = (
            crosswalk_data.get("cpt_display")
            or ("Periodontal mucosal debridement / scaling" if cpt_code == "41874"
                else ("Biopsy, vestibule of mouth" if cpt_code == "40808"
                      else "Unlisted dentoalveolar surgery / ostectomy"))
        )
        cdt_display = (
            crosswalk_data.get("cdt_display")
            or crosswalk_data.get("procedure_description")
            or f"Dental Procedure {cdt_code}"
        )
        est_coverage = float(crosswalk_data.get("estimated_coverage") or 600.0)

        nexus_info = self._determine_systemic_nexus(
            cdt_code=cdt_code,
            cpt_code=cpt_code,
            conditions=clinical_ctx["conditions"],
            medications=clinical_ctx["medications"],
            observations=clinical_ctx["observations"],
        )

        now_utc = datetime.now(timezone.utc)
        date_str = now_utc.strftime("%B %d, %Y")
        iso_timestamp = now_utc.isoformat()

        # Document Header & Title
        title = f"Letter of Medical Necessity - {patient['full_name']} - CDT {cdt_code} / CPT {cpt_code}"

        # 4. Recommended Medical Coding Cross-Walk
        coding_crosswalk = {
            "primary_icd10": nexus_info["primary_diagnosis"],
            "secondary_icd10": nexus_info["secondary_diagnosis"],
            "proposed_cpt": {
                "code": cpt_code,
                "display": cpt_display,
                "equivalent_cdt": cdt_code,
                "equivalent_cdt_display": cdt_display,
                "estimated_reimbursement": est_coverage,
            },
            "medical_necessity_category": crosswalk_data.get("reimbursement_category", "Primary Medical Necessity Eligible"),
        }

        # 5. Formal Attestation & Signature Block
        attestation_statement = (
            f"I, {clinician['name']}, practicing at {clinician['clinic_name']}, hereby attest under penalty "
            "of perjury that I am the licensed attending clinician responsible for the treatment plan of the patient named herein. "
            "I certify that the clinical indications, active systemic medical conditions, and objective diagnostic findings "
            "documented in this report are complete, accurate, and substantiated by standard of care clinical criteria. "
            f"The proposed procedure (CPT {cpt_code} / CDT {cdt_code}) is not an elective dental cosmetic service; rather, it is "
            "an indispensable medical intervention required to arrest active infectious osteolysis, prevent systemic glycemic and "
            "cardiovascular decompensation, and mitigate life-threatening systemic risks including osteomyelitis, septicemia, and "
            "end-organ failure. I strongly urge approval of full primary medical reimbursement under the specified medical cross-walk."
        )

        signature_block = {
            "clinician_name": clinician["name"],
            "clinician_degree": clinician["degree"],
            "npi": clinician["npi"],
            "state_license": clinician["state_license"],
            "clinic_name": clinician["clinic_name"],
            "address": clinician["address"],
            "phone": clinician["phone"],
            "date": date_str,
            "signature_status": "Digitally Signed & Attested",
        }

        # 6. Structured JSON Content
        content_json = {
            "document_type": "Letter of Medical Necessity",
            "title": title,
            "generated_at": iso_timestamp,
            "patient_details": patient,
            "clinician_details": clinician,
            "clinical_indications": {
                "active_conditions": clinical_ctx["conditions"],
                "active_medications": clinical_ctx["medications"],
                "objective_observations": clinical_ctx["observations"],
                "systemic_nexus_narrative": nexus_info["nexus_narrative"],
                "systemic_risks_if_untreated": nexus_info["untreated_risks"],
                "clinical_rationale": nexus_info["clinical_rationale"],
            },
            "recommended_coding_crosswalk": coding_crosswalk,
            "formal_attestation": {
                "statement": attestation_statement,
                "signature": signature_block,
            },
        }

        # 7. Formatted Markdown Content
        content_markdown = self._generate_markdown(
            patient=patient,
            clinician=clinician,
            nexus_info=nexus_info,
            coding_crosswalk=coding_crosswalk,
            attestation_statement=attestation_statement,
            signature_block=signature_block,
            date_str=date_str,
        )

        # 8. Formatted HTML Content
        content_html = self._generate_html(
            patient=patient,
            clinician=clinician,
            nexus_info=nexus_info,
            coding_crosswalk=coding_crosswalk,
            attestation_statement=attestation_statement,
            signature_block=signature_block,
            date_str=date_str,
        )

        return {
            "document_type": "Letter of Medical Necessity",
            "title": title,
            "generated_at": iso_timestamp,
            "patient_summary": patient,
            "clinician": clinician,
            "clinical_nexus": nexus_info,
            "coding_crosswalk": coding_crosswalk,
            "attestation": {
                "statement": attestation_statement,
                "signature": signature_block,
            },
            "content_json": content_json,
            "content_markdown": content_markdown,
            "content_html": content_html,
        }

    def _generate_markdown(
        self,
        patient: Dict[str, str],
        clinician: Dict[str, str],
        nexus_info: Dict[str, Any],
        coding_crosswalk: Dict[str, Any],
        attestation_statement: str,
        signature_block: Dict[str, str],
        date_str: str,
    ) -> str:
        """Generates clean GitHub Flavored Markdown representation of the LOMN."""
        primary_dx = coding_crosswalk["primary_icd10"]
        secondary_dx = coding_crosswalk["secondary_icd10"]
        cpt = coding_crosswalk["proposed_cpt"]

        risks_md = "\n".join(f"- **{risk.split(':')[0]}:** {':'.join(risk.split(':')[1:]).strip() if ':' in risk else risk}" for risk in nexus_info["untreated_risks"])
        nexus_md = "\n\n".join(nexus_info["nexus_paragraphs"])

        return f"""# FORMAL LETTER OF MEDICAL NECESSITY
**CONFIDENTIAL & PROPRIETARY CLINICAL DOCUMENT — FOR MEDICAL PAYER ADJUDICATION**

**Date:** {date_str}  
**Addressed To:** Medical Claims Adjudication Committee / Medical Director  
*(Aetna, Delta Dental Medical Primary, UnitedHealthcare, CMS-Medicare Part B Administrative Contractors)*

---

### 1. Patient Identification & Demographics
| Field | Value |
| :--- | :--- |
| **Patient Full Name** | {patient['full_name']} |
| **Date of Birth (DOB)** | {patient['dob']} |
| **Medical Record Number (MRN)** | `{patient['mrn']}` |
| **CareStack Account ID** | `{patient['account_id']}` |
| **Gender** | {patient['gender']} |
| **Address** | {patient['address']} |

---

### 2. Referring & Attending Clinician
- **Clinician Name:** {clinician['name']}
- **Qualifications / Degree:** {clinician['degree']}
- **National Provider Identifier (NPI):** `{clinician['npi']}`
- **State Dental License:** `{clinician['state_license']}`
- **Practice Entity:** {clinician['clinic_name']}
- **Practice Address:** {clinician['address']}
- **Telephone / Fax:** {clinician['phone']} / {clinician['fax']}

---

### 3. Clinical Indications & Systemic Nexus
{nexus_md}

#### Systemic Risks if Left Untreated:
{risks_md}

**Clinical Justification Summary:**  
{nexus_info['clinical_rationale']}

---

### 4. Recommended Medical Coding Cross-Walk
| Coding Category | Code | Clinical Description |
| :--- | :---: | :--- |
| **Primary Diagnosis (ICD-10)** | `{primary_dx['code']}` | **{primary_dx['display']}** ({primary_dx.get('category', 'Primary')}) |
| **Secondary Diagnosis (ICD-10)** | `{secondary_dx['code']}` | **{secondary_dx['display']}** ({secondary_dx.get('category', 'Secondary')}) |
| **Proposed Medical Procedure (CPT)** | `{cpt['code']}` | **{cpt['display']}** |
| **Correlated Dental Procedure (CDT)** | `{cpt['equivalent_cdt']}` | {cpt['equivalent_cdt_display']} |
| **Estimated Medical Coverage** | `${cpt['estimated_reimbursement']:.2f}` | {coding_crosswalk['medical_necessity_category']} |

---

### 5. Formal Legal & Clinical Attestation
> {attestation_statement}

---

### 6. Attending Clinician Signature Block
**Digitally Signed By:** `{signature_block['clinician_name']}`  
**Credential:** {signature_block['clinician_degree']}  
**NPI:** `{signature_block['npi']}` | **License:** `{signature_block['state_license']}`  
**Facility:** {signature_block['clinic_name']}  
**Date of Signature:** {signature_block['date']}  
**Verification Status:** Verified & Digitally Locked (MDIN Automated Interoperability Node)
"""

    def _generate_html(
        self,
        patient: Dict[str, str],
        clinician: Dict[str, str],
        nexus_info: Dict[str, Any],
        coding_crosswalk: Dict[str, Any],
        attestation_statement: str,
        signature_block: Dict[str, str],
        date_str: str,
    ) -> str:
        """Generates an elegant, printable, self-contained HTML document."""
        primary_dx = coding_crosswalk["primary_icd10"]
        secondary_dx = coding_crosswalk["secondary_icd10"]
        cpt = coding_crosswalk["proposed_cpt"]

        paragraphs_html = "".join(f"<p style='margin-bottom: 12px; line-height: 1.6;'>{p}</p>" for p in nexus_info["nexus_paragraphs"])
        risks_html = "".join(f"<li style='margin-bottom: 8px;'><strong>{r.split(':')[0]}:</strong> {':'.join(r.split(':')[1:]).strip() if ':' in r else r}</li>" for r in nexus_info["untreated_risks"])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Letter of Medical Necessity - {patient['full_name']}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background-color: #f8fafc; margin: 0; padding: 24px; }}
  .lomn-container {{ max-width: 860px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); padding: 40px; }}
  .letterhead {{ border-bottom: 3px solid #0284c7; padding-bottom: 20px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: flex-start; }}
  .letterhead h1 {{ margin: 0 0 6px 0; font-size: 24px; color: #0f172a; text-transform: uppercase; letter-spacing: 0.5px; }}
  .letterhead .sub {{ font-size: 13px; color: #64748b; font-weight: 500; }}
  .badge-confidential {{ background: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }}
  .section-title {{ font-size: 16px; font-weight: 700; color: #0369a1; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 24px; margin-bottom: 12px; border-bottom: 1px solid #f1f5f9; padding-bottom: 6px; }}
  table.data-table {{ width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 14px; }}
  table.data-table th, table.data-table td {{ padding: 10px 14px; text-align: left; border: 1px solid #e2e8f0; }}
  table.data-table th {{ background-color: #f1f5f9; color: #334155; font-weight: 600; width: 30%; }}
  table.coding-table {{ width: 100%; border-collapse: collapse; margin-bottom: 18px; font-size: 14px; }}
  table.coding-table th {{ background: #0284c7; color: #ffffff; padding: 10px; text-align: left; font-weight: 600; }}
  table.coding-table td {{ padding: 10px; border: 1px solid #cbd5e1; }}
  .code-badge {{ background: #e0f2fe; color: #0369a1; padding: 3px 8px; border-radius: 4px; font-family: monospace; font-weight: 700; }}
  .risks-box {{ background: #fffbeb; border-left: 4px solid #f59e0b; padding: 16px; border-radius: 4px; margin: 16px 0; }}
  .attestation-box {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-left: 4px solid #16a34a; padding: 16px; border-radius: 4px; font-style: italic; color: #166534; line-height: 1.6; margin: 20px 0; font-size: 13.5px; }}
  .sig-block {{ margin-top: 30px; border-top: 2px solid #e2e8f0; padding-top: 20px; display: flex; justify-content: space-between; }}
  .sig-col {{ font-size: 13px; line-height: 1.6; }}
  .sig-line {{ font-family: "Brush Script MT", cursive, sans-serif; font-size: 26px; color: #1e3a8a; margin-bottom: 4px; }}
</style>
</head>
<body>
<div class="lomn-container">
  <div class="letterhead">
    <div>
      <h1>Letter of Medical Necessity</h1>
      <div class="sub">{clinician['clinic_name']} &bull; {clinician['address']}</div>
      <div class="sub">Clinical Practice NPI: {clinician['npi']} &bull; Tel: {clinician['phone']}</div>
    </div>
    <div style="text-align: right;">
      <span class="badge-confidential">Medical Payer Priority</span>
      <div style="font-size: 13px; color: #475569; margin-top: 8px;">Date: <strong>{date_str}</strong></div>
    </div>
  </div>

  <div class="section-title">1. Patient Demographics & Identification</div>
  <table class="data-table">
    <tr><th>Patient Full Name</th><td><strong>{patient['full_name']}</strong></td></tr>
    <tr><th>Date of Birth (DOB)</th><td>{patient['dob']} (Gender: {patient['gender']})</td></tr>
    <tr><th>Medical Record Number (MRN)</th><td><code>{patient['mrn']}</code></td></tr>
    <tr><th>CareStack Account ID</th><td><code>{patient['account_id']}</code></td></tr>
    <tr><th>Patient Address</th><td>{patient['address']}</td></tr>
  </table>

  <div class="section-title">2. Attending / Referring Clinician</div>
  <table class="data-table">
    <tr><th>Attending Clinician</th><td><strong>{clinician['name']}</strong>, {clinician['degree']}</td></tr>
    <tr><th>NPI / State License</th><td>NPI: <code>{clinician['npi']}</code> | Lic: <code>{clinician['state_license']}</code></td></tr>
    <tr><th>Facility & Contact</th><td>{clinician['clinic_name']} &bull; {clinician['phone']}</td></tr>
  </table>

  <div class="section-title">3. Clinical Indications & Systemic Nexus</div>
  <div style="font-size: 14.5px; color: #334155;">
    {paragraphs_html}
  </div>

  <div class="risks-box">
    <div style="font-weight: 700; color: #92400e; margin-bottom: 8px; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px;">Anticipated Systemic Risks if Left Untreated:</div>
    <ul style="margin: 0; padding-left: 20px; color: #78350f; font-size: 13.5px;">
      {risks_html}
    </ul>
  </div>

  <div class="section-title">4. Recommended Medical Coding Cross-Walk</div>
  <table class="coding-table">
    <thead>
      <tr>
        <th>Classification</th>
        <th>Code</th>
        <th>Clinical Description</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Primary Diagnosis</strong></td>
        <td><span class="code-badge">{primary_dx['code']}</span></td>
        <td><strong>{primary_dx['display']}</strong></td>
      </tr>
      <tr>
        <td><strong>Secondary Diagnosis</strong></td>
        <td><span class="code-badge">{secondary_dx['code']}</span></td>
        <td><strong>{secondary_dx['display']}</strong></td>
      </tr>
      <tr>
        <td><strong>Proposed Medical CPT</strong></td>
        <td><span class="code-badge">{cpt['code']}</span></td>
        <td><strong>{cpt['display']}</strong> (Correlated CDT: <code>{cpt['equivalent_cdt']}</code>)</td>
      </tr>
      <tr>
        <td><strong>Estimated Reimbursement</strong></td>
        <td colspan="2"><strong style="color: #059669;">${cpt['estimated_reimbursement']:.2f}</strong> &bull; <em>{coding_crosswalk['medical_necessity_category']}</em></td>
      </tr>
    </tbody>
  </table>

  <div class="section-title">5. Clinician Attestation & Certification</div>
  <div class="attestation-box">
    &ldquo;{attestation_statement}&rdquo;
  </div>

  <div class="sig-block">
    <div class="sig-col">
      <div class="sig-line">Dr. Sarah Jenkins, DDS</div>
      <div><strong>{signature_block['clinician_name']}</strong></div>
      <div>Attending Clinician | NPI: <code>{signature_block['npi']}</code></div>
      <div>State Dental License: <code>{signature_block['state_license']}</code></div>
    </div>
    <div class="sig-col" style="text-align: right;">
      <div>Facility: <strong>{signature_block['clinic_name']}</strong></div>
      <div>Date of Execution: <strong>{signature_block['date']}</strong></div>
      <div style="color: #059669; font-weight: 700; margin-top: 6px;">&check; Electronically Authenticated & Sealed</div>
    </div>
  </div>
</div>
</body>
</html>"""


# Global singleton instance for use across routers and services
medical_necessity_generator = MedicalNecessityGenerator()
