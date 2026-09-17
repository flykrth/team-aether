# MDIN Live Demonstration Guide (DSOLVE 2026)

### 3–5 Minute Live Hackathon Presentation Script
**Problem 6: Open Problem Statement — Dental Industry**  
**Team Aether · College of Engineering Trivandrum (CET)**

---

## 1. Setup Before Presentation

1. **Terminal 1 (Backend)**:
   ```bash
   source .venv/bin/activate
   python backend/run.py
   ```
   *Verify: `http://localhost:8000/docs` is live.*

2. **Terminal 2 (Frontend)**:
   ```bash
   cd frontend
   npm run dev
   ```
   *Verify: `http://localhost:5173` is loaded in your browser.*

---

## 2. Minute-by-Minute Presentation Script

### Minute 0:00 – 1:00 | The Hook: The "Two-System Problem"
- **Speaker**:  
  > *"Judges, in the US healthcare system, medical care and dental care are completely disconnected. When a dentist opens their PMS—like CareStack—they are completely blind to the patient's hospital record in Epic or Cerner.*
  >
  > *A patient sitting in the dental chair for a tooth extraction might be on high-dose Warfarin for Atrial Fibrillation, or have a prosthetic heart valve requiring antibiotic premedication. If the patient forgets to write it down on an intake clipboard, an invasive extraction can lead to fatal uncontrolled hemorrhage or life-threatening Infective Endocarditis.*
  >
  > *Today, we built **MDIN**: The Medical-Dental Interoperability Node for CareStack."*

---

### Minute 1:00 – 2:15 | Patient 1: John Doe (Anticoagulation & Anaphylaxis)
- **Action**: In the UI (`http://localhost:5173`), click on **John Doe (CS-2001)**.
- **Action**: Click **"Simulate Webhook Sync"** in the top navigation bar.
- **Speaker**:  
  > *"Here is John Doe arriving at our dental practice. The moment he checks in, CareStack fires a webhook into MDIN. MDIN reconciles John Doe against the hospital's HL7 FHIR R4 EHR, resolving his medical record number with 100% confidence.*
  >
  > *Notice the two red alerts immediately written into CareStack's chart: John is on active **Warfarin therapy** for Atrial Fibrillation, and has a severe **Penicillin Anaphylaxis** allergy."*
- **Action**: On the CDT Procedure Toolbar, click **D7140 (Extraction, Erupted Tooth)**.
- **Speaker**:  
  > *"Now, the dentist plans a tooth extraction. Watch what happens when I click CDT D7140. Sub-second, MDIN fires an `order-select` CDS Hook.*
  >
  > *A **CRITICAL HAZARD** decision support card appears! It cites American Heart Association and ADA guidelines: do not discontinue Warfarin blindly, but verify recent INR is under 3.5 and prepare local hemostatic agents like Surgicel and tranexamic acid mouthwash.*
  >
  > *With one click on **'Request INR Consult'**, CareStack automatically dispatches a lab consult request to John's primary physician."*
- **Action**: On the right panel, toggle **"Show ConceptMap Translation Trace"**.
- **Speaker**:  
  > *"On the right, we see the hospital EHR record and MDIN's **FHIR ConceptMap Semantic Translation Engine**, translating RxNorm code 855332 directly into the dental alert `ACTIVE_ANTICOAGULANT`."*

---

### Minute 2:15 – 3:30 | Patient 2: Jane Smith & Patient 3: Robert Taylor
- **Action**: Select **Jane Smith (CS-2002)**.
- **Speaker**:  
  > *"Next, Jane Smith arrives for a routine cleaning—CDT D1110. A routine cleaning sounds harmless, right?"*
- **Action**: Click **D1110 (Adult Prophylaxis)**.
- **Speaker**:  
  > *"Dental scaling induces transient bacteremia. Because Jane has a **Prosthetic Cardiac Valve** (SNOMED: 315215002), bacteria entering her bloodstream can seed the artificial valve, causing subacute bacterial endocarditis—a condition with a 30% mortality rate.*
  >
  > *MDIN's CDS Hook triggers an immediate warning: AHA guidelines mandate 2 grams of Amoxicillin 30 to 60 minutes prior to procedure. The dental assistant sees this alert and verifies premedication before the hygienist touches a scaler."*
- **Action**: Select **Robert Taylor (CS-1003)**.
- **Speaker**:  
  > *"Finally, Robert Taylor has Type 2 Diabetes. MDIN pulls his latest hospital lab observation via FHIR USCDI v5: **HbA1c = 9.2%**.*
  >
  > *MDIN warns the dentist that severe hyperglycemia impairs wound healing and elevates dry socket risk by over 300%. It recommends morning scheduling and prophylactic chlorhexidine rinses."*

---

### Minute 3:30 – 4:30 | Architecture & Regulatory Compliance
- **Speaker**:  
  > *"How did we build this in 36 hours?*
  > 1. *FastAPI backend executing asynchronous FHIR R4 and CDS Hooks v1.0/v2.0 queries.*
  > 2. *FHIR ConceptMap ($translate) bridging ICD-10, SNOMED, and RxNorm to ADA dental CDT codes.*
  > 3. *Complete regulatory alignment: permitted under the **HIPAA TPO Treatment exception**, compliant with the **21st Century Cures Act** against Information Blocking, and 100% compliant with the **ONC HTI-1 DSI transparency rules**.*
  > 4. *A comprehensive automated test suite with **50 passing tests**.*
  >
  > *MDIN transforms dental care from an isolated island into an integrated, patient-safe clinical ecosystem. Thank you, and we welcome your questions!"*

---

## 3. Potential Judge Q&A Cheat Sheet

| Question | Winning Response |
|---|---|
| **"Why not just have the patient fill out an iPad questionnaire?"** | Patient recall error rates for pharmacotherapy exceed 40%, especially distinguishing aspirin from prescription anticoagulants like Warfarin or Eliquis. Furthermore, patients rarely know their exact HbA1c lab numbers or the specific type of prosthetic cardiac valve they possess. Automated EHR federation provides verifiable clinical truth. |
| **"Isn't sharing hospital data with a dentist a HIPAA violation?"** | No. Under **45 CFR § 164.506 (HIPAA TPO Exception)**, covered entities are legally permitted to disclose protected health information for **Treatment** purposes without separate patient authorization. Preventing surgical hemorrhage and endocarditis is the textbook definition of clinical treatment safety. |
| **"Why CDS Hooks instead of a custom webhook?"** | CDS Hooks is the official HL7 international standard for clinical decision support, adopted by major EHR vendors (Epic, Cerner). By building on standard CDS Hooks v1.0/v2.0 and FHIR R4, CareStack can connect not just to our node, but to any certified hospital EHR nationwide without vendor lock-in. |
| **"How does the ConceptMap engine handle ambiguous codes?"** | We implement FHIR R4 ConceptMap `$translate` equivalence semantics (`equivalent`, `relatedto`, `narrower`, `wider`). Furthermore, our engine performs multi-factor risk synthesis: for instance, Warfarin alone is an alert, but Warfarin *plus* Atrial Fibrillation escalates into a `CRITICAL_HEMORRHAGE_HAZARD`. |
