# Judging Presentation & Live Demo Protocol

**System Name**: Medical-Dental Interoperability Node (MDIN) for CareStack  
**Event**: DSOLVE 2026 · DRISHTI · College of Engineering Trivandrum (CET)  
**Track**: Problem 6 — Open Problem Statement (US & Global Dental Industry)  
**Team**: Team Aether  
**Target Audience**: CareStack Engineering Leadership, Health IT Architects, Clinical Informatics Judges  
**Presentation Duration**: 3 – 5 Minutes (Live Pitch + Demo) followed by Technical Q&A

---

## Executive Pitch Deck Outline (5 Slides)

### Slide 1: The Triple Liability in Dental Practice Software

- **The Problem**: Dentistry and medicine exist in total technological isolation. When hospitals adopted certified EHRs (Epic, Cerner), dental software remained siloed.
- **The Three Liabilities**:
  1. **Clinical Liability (Patient Safety)**: Over 40–50% of patients fail to self-report critical systemic medications. Dentists perform surgical extractions blind to active Warfarin/DOAC anticoagulants (fatal hemorrhage risk) or prosthetic heart valves (30% mortality bacterial endocarditis).
  2. **Financial Liability (Lost Practice Revenue & Patient Burden)**: Annual dental insurance maximums are capped at $1,000–$1,500. Medically necessary procedures (periodontal therapy for uncontrolled diabetics, jaw reconstructions, biopsies) are denied by dental payers and rarely cross-coded to medical insurance due to coding complexity.
  3. **Operational Liability (Schedule Density & Chair Utilization)**: Obtaining physician medical clearance requires 5–7 days of manual phone calls and faxes. Chairs sit empty, surgeries are delayed, and administrative overhead spikes.
- **The Core Solution**: **MDIN (Medical-Dental Interoperability Node)** — an open-standards gateway engineered specifically for CareStack, transforming CareStack into the world's first fully interoperable medical-dental PMS.

---

### Slide 2: The Standards-Based Architecture (Why FHIR + CDS Hooks Beat LLM-Only Pipelines)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 WHY STANDARDS-BASED BEATS LLM-ONLY                              │
├────────────────────────────────┬────────────────────────────────┬──────────────────────────────┤
│  DIMENSION                     │  PROPRIETARY / LLM-ONLY        │  MDIN ARCHITECTURE           │
├────────────────────────────────┼────────────────────────────────┼──────────────────────────────┤
│  Clinical Determinism          │  Non-deterministic / Hallucinatory │  100% Deterministic ConceptMap   │
│  Informatics Standards         │  Proprietary JSON payloads     │  HL7® FHIR® R4 (USCDI v5)    │
│  Decision Support Integration  │  Custom popups & chat widgets  │  HL7® CDS Hooks™ v1.0 / v2.0 │
│  Claims Standardization        │  Manual claim text generation  │  ANSI ASC X12N 837P & CMS-1500│
│  Latency SLA                   │  1,500ms – 4,000ms             │  < 250ms deterministic lookup│
│  Regulatory Defensibility      │  Black-box AI (HTI-1 breach)   │  ONC HTI-1 FAVES & AHA/ADA Cited │
└────────────────────────────────┴────────────────────────────────┴──────────────────────────────┘
```

- **Core Architectural Components**:
  - **CareStack Web API V1 Surface**: Enforces 3-Key Header Authentication (`VendorKey`, `AccountKey`, `AccountId`) with native `PatientViewModel`, appointment endpoints, and periodontal probing depth mapping.
  - **HL7 FHIR R4 USCDI v5 Pipeline**: Ingests Conditions (ICD-10-CM / SNOMED CT), MedicationRequests (RxNorm), Observations (LOINC), and Allergies.
  - **Semantic ConceptMap Engine (`$translate`)**: Normalizes disparate medical vocabularies to dental CDT procedure codes.
  - **CDS Hooks v1.0/v2.0**: Implements standard `patient-view` and `order-select` hooks with prefetched clinical context.
  - **Digital Clearance Passport Engine**: Employs HL7 FHIR R4 `Task` (code: `medical-clearance-request`) and `CommunicationRequest` resources for direct EHR InBasket integration.

---

### Slide 3: Live Synchronous Demo Execution Protocol (Step-by-Step Clicks)

This protocol is timed for a seamless 3-minute live walkthrough during the judging round:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ TIMECODE │ STEP & CLINICAL SCENARIO               │ ACTIONS & CLICKSTREAM                       │
├──────────┼────────────────────────────────────────┼─────────────────────────────────────────────┤
│ 00:00 -  │ INTRODUCTION & DEMO BAR                │ • Show CareStack Dental Operatory View.     │
│ 00:30    │ "Welcome to MDIN for CareStack."       │ • Point out the DSOLVE 2026 Live Pitch      │
│          │                                        │   Dual-View Switcher on top.                │
├──────────┼────────────────────────────────────────┼─────────────────────────────────────────────┤
│ 00:30 -  │ PILLAR 1: CLINICAL SAFETY              │ • Select patient: John Doe (CS-2001).       │
│ 01:30    │ John Doe · CDT D7140 Extraction        │ • Click CDT 'D7140' (Extraction, Erupted).  │
│          │ Critical Anticoagulant Contraindication│ • Observe instant red glowing CDS Hook card:│
│          │                                        │   "CRITICAL CLINICAL HAZARD: High           │
│          │                                        │    Hemorrhage Hazard on Warfarin Therapy".  │
│          │                                        │ • Click "Post Medical Alert to CareStack".  │
│          │                                        │ • Alert posts immediately to patient chart. │
├──────────┼────────────────────────────────────────┼─────────────────────────────────────────────┤
│ 01:30 -  │ PILLAR 3: SCHEDULE EFFICIENCY          │ • On the same D7140 card, click:            │
│ 02:45    │ 1-Click Digital Clearance Passport     │   "Dispatch Digital Clearance Passport".    │
│          │ Real-Time InBasket & Webhook Loop      │ • Observe live status change:               │
│          │                                        │   "Passport Dispatched via FHIR Task".      │
│          │                                        │ • Point to the demographic header: live     │
│          │                                        │   amber badge "Clearance Requested".        │
│          │                                        │ • Switch to "External Physician Portal".    │
│          │                                        │ • Dr. Kenneth Vance, MD reviews InBasket,   │
│          │                                        │   selects "Approve with Conditions", sets   │
│          │                                        │   INR 2.0-2.5, and clicks "Electronically   │
│          │                                        │   Sign & Transmit".                         │
│          │                                        │ • Switch back to CareStack: header badge is │
│          │                                        │   now green "Surgically Cleared by          │
│          │                                        │   Cardiology", with slide-in toast notice!  │
├──────────┼────────────────────────────────────────┼─────────────────────────────────────────────┤
│ 02:45 -  │ PILLAR 2: FINANCIAL OPTIMIZATION       │ • Switch patient to: Robert Taylor (CS-1003)│
│ 03:30    │ Robert Taylor · Uncontrolled Diabetes  │   (Type 2 Diabetes, HbA1c 9.2%).            │
│          │ Medical Cross-Coding & Claims          │ • Click CDT 'D4341' (Perio Scaling).        │
│          │                                        │ • Observe emerald Opportunity Card:         │
│          │                                        │   "Est. Medical Coverage: $600.00".         │
│          │                                        │ • Click "Review Medical Claim & LOMN".      │
│          │                                        │ • Show authentic CMS-1500 red-ink form,     │
│          │                                        │   compiled 837P EDI stream, and SHA-256     │
│          │                                        │   signed Letter of Medical Necessity        │
│          │                                        │   ingested into CareStack Documents!        │
└──────────┴────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

### Slide 4: Regulatory & Commercial Moat

1. **HIPAA Privacy Rule TPO Exception (45 CFR § 164.506)**:
   - Covers Treatment, Payment, and Health Care Operations.
   - Authorizes covered entities (hospital EHRs and dental practices) to disclose Protected Health Information (PHI) for coordination of care without individual patient authorization.
2. **ONC 21st Century Cures Act & Information Blocking Rule (45 CFR Part 171)**:
   - Mandates that certified Health IT developers (Epic, Cerner) provide standardized FHIR R4 APIs without unreasonable delays or fees.
   - MDIN operates as an authorized actor exercising patient and clinician access rights under USCDI v5.
3. **ONC HTI-1 Algorithmic Transparency (FAVES Principles)**:
   - All Decision Support Interventions (DSI) comply with the **FAVES** mandate: **Fair, Appropriate, Valid, Effective, and Safe**.
   - Every CDS card displays plain-language clinical justification, source attribution (AHA, ADA, AAOMS), and explicit evidence provenance.

---

## Comprehensive Technical Defense Q&A

### Q1: "How do you handle HIPAA consent and privacy for medical data retrieval?"
> **Answer**:  
> "Under the **HIPAA Privacy Rule (45 CFR § 164.506 - Treatment, Payment, and Health Care Operations)**, healthcare providers are explicitly permitted to exchange Protected Health Information for clinical treatment activities without requiring special patient authorization or business associate agreements between independent providers.  
> When a patient check-in occurs at a dental practice, that practice is providing direct patient care. Querying the patient's medical history for active anticoagulant therapy or cardiac valve status is a direct **Treatment activity**. Furthermore, MDIN implements strict role-based access control, does not persist external PHI outside the patient's authenticated session, and records complete SHA-256 cryptographic audit provenance for every FHIR interaction."

---

### Q2: "How does CDS Hooks avoid clinician alert fatigue?"
> **Answer**:  
> "Alert fatigue is a well-documented cause of clinician burnout and ignored warnings in EHRs. MDIN solves this through three deliberate engineering mechanisms:  
> 1. **Context-Specific Prefetch Hook Scoping**: Rather than blasting alerts continuously, MDIN's `order-select` hook only evaluates rules when an invasive or bacteremia-inducing procedure is actively clicked on the odontogram. Non-invasive procedures (e.g. routine exam `D0120`) do not trigger surgical hemorrhage warnings.  
> 2. **Multi-Factor Risk Synthesis Engine**: MDIN does not alert on isolated data points. For instance, Warfarin therapy alone triggers an informational tag; it is only when combined with an invasive extraction code (`D7140`) and an elevated or absent INR that MDIN escalates the card to `CRITICAL`.  
> 3. **Concise Actionable Design**: Cards strictly enforce a $\le 140$ character primary headline, accompanied by one-click resolution buttons (*'Post Medical Alert'*, *'Dispatch Clearance Passport'*), allowing the clinician to resolve the alert in under 2 seconds."

---

### Q3: "How does the Digital Clearance Passport link into external hospital EHRs?"
> **Answer**:  
> "Rather than creating a proprietary messaging protocol, MDIN implements the official **HL7® FHIR® R4 Task resource** paired with **CommunicationRequest**:  
> - When the dentist clicks *'Dispatch Digital Clearance Passport'*, MDIN packages patient demographics, dentist NPI, proposed CDT codes, and ConceptMap clinical justification into a FHIR `Task` with code `medical-clearance-request`.  
> - In real-world enterprise deployments, this Task maps directly to the hospital's **Epic InBasket** or **Cerner Message Center** pool for the attending specialist (e.g., Dr. Kenneth Vance, Cardiology).  
> - The external specialist reviews the structured request within their EHR, enters coagulation targets (e.g., target INR 2.0–2.5), and signs off electronically.  
> - Upon signing, an HL7 FHIR Task completion event triggers an authenticated webhook callback to CareStack (`POST /api/carestack/patients/{id}/medical-clearance-status`), updating the patient's operatory banner in real time without human intervention."

---

### Q4: "What is the computational latency of the decision engine, and how does it scale?"
> **Answer**:  
> "Our architecture guarantees a total roundtrip response latency of **< 250 milliseconds** at chairside:  
> 1. **In-Memory Graph Lookups**: The FHIR ConceptMap semantic engine operates via pre-compiled in-memory hash mappings linking ICD-10, SNOMED CT, RxNorm, and LOINC codes to CDT safety categories.  
> 2. **Prefetched USCDI Bundles**: By leveraging the CDS Hooks `prefetch` specification, the patient's medical summary is fetched once during chart loading (`patient-view`), so subsequent odontogram clicks (`order-select`) evaluate instantaneously without redundant HTTP roundtrips.  
> 3. **Asynchronous ASGI Concurrency**: The backend runs on FastAPI and Uvicorn with asynchronous event loops, easily sustaining hundreds of concurrent chairside requests with sub-50ms engine processing time."

---

## Live Judging Checklist & Rehearsal Metrics

- [x] **Backend Test Suite Verified**: 146 / 146 tests passing in Pytest (`pytest backend/tests/`).
- [x] **Frontend Production Build Verified**: Zero errors in Vite build (`npm run build`).
- [x] **Chairside Demo Clicks Validated**:
  - `CS-2001` (John Doe): Red critical card on `D7140` -> 1-click clearance dispatch -> live amber badge.
  - `Physician Portal`: InBasket review -> Dr. Vance signs -> instantaneous CareStack green clearance.
  - `CS-1003` (Robert Taylor): Emerald cross-coding card on `D4341` -> CMS-1500 & LOMN modal.
- [x] **Presentation Deck Timing**: 3:45 total speaking time, leaving 1:15 for technical Q&A.
