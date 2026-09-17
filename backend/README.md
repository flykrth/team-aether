# Backend — Medical-Dental Interoperability Node (MDIN)

Backend microservice providing bi-directional synchronization, HL7 FHIR R4 standard endpoints, CareStack PMS integration, and Clinical Decision Support (CDS Hooks v1.0).

## Stack

- **Language / runtime**: Python 3.10+
- **Framework**: FastAPI (Asynchronous REST API)
- **ASGI Server**: Uvicorn
- **Data Validation & Schemas**: Pydantic v2 & Pydantic-Settings
- **HTTP Client**: HTTPX
- **Testing**: Pytest & FastAPI TestClient
- **Standards Implemented**: HL7 FHIR R4, CDS Hooks v1.0, CDT/SNOMED-CT cross-mapping

## Local Setup

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

The server will start at `http://localhost:8000`.
- Interactive Swagger UI: `http://localhost:8000/docs`
- ReDoc Documentation: `http://localhost:8000/redoc`

## API Endpoints Overview

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Node health status and version info |
| `GET` | `/` | Service directory and metadata |
| `GET` | `/api/carestack/status` | CareStack connectivity and sync telemetry |
| `GET` | `/api/carestack/patients` | CareStack dental patients & active treatment plans |
| `POST` | `/api/carestack/sync` | Trigger bi-directional PMS <-> EHR sync |
| `GET` | `/api/fhir/metadata` | FHIR R4 CapabilityStatement |
| `GET` | `/api/fhir/Patient` | FHIR Patient demographics |
| `GET` | `/api/fhir/Condition` | Medical conditions (Osteoporosis, Diabetes, Heart Valve) |
| `GET` | `/api/fhir/Observation` | Medical diagnostic labs (HbA1c, INR) |
| `GET` | `/api/fhir/AllergyIntolerance`| Medical drug and material allergies |
| `GET` | `/cds-services` | CDS Hooks discovery endpoint |
| `POST` | `/cds-services/med-dental-risk-evaluator` | CDS evaluation (MRONJ, bleeding, diabetic risks) |

## CORS Configuration

FastAPI is configured with `CORSMiddleware` to allow frontend clients running on:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

## Running Tests

```bash
source .venv/bin/activate
pytest backend/tests -v
```

## Project Layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py             # App settings & CORS configuration
│   ├── main.py               # FastAPI entrypoint, middleware, router mounts
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── carestack.py      # /api/carestack router
│   │   ├── fhir.py           # /api/fhir R4 router
│   │   └── cds_services.py   # /cds-services CDS Hooks router
│   └── schemas/
│       ├── __init__.py
│       ├── carestack.py      # CareStack Pydantic models
│       ├── fhir.py           # FHIR R4 resource models
│       └── cds.py            # CDS Hooks v1.0 models
├── tests/
│   ├── __init__.py
│   └── test_main.py          # Pytest suite
├── .env.example
├── requirements.txt
└── run.py                    # Standalone runnable server script
```