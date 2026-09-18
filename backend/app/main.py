"""
FastAPI application entrypoint for the Medical-Dental Interoperability Node (MDIN).
Configures CORS for frontend access (ports 3000/5173) and mounts CareStack, FHIR, and CDS Hooks routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

from .config import settings
from .routers import carestack_router, fhir_router, cds_router, billing_router, clearance_router, agents_router, assistant_router, records_router, risk_router, coverage_router, visits_router
from .services.carestack_client import describe_integration_mode
from .services.agent_supervisor import agent_supervisor


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Run the MAO supervisor continuously in the background for the life of the process
    await agent_supervisor.start()
    yield
    await agent_supervisor.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Enable CORS for frontend clients (supporting ports 3000 and 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the required interoperability routers
app.include_router(carestack_router, prefix="/api/carestack", tags=["CareStack"])
# Same simulator, mounted again under the CareStack-V1-shaped path so integration
# clients can be pointed at it unchanged. Serves synthetic data, not a real account.
app.include_router(carestack_router, prefix="/api/v1.0", tags=["CareStack Web API V1 (Simulator)"])
app.include_router(fhir_router, prefix="/api/fhir", tags=["FHIR R4"])
app.include_router(cds_router, prefix="/cds-services", tags=["CDS Hooks"])
app.include_router(billing_router, prefix="/api/billing", tags=["Medical Cross-Coding & Billing"])
app.include_router(clearance_router, prefix="/api/clearance", tags=["Medical Clearance Passport"])
app.include_router(agents_router, prefix="/api/agents", tags=["Multi-Agent Orchestrator"])
app.include_router(assistant_router, prefix="/api/assistant", tags=["MAO Assistant"])
app.include_router(risk_router, prefix="/api/risk", tags=["Risk Check"])
app.include_router(coverage_router, prefix="/api/coverage", tags=["Dental Coverage Recovery"])
app.include_router(visits_router, prefix="/api/visits", tags=["Visit Workflow"])
app.include_router(records_router, prefix="/api/records", tags=["Patient Records"])


@app.get("/", tags=["System"])
async def root():
    """Root endpoint providing service metadata and discovery links."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "carestack_integration": describe_integration_mode(),
        "fhir_server": settings.FHIR_SERVER_URL,
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "carestack": "/api/carestack/status",
            "carestack_connectivity": "/api/carestack/connectivity",
            "carestack_v1": "/api/v1.0/patients",
            "fhir": "/api/fhir/metadata",
            "fhir_server_status": "/api/fhir/server-status",
            "cds_discovery": "/cds-services",
            "billing": "/api/billing/crosswalk-rules",
            "evaluate_claim": "/api/billing/evaluate-claim",
            "clearance_dispatch": "/api/clearance/dispatch",
            "clearance_patient": "/api/clearance/patient/{patient_id}",
            "agents_status": "/api/agents/status",
            "agents_stream": "/api/agents/stream/{patient_id}",
            "assistant_chat": "/api/assistant/chat",
            "records_patients": "/api/records/patients",
            "records_extract": "/api/records/extract",
            "records_import": "/api/records/patients/{patient_id}/import",
        },
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for container orchestrators and frontend pinging."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
