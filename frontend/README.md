# Frontend — Medical-Dental Interoperability Node (MDIN)

Modern React + Vite + Tailwind CSS dashboard providing a unified clinical view connecting CareStack Dental Practice Management with Medical EHRs and CDS Hooks v1.0.

## Stack

- **Framework / Bundler**: React 18 & Vite
- **Styling**: Tailwind CSS & PostCSS
- **Icons**: Lucide React
- **API Client**: Native Fetch with Vite Proxy & Configurable Base URL
- **Dev Server Port**: `5173` (with fallback/cross-origin support for `3000`)

## Key Features

1. **Interoperability Topology Monitor**: Live connection status of CareStack PMS, FHIR R4 server, and CDS Hooks engine.
2. **Dual-Panel Clinical Record Viewer**: Side-by-side comparison of CareStack proposed dental treatment plans (CDT codes like D7140, D4341) with Medical EHR diagnoses, lab values (HbA1c, INR), and allergies.
3. **CDS Hooks Real-Time Alerts**: Automated alert cards highlighting cross-specialty contraindications (MRONJ osteonecrosis risk, AHA antibiotic prophylaxis requirements, bleeding risks).
4. **Interactive Endpoint Tester**: One-click REST/CDS caller allowing hackathon judges to execute live API queries against `/api/carestack`, `/api/fhir`, and `/cds-services` and view formatted JSON with response latency.

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
│       ├── InteroperabilityDashboard.jsx # System topology card
│       ├── PatientRecordViewer.jsx # Dual medical/dental viewer & sync
│       ├── CdsAlertCard.jsx       # CDS Hooks card renderer
│       └── EndpointTester.jsx     # Live API tester for judges
└── .env.example
```