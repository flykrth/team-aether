"""
Configuration settings for the Medical-Dental Interoperability Node (MDIN).
Supports loading from environment variables or .env file with safe defaults.
"""

from functools import lru_cache
from typing import List
import os

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import Field

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=os.getenv("ENV_FILE", ".env"),
            env_file_encoding="utf-8",
            extra="ignore",
        )

        PROJECT_NAME: str = "Medical-Dental Interoperability Node (MDIN)"
        VERSION: str = "0.1.0"
        DESCRIPTION: str = (
            "Bi-directional bridge and Clinical Decision Support engine connecting "
            "CareStack Dental Practice Management with Medical EHRs via FHIR R4 and CDS Hooks."
        )
        DEBUG: bool = True
        HOST: str = "0.0.0.0"
        PORT: int = 8000

        # Frontend access origins (ports 3000 & 5173 supported out of the box)
        CORS_ORIGINS: List[str] = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

        # CareStack Web API V1 Authentication & Integration
        CARESTACK_BASE_URL: str = "https://brightsmiles.carestack.com"
        CARESTACK_VENDOR_KEY: str = "carestack-vendor-key-sec-99210"
        CARESTACK_ACCOUNT_KEY: str = "carestack-account-key-sec-88412"
        CARESTACK_ACCOUNT_ID: str = "ACCT-101"
        CARESTACK_API_KEY: str = "mock-carestack-api-key"
        CARESTACK_PRACTICE_ID: str = "PRACTICE-101"

        # FHIR R4 Integration
        FHIR_SERVER_URL: str = "https://hapi.fhir.org/baseR4"

        # CDS Hooks Service
        CDS_DISCOVERY_PATH: str = "/cds-services"

except ImportError:
    from pydantic import BaseModel, Field

    class Settings(BaseModel):
        PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Medical-Dental Interoperability Node (MDIN)")
        VERSION: str = os.getenv("VERSION", "0.1.0")
        DESCRIPTION: str = os.getenv(
            "DESCRIPTION",
            "Bi-directional bridge and Clinical Decision Support engine connecting "
            "CareStack Dental Practice Management with Medical EHRs via FHIR R4 and CDS Hooks.",
        )
        DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes")
        HOST: str = os.getenv("HOST", "0.0.0.0")
        PORT: int = int(os.getenv("PORT", "8000"))

        CORS_ORIGINS: List[str] = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

        CARESTACK_BASE_URL: str = os.getenv("CARESTACK_BASE_URL", "https://brightsmiles.carestack.com")
        CARESTACK_VENDOR_KEY: str = os.getenv("CARESTACK_VENDOR_KEY", "carestack-vendor-key-sec-99210")
        CARESTACK_ACCOUNT_KEY: str = os.getenv("CARESTACK_ACCOUNT_KEY", "carestack-account-key-sec-88412")
        CARESTACK_ACCOUNT_ID: str = os.getenv("CARESTACK_ACCOUNT_ID", "ACCT-101")
        CARESTACK_API_KEY: str = os.getenv("CARESTACK_API_KEY", "mock-carestack-api-key")
        CARESTACK_PRACTICE_ID: str = os.getenv("CARESTACK_PRACTICE_ID", "PRACTICE-101")

        FHIR_SERVER_URL: str = os.getenv("FHIR_SERVER_URL", "https://hapi.fhir.org/baseR4")
        CDS_DISCOVERY_PATH: str = os.getenv("CDS_DISCOVERY_PATH", "/cds-services")


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()


settings = get_settings()
