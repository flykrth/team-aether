# Backend — Medical-Dental Interoperability Node (MDIN)

Backend microservice providing bi-directional synchronization, HL7® FHIR® R4 standard endpoints, CareStack PMS Web API V1 integration, real-time Clinical Decision Support (CDS Hooks v1.0/v2.0), and automated Medical Cross-Coding / ANSI ASC X12N 837P EDI claim generation.

---

## Technical Stack & Standards

- **Language / Runtime**: Python 3.10+
- **Web Framework**: FastAPI (Asynchronous REST API)
- **ASGI Server**: Uvicorn
- **Data Validation & Schemas**: Pydantic v2 & Pydantic-Settings
- **HTTP Client**: HTTPX (Asynchronous HTTP/2-ready client)
- **Automated Testing**: Pytest & FastAPI TestClient (**132/132 Passing Tests**)
- **Health IT Standards**:
  - **HL7® FHIR® Release 4.0.1** (USCDI v5 Conformance)
  - **HL7 CDS Hooks™ v1.0 / v2.0** (`patient-view`, `order-select`)
  - **FHIR ConceptMap** (`$translate` semantic vocabulary cross-walk)
- **Claims & Billing Standards**:
  - **ANSI ASC X12N 837P** (Health Care Claim: Professional, Version 005010X222A1)
  - **NUCC CMS-1500** (Form 1500 02-12 Digital Facsimile)
  - **ADA CDT to AMA CPT Crosswalk Engine**

---

## Local Setup & Execution

### 1. Create and Activate Virtual Environment

```bash
# From repository root
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Configure Environment

```bash
cp backend/.env.example backend/.env
```

### 4. Start Backend Server

```bash
python backend/run.py
```

The server will start on port `8000`:
- **Interactive Swagger UI**: `http://localhost:8000/docs`
- **ReDoc Documentation**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`
- **Health Check Probe**: `http://localhost:8000/health`

### 5. Production Docker Deployment

```bash
# Build standalone backend container image
docker build -t mdin-backend ./backend

# Run container exposing port 8000
docker run -d -p 8000:8000 --name mdin-backend mdin-backend
```

---

## API Endpoints Reference

### 1. CareStack Web API V1 Surface (`/api/v1.0`)
All requests authenticate using three header keys: `VendorKey`, `AccountKey`, and `AccountId`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1.0/auth/verify` | Verify CareStack API keys (VendorKey, AccountKey, AccountId) |
| `GET` | `/api/v1.0/patients/{id}` | Read single patient record (`PatientViewModel`) |
| `POST` | `/api/v1.0/patients/search` | Search patients with `SearchRequest` (`PatientSearchResponseModel`) |
| `POST` | `/api/v1.0/patients` | Create new CareStack patient record |
| `PUT` | `/api/v1.0/patients` | Update existing CareStack patient record |
| `GET` | `/api/v1.0/patients/{id}/periodontal-charting` | Full-mouth periodontal probing examination |
| `GET` | `/api/v1.0/procedure-codes` | List ADA CDT dental procedure codes |
| `GET` | `/api/v1.0/treatments/appointment-procedures/{id}` | Get procedure code IDs assigned to an appointment |
| `POST` | `/api/v1.0/appointments` | Book new chairside appointment |
| `GET` | `/api/v1.0/appointments/{id}` | Read appointment details |
| `PUT` | `/api/v1.0/appointments/{id}/modify-status` | Modify status of appointment (Scheduled, InChair, Checkout) |
| `PUT` | `/api/v1.0/appointments/{id}/checkout` | Checkout appointment post-procedure |
| `PUT` | `/api/v1.0/appointments/{id}/cancel` | Cancel chairside appointment |
| `GET` | `/api/v1.0/appointment-status` | List all available appointment statuses |
| `GET` | `/api/v1.0/sync/patients` | Incremental patient synchronization |
| `GET` | `/api/v1.0/sync/treatment-procedures` | Incremental dental treatment procedure synchronization |
| `GET` | `/api/v1.0/locations` | List clinic locations |
| `GET` | `/api/v1.0/operatories` | List dental operatories / chairs |
| `GET` | `/api/v1.0/patients/{id}/documents` | Retrieve clinical documents & LOMN attached to chart |
| `POST` | `/api/v1.0/patients/{id}/documents` | Attach signed clinical document/LOMN with SHA-256 |

### 2. MDIN Core & Federated EHR Endpoints (`/api/carestack` & `/api/fhir`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Node health status and version telemetry |
| `GET` | `/` | Service directory and metadata |
| `GET` | `/api/carestack/status` | CareStack connectivity and sync telemetry |
| `GET` | `/api/carestack/patients` | List CareStack dental patients & active treatment plans |
| `POST` | `/api/carestack/webhook` | Ingest appointment/check-in events and trigger sync |
| `POST` | `/api/carestack/patients/{id}/medical-alerts` | Write critical medical alert back to CareStack chart |
| `GET` | `/api/carestack/patients/{id}/medical-alerts` | Retrieve chart alerts for chairside display |
| `POST` | `/api/carestack/sync` | Trigger bi-directional PMS $\leftrightarrow$ EHR sync |
| `GET` | `/api/fhir/metadata` | FHIR R4 CapabilityStatement |
| `GET` | `/api/fhir/server-status` | Probe live HL7 public test server ping latency |
| `GET` | `/api/fhir/Patient` | FHIR Patient demographics (exact & probabilistic) |
| `GET` | `/api/fhir/Patient/{id}` | Read single FHIR Patient by ID or MRN |
| `GET` | `/api/fhir/Patient/{id}/$everything` | **USCDI v5** comprehensive medical record bundle export |
| `POST` | `/api/fhir/ConceptMap/$translate` | Translate medical code (ICD/SNOMED/RxNorm) to dental alert |
| `POST` | `/api/fhir/Patient/{id}/$evaluate-risks` | Synthesize multi-factor dental risks from patient EHR |

### 3. HL7 CDS Hooks Engine (`/cds-services`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/cds-services` | CDS Hooks discovery endpoint catalog |
| `POST` | `/cds-services/patient-view-alert` | Evaluate `patient-view` hook when opening patient chart |
| `POST` | `/cds-services/order-select-contraindication` | Real-time CDT procedure contraindication evaluation |

### 4. Administrative Decision Support & Medical Billing (`/api/billing`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/billing/evaluate-claim` | Evaluate dental CDT for medical CPT cross-coding |
| `GET` | `/api/billing/crosswalk-rules` | Get active FHIR ConceptMap CDT-to-CPT crosswalk rules |
| `POST` | `/api/billing/generate-837p` | Convert CMS-1500 claim into ANSI ASC X12N 837P EDI |
| `POST` | `/api/billing/generate-and-attach-lomn` | Generate Letter of Medical Necessity & attach to CareStack |

---

## Automated Verification & Test Suite

The backend test suite covers **132 discrete test cases** with a 100% pass rate:

```bash
source .venv/bin/activate
pytest backend/tests/ -v
```

```
============================== test session starts ==============================
backend/tests/test_carestack_api.py ..................                   [ 13%]
backend/tests/test_fhir_public_server.py ........                        [ 19%]
backend/tests/test_main.py ..........                                    [ 27%]
backend/tests/test_mdin_e2e_full.py .............                        [ 37%]
backend/tests/test_mdin_suite.py .............                           [ 46%]
backend/tests/test_phase2_mdin.py ...........                            [ 55%]
backend/tests/test_phase3_terminology.py .............                   [ 65%]
backend/tests/test_phase4_cds_hooks.py ................                  [ 77%]
backend/tests/test_step8_cross_coding.py .................               [ 90%]
backend/tests/test_step9_lomn.py .............                           [100%]
======================= 132 passed, 2 warnings in 28.46s =======================
```

---

## Project Layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py                 # Configuration settings & CORS setup
│   ├── main.py                   # FastAPI entrypoint, middleware, router mounts
│   ├── data/
│   │   ├── synthetic_ehr.json    # Standard USCDI v5 reference clinical dataset
│   │   └── terminology_maps.json # ConceptMap rules (ICD/SNOMED/RxNorm & CDT-to-CPT)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── cds_hooks.py          # CDS Hooks request/response Pydantic models
│   │   ├── claims.py             # CMS-1500 & ANSI ASC X12N 837P EDI models
│   │   └── fhir.py               # HL7 FHIR R4 resource models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── billing.py            # /api/billing medical cross-coding & claims router
│   │   ├── carestack.py          # /api/carestack & /api/v1.0 CareStack router
│   │   ├── cds_services.py       # /cds-services CDS Hooks router
│   │   └── fhir.py               # /api/fhir HL7 FHIR R4 router
│   ├── schemas/                  # Pydantic schemas for request/response serialization
│   └── services/
│       ├── carestack_client.py   # Asynchronous CareStack API HTTP client
│       ├── cds_engine.py         # CDS Hooks evaluation & clinical rules engine
│       ├── concept_map.py        # FHIR ConceptMap $translate & risk synthesizer
│       ├── crosswalk_engine.py   # Administrative cross-coding & claim pre-populator
│       ├── document_generator.py # Letter of Medical Necessity clinical narrative generator
│       └── fhir_client.py        # Live HL7 FHIR R4 public test server client
├── tests/                        # 132-test automated verification suite
├── Dockerfile                    # Container definition for production deployment
├── requirements.txt              # Python runtime dependencies
└── run.py                        # Standalone Uvicorn launcher
```