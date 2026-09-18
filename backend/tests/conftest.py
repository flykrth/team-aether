"""
Suite-wide guard: backend/.env holds real provider keys on a developer machine, and several code
paths call an LLM when a key is present. Tests must never reach a real provider, so every test starts
with no keys; a test that needs one sets a fake with monkeypatch and mocks the transport.
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _no_real_provider_keys(monkeypatch):
    for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY",
                 # a developer's real CareStack account must never be the target of a test either
                 "CARESTACK_BASE_URL", "CARESTACK_VENDOR_KEY", "CARESTACK_ACCOUNT_KEY", "CARESTACK_ACCOUNT_ID"):
        monkeypatch.setattr(settings, name, "", raising=False)
    monkeypatch.setattr(settings, "USE_LIVE_CARESTACK", False, raising=False)


@pytest.fixture(autouse=True)
def _no_retry_waits(monkeypatch):
    from app.services.assistant import gemini
    monkeypatch.setattr(gemini, "RETRY_DELAYS", (0, 0))
