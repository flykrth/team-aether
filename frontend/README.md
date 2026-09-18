# Frontend — Medical-Dental Interoperability Node (MDIN)

Modern React + Vite + Tailwind CSS dashboard providing a unified clinical view connecting CareStack Dental Practice Management with Medical EHRs and CDS Hooks v1.0.

## Stack

- **Framework / Bundler**: React 18 & Vite
- **Styling**: Tailwind CSS & PostCSS
- **Icons**: Lucide React
- **API Client**: Native Fetch with Vite Proxy & Configurable Base URL
- **Dev Server Port**: `5173` (with fallback/cross-origin support for `3000`)

## Key Features

1. **Split-Screen Chairside Workspace**: CareStack dental chart on the left, live CDS decision overlay and Medical EHR trace on the right.
2. **Interactive CDT Procedure Toolbar**: Selecting a procedure (D0120, D1110, D4341, D7140, D7210) fires the `order-select` CDS Hook against the MDIN engine in real time.
3. **CDS Hooks Real-Time Alerts**: Cards styled by indicator (critical/warning/info) surfacing cross-specialty contraindications (bleeding risk, AHA antibiotic prophylaxis, penicillin allergy), with chairside actions to append a medical alert to the chart or request a pre-op INR consult.
4. **Medical EHR Interoperability Trace**: Raw FHIR `Condition`, `MedicationRequest`, `AllergyIntolerance`, and `Observation` (lab) resources, with a toggle showing the live ConceptMap `$translate` transformation into dental alert codes.
5. **Live Medical Alerts Banner & Webhook Sync**: Chart alerts synchronized from the external EHR, plus a one-click check-in webhook simulation.
6. **Developer Console & Endpoint Tester**: Live REST/CDS inspection against `/api/carestack`, `/api/fhir`, and `/cds-services` with formatted JSON responses.

## Local Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
```

### 3. Start Development Server

```bash
npm run dev
```

The frontend will run at `http://localhost:5173`.
All requests to `/api`, `/cds-services`, and `/health` are automatically proxied to `http://localhost:8000`.

### 4. Build for Production (Node.js)

```bash
npm run build
npm run preview
```

### 5. Production Docker Deployment (Nginx Reverse Proxy)

```bash
# Build multi-stage production Nginx container
docker build -t mdin-frontend ./frontend

# Run container exposing port 80
docker run -d -p 80:80 --name mdin-frontend mdin-frontend
```

## Project Layout

```
frontend/
├── index.html                     # HTML5 entrypoint
├── package.json                   # Dependencies and scripts
├── vite.config.js                 # Vite config + backend API proxy
├── tailwind.config.js             # Tailwind CSS theme extension
├── postcss.config.js              # PostCSS plugins
├── setup.sh                       # Frontend quickstart setup script
├── src/
│   ├── main.jsx                   # React root render
│   ├── App.jsx                    # Master application container
│   ├── index.css                  # Tailwind styles
│   ├── services/
│   │   └── api.js                 # API client for backend endpoints
│   └── components/
│       ├── Navbar.jsx             # Top bar with status & docs link
│       ├── PatientHeader.jsx      # Patient demographic banner
│       ├── ClinicalContext.jsx    # Consolidated clinical context panel
│       ├── CareStackChart.jsx     # Dental chart: patient, CDT toolbar, alerts banner
│       ├── CDSHookCard.jsx        # CDS Hooks card renderer & chairside actions
│       ├── MedicalEHRViewer.jsx   # Raw FHIR resources & ConceptMap $translate trace
│       ├── EvidenceDrawer.jsx     # Evidence & guideline provenance drawer
│       ├── PatientTimeline.jsx    # Chronological clinical event timeline
│       ├── PatientRecordViewer.jsx # Dual medical/dental viewer & sync
│       ├── CdsAlertCard.jsx       # Legacy CDS Hooks card renderer
│       ├── InteroperabilityDashboard.jsx # System topology card
│       ├── EndpointTester.jsx     # Live API tester
│       └── DeveloperConsole.jsx   # Developer inspection console
└── .env.example
```