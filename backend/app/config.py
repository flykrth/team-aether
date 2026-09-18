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

        # FHIR R4 Public Test Server Integration (HL7 Directory)
        # Reference: https://confluence.hl7.org/spaces/FHIR/pages/35718859/Public+Test+Servers
        FHIR_SERVER_URL: str = "https://hapi.fhir.org/baseR4"
        FHIR_FALLBACK_SERVER_URL: str = "https://lforms-fhir.nlm.nih.gov/baseR4"
        FHIR_TIMEOUT_SECONDS: float = 8.0
        FHIR_USE_CACHE_FALLBACK: bool = True

        # MAO Assistant (LLM chat agent). Real secrets: set in .env only, never commit.
        # One MASTER provider runs the tool-calling loop (first configured of gemini, groq,
        # nvidia unless ASSISTANT_MASTER_PROVIDER forces one); the others serve as parallel
        # specialists for consult_specialists.
        GEMINI_API_KEY: str = ""
        GEMINI_MODEL: str = "gemini-3.8-flash"
        # Scanned-PDF OCR: auto = NVIDIA Nemotron Parse when NVIDIA_API_KEY is set, else Gemini
        DOCUMENT_OCR_PROVIDER: str = "auto"
        NVIDIA_PARSE_MODEL: str = "nvidia/nemotron-parse"
        # Coverage Recovery RAG: auto = Gemini embeddings when GEMINI_API_KEY is set, else NVIDIA, else lexical search only
        EMBEDDING_PROVIDER: str = "auto"
        GEMINI_EMBED_MODEL: str = "gemini-embedding-2"
        NVIDIA_EMBED_MODEL: str = "nvidia/llama-nemotron-embed-1b-v2"
        GROQ_API_KEY: str = ""
        GROQ_MODEL: str = "openai/gpt-oss-120b"
        GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
        NVIDIA_API_KEY: str = ""
        NVIDIA_MODEL: str = "nvidia/nemotron-3-super-120b-a12b"
        NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
        ASSISTANT_MASTER_PROVIDER: str = ""  # "", gemini, groq or nvidia

        # Voice input (speech to text). auto = NVIDIA when NVIDIA_STT_URL is set, else Groq Whisper.
        # NVIDIA's hosted ASR is gRPC-only; NVIDIA_STT_URL points at a self-hosted Speech NIM
        # (http://host:9000), which is the only NVIDIA ASR route that speaks plain HTTP.
        STT_PROVIDER: str = "auto"  # auto | nvidia | groq
        GROQ_STT_MODEL: str = "whisper-large-v3-turbo"
        NVIDIA_STT_MODEL: str = "nvidia/nemotron-asr-streaming"
        NVIDIA_STT_URL: str = ""

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
        FHIR_FALLBACK_SERVER_URL: str = os.getenv("FHIR_FALLBACK_SERVER_URL", "https://lforms-fhir.nlm.nih.gov/baseR4")
        FHIR_TIMEOUT_SECONDS: float = float(os.getenv("FHIR_TIMEOUT_SECONDS", "8.0"))
        FHIR_USE_CACHE_FALLBACK: bool = os.getenv("FHIR_USE_CACHE_FALLBACK", "True").lower() in ("1", "true", "yes")

        GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        DOCUMENT_OCR_PROVIDER: str = os.getenv("DOCUMENT_OCR_PROVIDER", "auto")
        NVIDIA_PARSE_MODEL: str = os.getenv("NVIDIA_PARSE_MODEL", "nvidia/nemotron-parse")
        EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "auto")
        GEMINI_EMBED_MODEL: str = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-2")
        NVIDIA_EMBED_MODEL: str = os.getenv("NVIDIA_EMBED_MODEL", "nvidia/llama-nemotron-embed-1b-v2")
        GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
        NVIDIA_MODEL: str = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
        NVIDIA_BASE_URL: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        ASSISTANT_MASTER_PROVIDER: str = os.getenv("ASSISTANT_MASTER_PROVIDER", "")
        STT_PROVIDER: str = os.getenv("STT_PROVIDER", "auto")
        GROQ_STT_MODEL: str = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo")
        NVIDIA_STT_MODEL: str = os.getenv("NVIDIA_STT_MODEL", "nvidia/nemotron-asr-streaming")
        NVIDIA_STT_URL: str = os.getenv("NVIDIA_STT_URL", "")
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
