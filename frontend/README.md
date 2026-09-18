# Frontend — Medical-Dental Interoperability Node (MDIN)

Modern React + Vite + Tailwind CSS chairside clinical workstation providing a unified interface connecting CareStack Dental Practice Management with enterprise Hospital Medical EHRs, HL7® CDS Hooks™ v1.0/v2.0, and an automated Medical Cross-Coding / Financial Optimization dashboard.

---

## Technical Stack

- **Framework & Bundler**: React 18 & Vite
- **Styling & Layout**: Tailwind CSS & PostCSS
- **Iconography**: Lucide React
- **API Client**: Native Fetch with Vite Development Proxy & Configurable Base URL
- **Production Server**: Multi-stage Nginx Reverse Proxy (Serving static bundle & routing `/api/` to backend)
- **Default Ports**: Port `5173` (Development Server), Port `80` (Production Nginx Gateway)

---

## Key Clinical & Administrative Capabilities

1. **Split-Screen Chairside Operatory Workspace**:
   - Left Column: CareStack dental chart, patient demographics, active medical alert banner, interactive CDT procedure toolbar, and active treatment plan.
   - Right Column: Live CDS Hooks decision support overlay, federated medical EHR records, and interactive ConceptMap translation trace.
2. **Interactive CDT Procedure Toolbar (Odontogram Actions)**:
   - Selecting a CDT dental procedure (e.g., `D0120`, `D1110`, `D4341`, `D7140`, `D7210`) fires an `order-select` CDS Hook against the MDIN engine sub-second.
3. **Evidence-Based CDS Decision Support Cards**:
   - Styled by indicator severity (`critical` red pulsing, `warning` amber, `info` blue).
   - Surfaces contraindications (anticoagulant hemorrhage hazard, AHA antibiotic prophylaxis for prosthetic valves, penicillin anaphylaxis conflicts).
   - One-click chairside actions: "Request Pre-Op INR Consult", "Append Alert to CareStack Chart".
4. **Federated Medical EHR Interoperability Trace**:
   - Visualizes raw HL7 FHIR R4 resources (`Condition`, `MedicationRequest`, `AllergyIntolerance`, `Observation`) directly from the hospital EHR.
   - Interactive toggle revealing real-time FHIR ConceptMap `$translate` semantic mappings (e.g., RxNorm `855332` $\to$ `ACTIVE_ANTICOAGULANT`).
5. **Financial Optimization & Medical Cross-Coding Modal (`FinancialOptimizationModal.jsx`)**:
   - **Tab 1: Interactive CMS-1500 Claim Form Facsimile**: Pixel-perfect digital facsimile with authentic red-border styling conforming to NUCC Form 1500 (02-12).
   - **Tab 2: Letter of Medical Necessity (LOMN) Live Viewer**: Formally structured clinical justification narrative linking dental surgery to systemic endocrine/cardiovascular conditions, complete with clinician signature block, hospital MRN, and cryptographic SHA-256 verification badge.
   - **Tab 3: ANSI ASC X12N 837P EDI Stream**: Authentic HIPAA Title II Electronic Health Care Claim Professional transaction stream with one-click clipboard copying.
   - **Action Bar**: "Approve & Submit Electronic 837P Claim" (dispatches claim, generates Claim Control Number, and attaches document to CareStack).

---

## Local Setup & Execution

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

### 3. Launch Development Server

```bash
npm run dev
```

The clinical interface will run at `http://localhost:5173`.  
*The Vite development server automatically proxies all `/api`, `/cds-services`, and `/health` requests to the backend server at `http://localhost:8000`.*

### 4. Build for Production

```bash
npm run build
npm run preview
```

### 5. Production Docker Deployment (Nginx Reverse Proxy)

```bash
# Build production multi-stage Nginx container
docker build -t mdin-frontend ./frontend

# Run container exposing port 80
docker run -d -p 80:80 --name mdin-frontend mdin-frontend
```

---

## Project Layout

```
frontend/
├── index.html                           # HTML5 entrypoint
├── package.json                         # Dependencies and scripts
├── vite.config.js                       # Vite configuration & backend proxy
├── tailwind.config.js                   # Tailwind CSS theme extension
├── postcss.config.js                    # PostCSS configuration
├── src/
│   ├── main.jsx                         # React root mount
│   ├── App.jsx                          # Master application container & state orchestration
│   ├── index.css                        # Tailwind styles & custom animations
│   ├── services/
│   │   └── api.js                       # RESTful API client for MDIN & CareStack endpoints
│   └── components/
│       ├── Navbar.jsx                   # Navigation header with backend telemetry & docs links
│       ├── PatientHeader.jsx            # Patient demographic header
│       ├── ClinicalContext.jsx          # Consolidated clinical context panel
│       ├── CareStackChart.jsx           # Dental chart: patient selector, CDT toolbar, alert banner
│       ├── CDSHookCard.jsx              # CDS Hooks card renderer & chairside action dispatchers
│       ├── MedicalEHRViewer.jsx         # Raw FHIR resources & ConceptMap translation trace
│       ├── FinancialOptimizationModal.jsx # CMS-1500 facsimile, LOMN viewer & 837P EDI modal
│       ├── EvidenceDrawer.jsx           # Clinical guideline evidence drawer (AHA, ADA, AAOMS)
│       ├── PatientTimeline.jsx          # Chronological clinical event timeline
│       ├── PatientRecordViewer.jsx      # Dual medical/dental viewer & sync interface
│       ├── InteroperabilityDashboard.jsx # System topology card
│       ├── EndpointTester.jsx           # Interactive API tester
│       └── DeveloperConsole.jsx         # Developer inspection console
└── .env.example
```