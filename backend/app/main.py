"""
FastAPI application entrypoint for the Medical-Dental Interoperability Node (MDIN).
Configures CORS for frontend access (ports 3000/5173) and mounts CareStack, FHIR, and CDS Hooks routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

from .config import settings
from .routers import carestack_router, fhir_router, cds_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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
app.include_router(fhir_router, prefix="/api/fhir", tags=["FHIR R4"])
app.include_router(cds_router, prefix="/cds-services", tags=["CDS Hooks"])


@app.get("/", tags=["System"])
async def root():
    """Root endpoint providing service metadata and discovery links."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "carestack": "/api/carestack/status",
            "fhir": "/api/fhir/metadata",
            "cds_discovery": "/cds-services",
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
