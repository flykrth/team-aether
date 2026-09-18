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

        # --- Live CareStack account (OUTBOUND credentials) ---
        # Real secrets. Deliberately empty by default so nothing ships in source:
        # supply all four via environment and set USE_LIVE_CARESTACK=true to route
        # CareStack traffic at a real account. Left unset, MDIN serves the bundled
        # simulator instead.
        USE_LIVE_CARESTACK: bool = False
        CARESTACK_BASE_URL: str = ""
        CARESTACK_VENDOR_KEY: str = ""
        CARESTACK_ACCOUNT_KEY: str = ""
        CARESTACK_ACCOUNT_ID: str = ""

        # --- Bundled CareStack simulator (INBOUND credentials) ---
        # Not secrets. These gate the in-memory simulator shipped for demos and
        # tests, which holds only synthetic patient data.
        SIMULATOR_VENDOR_KEY: str = "demo-vendor-key"
        SIMULATOR_ACCOUNT_KEY: str = "demo-account-key"
        SIMULATOR_ACCOUNT_ID: str = "demo-account-001"

        # FHIR R4 Integration
        FHIR_SERVER_URL: str = "https://hapi.fhir.org/baseR4"

        # CDS Hooks Service
        CDS_DISCOVERY_PATH: str = "/cds-services"

        @property
        def carestack_live_configured(self) -> bool:
            """True when a real CareStack account is fully configured and enabled."""
            return bool(
                self.USE_LIVE_CARESTACK
                and self.CARESTACK_BASE_URL
                and self.CARESTACK_VENDOR_KEY
                and self.CARESTACK_ACCOUNT_KEY
                and self.CARESTACK_ACCOUNT_ID
            )

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

        # Live CareStack account (OUTBOUND) - real secrets, environment only.
        USE_LIVE_CARESTACK: bool = os.getenv("USE_LIVE_CARESTACK", "False").lower() in ("1", "true", "yes")
        CARESTACK_BASE_URL: str = os.getenv("CARESTACK_BASE_URL", "")
        CARESTACK_VENDOR_KEY: str = os.getenv("CARESTACK_VENDOR_KEY", "")
        CARESTACK_ACCOUNT_KEY: str = os.getenv("CARESTACK_ACCOUNT_KEY", "")
        CARESTACK_ACCOUNT_ID: str = os.getenv("CARESTACK_ACCOUNT_ID", "")

        # Bundled simulator (INBOUND) - demo credentials, not secrets.
        SIMULATOR_VENDOR_KEY: str = os.getenv("SIMULATOR_VENDOR_KEY", "demo-vendor-key")
        SIMULATOR_ACCOUNT_KEY: str = os.getenv("SIMULATOR_ACCOUNT_KEY", "demo-account-key")
        SIMULATOR_ACCOUNT_ID: str = os.getenv("SIMULATOR_ACCOUNT_ID", "demo-account-001")

        FHIR_SERVER_URL: str = os.getenv("FHIR_SERVER_URL", "https://hapi.fhir.org/baseR4")
        CDS_DISCOVERY_PATH: str = os.getenv("CDS_DISCOVERY_PATH", "/cds-services")

        @property
        def carestack_live_configured(self) -> bool:
            """True when a real CareStack account is fully configured and enabled."""
            return bool(
                self.USE_LIVE_CARESTACK
                and self.CARESTACK_BASE_URL
                and self.CARESTACK_VENDOR_KEY
                and self.CARESTACK_ACCOUNT_KEY
                and self.CARESTACK_ACCOUNT_ID
            )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()


settings = get_settings()
