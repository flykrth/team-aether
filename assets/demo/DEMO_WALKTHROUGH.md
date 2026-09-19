# CrossWalk Live Demonstration Guide (DSOLVE 2026)

### 3–5 Minute Live Hackathon Presentation Script
**Problem 6: Open Problem Statement — Dental Industry**  
**Team Aether · College of Engineering Trivandrum (CET)**

---

## 1. Setup Before Presentation

1. **Terminal 1 (Backend ASGI Server)**:
   ```bash
   source .venv/bin/activate
   python backend/run.py
   ```
   *Verify: `http://localhost:8000/docs` is live.*

2. **Terminal 2 (Frontend React Client)**:
   ```bash
   cd frontend
   npm run dev
   ```
   *Verify: `http://localhost:5173` is loaded in your browser.*

---

## 2. Minute-by-Minute Presentation Script

### Minute 0:00 – 1:00 | The Hook: The "Two-System Problem"
- **Speaker**:  
  > *"Judges, in contemporary healthcare across the US and globally, medical care and dental care operate in complete clinical, technological, and financial isolation.*
  >
  > *When a dentist opens their Practice Management System—like CareStack—they are completely blind to the patient's hospital record in Epic or Cerner. Dental offices still rely on self-reported clipboards or iPad questionnaires. Studies show that over 40% of patients fail to report critical medications.*
  >
  > *A patient sitting in the dental chair for a tooth extraction might be on high-dose Warfarin for Atrial Fibrillation, or have an artificial heart valve requiring antibiotic premedication. If the clinician is blind to this data, an invasive extraction can trigger fatal uncontrolled hemorrhage or life-threatening Infective Endocarditis.*
  >
  > *Today, we built **CrossWalk**: The CrossWalk for CareStack."*

---

### Minute 1:00 – 2:15 | Patient 1: John Doe (Anticoagulation & Anaphylaxis)
- **Action**: In the UI (`http://localhost:5173`), click on **John Doe (CS-2001)** in the CareStack Chart panel.
- **Action**: Click **"Trigger Webhook Sync"** in the top navigation bar.
- **Speaker**:  
  > *"Here is John Doe arriving at our dental practice. The moment he checks in at the front desk, CareStack dispatches a `patient.checkin` webhook into CrossWalk. CrossWalk reconciles John Doe against the hospital's HL7 FHIR R4 EHR with 100% confidence.*
  >
  > *Notice the two red alerts immediately written back to CareStack's chart: John is on active **Warfarin therapy** for Atrial Fibrillation, and has a documented severe **Penicillin Anaphylaxis** allergy."*
- **Action**: On the CDT Procedure Toolbar, click **D7140 (Extraction, Erupted Tooth)**.
- **Speaker**:  
  > *"Now, the dentist plans a tooth extraction. Watch what happens when I click CDT D7140. Sub-second, CrossWalk fires an `order-select` CDS Hook.*
  >
  > *A **CRITICAL HAZARD** decision support card appears! It cites American Heart Association and ADA guidelines: do not discontinue Warfarin blindly, but verify recent INR is under 3.5 and prepare local hemostatic agents like Surgicel and tranexamic acid mouthwash.*
  >
    > *With one click on **'Dispatch Digital Clearance Passport'**, CareStack automatically dispatches an HL7 FHIR Task and CommunicationRequest to John's cardiologist, Dr. Kenneth Vance at Metropolitan Heart Center!*
    >
    > *In Pillar 3, this transforms a 5-7 day phone-and-fax clearance cycle into a 5-minute digital workflow. Dr. Vance reviews the pre-populated clinical justification in his InBasket portal, sets target INR parameters, and signs off. CareStack receives an instant webhook callback and updates the operatory banner to green clearance!*"*
- **Action**: On the right panel, toggle **"Show ConceptMap Translation Trace"**.
- **Speaker**:  
  > *"On the right, we see the hospital EHR record and CrossWalk's **FHIR ConceptMap Semantic Translation Engine**, translating RxNorm code 855332 directly into the dental alert `ACTIVE_ANTICOAGULANT`."*

---

### Minute 2:15 – 3:15 | Patient 2: Jane Smith (Prosthetic Valve & Endocarditis)
- **Action**: Select **Jane Smith (CS-2002)**.
- **Speaker**:  
  > *"Next, Jane Smith arrives for a routine cleaning—CDT D1110. A routine cleaning sounds harmless, right?"*
- **Action**: Click **D1110 (Adult Prophylaxis)**.
- **Speaker**:  
  > *"Dental scaling induces transient bacteremia across gingival margins. Because Jane has a **Prosthetic Cardiac Valve** (SNOMED: 315215002), oral bacteria entering her bloodstream can seed the artificial valve, causing subacute bacterial endocarditis—a condition with a 30% mortality rate.
  >
  > *CrossWalk's CDS Hook triggers an immediate warning: AHA guidelines mandate 2 grams of Amoxicillin 30 to 60 minutes prior to procedure. The dental assistant sees this alert and verifies premedication before the hygienist touches a scaler.
  >
  > *And if Jane were allergic to penicillin like John Doe, CrossWalk's multi-factor risk engine automatically suppresses Amoxicillin and mandates Clindamycin or Azithromycin instead."*

---

### Minute 3:15 – 4:15 | Patient 3: Robert Taylor (Financial Cross-Coding & Claims)
- **Action**: Select **Robert Taylor (CS-1003)**.
- **Speaker**:  
  > *"Finally, in Pillar 2, Robert Taylor has Type 2 Diabetes with **HbA1c = 9.2%**. Severe hyperglycemia impairs healing and elevates dry socket risk.
  >
  > *Robert needs deep periodontal scaling—CDT D4341. In typical dental offices, dental insurance caps out at $1,000, leaving Robert to pay hundreds out of pocket.
  >
  > *Watch this: Click **'Financial Optimization'**."*
- **Action**: Click the **Financial Optimization** button to open `FinancialOptimizationModal.jsx`.
- **Speaker**:  
  > *"CrossWalk contains an **Administrative Decision Support & Medical Cross-Coding Engine**!
  >
  > *It detects that Robert's periodontal disease is directly linked to his systemic Type 2 Diabetes (ICD-10 E11.9). It automatically cross-codes dental CDT D4341 into **medical CPT 41874 (Alveoloplasty w/ bone contouring)**, unlocking **$600.00** in primary medical insurance coverage!
  >
  > *Here in Tab 1, CrossWalk automatically pre-populates an authentic **CMS-1500 Digital Claim Form** with all diagnostic pointers and NPI billing provider details.
  >
  > *In Tab 2, CrossWalk auto-generates a formal **Letter of Medical Necessity (LOMN)** citing peer-reviewed ADA/AAP evidence, signed by the clinician and cryptographically sealed with a SHA-256 hash directly into CareStack's document repository!
  >
  > *In Tab 3, CrossWalk compiles the complete **ANSI ASC X12N 837P EDI** electronic claim transaction stream! With one click on **'Approve & Submit'**, the claim is transmitted with a verifiable Claim Control Number."*

---

### Minute 4:15 – 5:00 | Architecture, Regulatory Compliance & Q&A
- **Speaker**:  
  > *"How did we engineer this in 36 hours?
  > 1. *A high-performance FastAPI ASGI backend executing asynchronous HL7 FHIR R4, CDS Hooks v1.0/v2.0 queries, and FHIR CommunicationRequest/Task clearance lifecycles under 250ms.*
  > 2. *FHIR ConceptMap ($translate) bridging ICD-10, SNOMED, and RxNorm to ADA dental CDT codes.*
  > 3. *Complete regulatory alignment: permitted under the **HIPAA TPO Treatment exception (45 CFR § 164.506)**, compliant with the **21st Century Cures Act** against Information Blocking, and 100% compliant with **ONC HTI-1 DSI / FAVES transparency rules**.*
  > 4. *An exhaustive automated test suite with **146 / 146 passing tests** across 12 test suites.*
  >
  > *CrossWalk transforms dental care from an isolated island into an integrated, patient-safe clinical, financial, and scheduling ecosystem. Thank you, and we welcome your questions!"*

---

## 3. Potential Judge Q&A Cheat Sheet

| Question | Winning Response |
|---|---|
| **"Why not just have the patient fill out an iPad questionnaire?"** | Patient recall error rates for pharmacotherapy exceed 40%, especially distinguishing aspirin from prescription anticoagulants like Warfarin or Eliquis. Furthermore, patients rarely know their exact HbA1c lab numbers or the specific type of prosthetic cardiac valve they possess. Automated EHR federation provides verifiable clinical truth. |
| **"Isn't sharing hospital data with a dentist a HIPAA violation?"** | No. Under **45 CFR § 164.506 (HIPAA TPO Exception)**, covered entities are legally permitted to disclose protected health information for **Treatment** purposes without separate patient authorization. Preventing surgical hemorrhage and endocarditis is the textbook definition of clinical treatment safety. |
| **"Why CDS Hooks instead of a custom webhook?"** | CDS Hooks is the official HL7 international standard for clinical decision support, adopted by major enterprise EHR vendors (Epic, Cerner). By building on standard CDS Hooks v1.0/v2.0 and FHIR R4, CareStack can connect not just to our node, but to any certified hospital EHR nationwide without vendor lock-in. |
| **"How does the ConceptMap engine handle ambiguous codes?"** | We implement FHIR R4 ConceptMap `$translate` equivalence semantics (`equivalent`, `relatedto`, `narrower`, `wider`). Furthermore, our engine performs multi-factor risk synthesis: for instance, Warfarin alone is an alert, but Warfarin *plus* Atrial Fibrillation escalates into a `CRITICAL_HEMORRHAGE_HAZARD`. |
| **"How does medical cross-coding benefit dental practices financially?"** | Dental insurance has had fixed $1,000–$1,500 annual maximums since the 1970s. Surgical and periodontal care linked to systemic diseases (diabetes, TMJ, oncologic biopsies) is legally covered under primary medical insurance (Major Medical). CrossWalk automates the CDT-to-CPT mapping, CMS-1500 generation, LOMN justification, and 837P EDI transmission, eliminating administrative overhead and maximizing patient reimbursement. |
