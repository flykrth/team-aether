# Pitch Deck Outline — MDIN: Medical-Dental Interoperability Node for CareStack

**DSOLVE 2026 · DRISHTI · College of Engineering Trivandrum (CET)**  
**Problem 6: Open Problem Statement — Dental Industry (US & Global Focus)**  
**Team Aether**

---

## Slide 1 — Title & Hook (≈30s)

- **Project Title**: **MDIN: Medical-Dental Interoperability Node for CareStack**
- **Tagline**: Bridging the Divide Between Dental Practice Management and Hospital EHRs
- **Team**: Team Aether · College of Engineering Trivandrum (CET)
- **Problem Statement**: Problem 6 — Open Problem Statement (US & Global Dental Industry)

---

## Slide 2 — The "Two-System Problem" (≈45s)

- **The Pain Point**: Medical and dental healthcare exist in complete technological, clinical, and legal silos.
- **Clinical Jeopardy**:
  - Dentists operate blind to hospital EHRs (Epic, Cerner).
  - High-potency anticoagulants (Warfarin/DOACs) $\to$ Uncontrolled intraoperative hemorrhage during extractions.
  - Prosthetic cardiac valves $\to$ Transient bacteremia from cleanings seeding valves, causing fatal bacterial endocarditis (30% mortality).
  - Undocumented penicillin allergies $\to$ Fatal chairside anaphylaxis from empirical Amoxicillin.
- **Operational & Financial Waste**:
  - Patient self-reporting error rate exceeds 40–50%.
  - 48–72 hour phone tag and fax delays for physician clearances.
  - Dental insurance caps ($1,000–$1,500/year) force patients out-of-pocket for medically necessary oral surgeries.

---

## Slide 3 — The Solution: MDIN (≈45s)

- **One-Sentence Pitch**: An open-standard, federated interoperability gateway that connects CareStack PMS to hospital EHRs using HL7® FHIR® R4 and sub-second CDS Hooks™ v1.0/v2.0.
- **How It Works (The 3-Step Flow)**:
  1. **Reconciliation**: On patient check-in, MDIN resolves patient identity with hospital EHRs via USCDI v5.
  2. **Chairside Decision Support**: When a dentist clicks a CDT procedure on the odontogram, MDIN evaluates medical diagnoses and labs sub-second, surfacing evidence-based CDS cards (AHA/ADA/AAOMS).
  3. **Financial Optimization**: Cross-codes dental procedures to medical CPT codes, pre-populating CMS-1500 forms, compiling ANSI 837P EDI claims, and generating Letters of Medical Necessity.

---

## Slide 4 — Live Demo Highlights (≈90–120s)

- **Patient 1 (John Doe)**: Warfarin anticoagulation + Penicillin anaphylaxis $\to$ CDS Hook blocks Amoxicillin, warns on D7140 extraction, and dispatches 1-click pre-op INR consult.
- **Patient 2 (Jane Smith)**: Prosthetic cardiac valve $\to$ Routine cleaning D1110 triggers mandatory AHA antibiotic prophylaxis warning card.
- **Patient 3 (Robert Taylor)**: Uncontrolled diabetes (HbA1c 9.2%) $\to$ Financial Optimization dashboard translates D4341 scaling into medical CPT 41874 ($600 medical coverage), generating authentic CMS-1500 facsimile, SHA-256 signed LOMN, and ANSI 837P EDI stream.

---

## Slide 5 — Engineering & Technical Highlights (≈30s)

- **Technology Stack**: FastAPI ASGI backend, Vite React 18 frontend, Tailwind CSS, Docker Compose, Nginx reverse proxy.
- **Standards Implemented**: CareStack Web API V1, HL7 FHIR R4.0.1 (USCDI v5), CDS Hooks v1.0/v2.0, ANSI ASC X12N 837P EDI, NUCC CMS-1500.
- **Semantic Translation**: FHIR ConceptMap ($translate) bridging ICD-10, SNOMED CT, RxNorm, and LOINC to ADA CDT codes.
- **Automated Verification**: **132 / 132 passing tests (100% pass rate)** in Pytest.

---

## Slide 6 — Market & Health Policy Impact (≈30s)

- **Target Market**: Over 130,000 dental practices in the US and UK managing high-risk elderly and medically complex patients.
- **Regulatory Alignment**:
  - **HIPAA TPO Exception (45 CFR § 164.506)**: Clinical data exchange for treatment purposes without patient authorization.
  - **21st Century Cures Act (45 CFR Part 171)**: Information blocking prohibition compliance via open FHIR endpoints.
  - **ONC HTI-1 DSI Rule**: Full transparency, explainability, and guideline source attribution on all CDS cards.

---

## Slide 7 — Roadmap & Conclusion (≈30s)

- **Future Horizons**: Direct SMART on FHIR embedded launch inside CareStack cloud, AI-powered real-time prior authorization querying.
- **Takeaway**: *"MDIN transforms dental care from an isolated island into an integrated, patient-safe clinical and financial ecosystem."*

---

## Technical Q&A Preparation

1. **Why CDS Hooks instead of custom webhooks?**  
   CDS Hooks is the official HL7 international standard for clinical decision support adopted by Epic, Cerner, and certified EHRs nationwide. It avoids proprietary vendor lock-in.
2. **Is sharing medical data with a dentist HIPAA-compliant?**  
   Yes. Under 45 CFR § 164.506 (HIPAA Treatment, Payment, and Operations Exception), covered entities may share PHI for treatment activities without separate patient consent.
3. **How does the ConceptMap engine handle ambiguous codes?**  
   Through FHIR ConceptMap equivalence mappings (`equivalent`, `relatedto`, `narrower`) paired with a multi-factor risk synthesis engine that compound-evaluates co-occurring diagnoses and therapies.
4. **How does medical cross-coding benefit practices?**  
   It unlocks primary medical insurance coverage for procedures with documented systemic disease etiology, eliminating manual 45-minute medical necessity letter drafting and recovering thousands in legitimate reimbursement.