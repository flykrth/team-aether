"""
Speech to text for the assistant's voice input.

Groq Whisper is the working hosted route: plain HTTPS multipart, and it accepts the browser's
MediaRecorder output (audio/webm;codecs=opus) without transcoding.

NVIDIA: the hosted Nemotron / Parakeet ASR functions on build.nvidia.com are gRPC-only (Riva
protocol on grpc.nvcf.nvidia.com:443 with a per-model function-id). httpx cannot speak gRPC and
this project takes no new dependencies, so the hosted route is NOT implemented here (see
_transcribe_nvidia_hosted). What is implemented is the documented plain-HTTP route of a
self-hosted Speech NIM container (POST {NVIDIA_STT_URL}/v1/audio/transcriptions), enabled only
when NVIDIA_STT_URL is set. That route documents WAV / Ogg-Opus / FLAC input, so in auto mode a
rejected browser webm clip falls through to Groq.
"""

import time
from typing import Any, Dict, List, Optional

import httpx

from ...config import settings
from . import providers
from .errors import AssistantError, SpeechNotConfigured

MAX_AUDIO_BYTES = 15 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/wav", "audio/x-wav", "audio/wave", "audio/mp4", "audio/ogg",
                       "video/webm"}  # some browsers label an audio-only MediaRecorder blob video/webm
_EXTENSIONS = {"audio/webm": "webm", "video/webm": "webm", "audio/wav": "wav", "audio/x-wav": "wav",
               "audio/wave": "wav", "audio/mp4": "m4a", "audio/ogg": "ogg"}

# Whisper's prompt biases spelling toward the vocabulary of this app (max 224 tokens).
_VOCABULARY_PROMPT = (
    "Dental practice voice command. Terms: CareStack, CDT code D7210, surgical extraction, medical clearance, "
    "warfarin, apixaban, clopidogrel, aspirin, metformin, atrial fibrillation, coronary stent, hypertension, "
    "type 2 diabetes, INR, HbA1c, penicillin allergy, ICD-10, CMS-1500."
)


def base_content_type(content_type: Optional[str]) -> str:
    """'audio/webm;codecs=opus' -> 'audio/webm'."""
    return (content_type or "").split(";")[0].strip().lower()


def _nvidia_ready() -> bool:
    return bool(settings.NVIDIA_STT_URL)


def _groq_ready() -> bool:
    return bool(settings.GROQ_API_KEY)


def speech_providers() -> List[str]:
    """Usable speech providers in the order they are tried."""
    mode = (settings.STT_PROVIDER or "auto").strip().lower()
    ready = [name for name, ok in (("nvidia", _nvidia_ready()), ("groq", _groq_ready())) if ok]
    return ready if mode == "auto" else [p for p in ready if p == mode]


SELF_HOSTED_NIM_LABEL = "self-hosted NVIDIA Speech NIM"


def _model(provider: str) -> str:
    # The self-hosted NIM route sends no model id (the container serves whatever it was started with), so
    # reporting NVIDIA_STT_MODEL here would claim the hosted Nemotron ASR, which is not wired (gRPC-only).
    return SELF_HOSTED_NIM_LABEL if provider == "nvidia" else settings.GROQ_STT_MODEL


def speech_status() -> Dict[str, Any]:
    available = speech_providers()
    provider = available[0] if available else None
    return {"configured": bool(available), "provider": provider, "model": _model(provider) if provider else None}


async def _post_audio(client: httpx.AsyncClient, label: str, url: str, key: str, files, data) -> str:
    try:
        response = await client.post(url, headers={"Authorization": f"Bearer {key}"} if key else {}, files=files, data=data)
    except httpx.HTTPError as exc:
        raise AssistantError(f"Could not reach {label}: {exc.__class__.__name__}") from exc
    if response.status_code != 200:
        try:
            error = response.json().get("error", "")
            detail = error.get("message", "") if isinstance(error, dict) else str(error)
        except ValueError:
            detail = ""
        raise AssistantError(f"{label} returned {response.status_code}. {detail}".strip())
    try:
        return (response.json().get("text") or "").strip()
    except ValueError as exc:
        raise AssistantError(f"{label} returned an unexpected response.") from exc


async def _transcribe_groq(client: httpx.AsyncClient, audio: bytes, filename: str, content_type: str) -> str:
    return await _post_audio(
        client, "Groq speech-to-text", f"{settings.GROQ_BASE_URL.rstrip('/')}/audio/transcriptions", settings.GROQ_API_KEY,
        files={"file": (filename, audio, content_type)},  # httpx sets the multipart boundary itself
        data={"model": settings.GROQ_STT_MODEL, "language": "en", "response_format": "json",
              "temperature": "0", "prompt": _VOCABULARY_PROMPT},
    )


async def _transcribe_nvidia_nim(client: httpx.AsyncClient, audio: bytes, filename: str, content_type: str) -> str:
    """Self-hosted Speech NIM over plain HTTP. The API key is optional there; sent when present."""
    return await _post_audio(
        client, "NVIDIA Speech NIM", f"{settings.NVIDIA_STT_URL.rstrip('/')}/v1/audio/transcriptions", settings.NVIDIA_API_KEY,
        files={"file": (filename, audio, content_type)},
        data={"language": "en-US"},
    )


async def _transcribe_nvidia_hosted(*_args, **_kwargs) -> str:
    """UNIMPLEMENTED on purpose: hosted NVIDIA ASR needs the Riva gRPC client (nvidia-riva-client) plus a
    per-model function-id and server-side webm -> PCM transcoding. Wire it here if that dependency is allowed."""
    raise NotImplementedError("Hosted NVIDIA ASR is gRPC-only")


async def transcribe(audio: bytes, content_type: str = "audio/webm", client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    """Returns {text, provider, model, duration_ms}. Tries each usable provider in order."""
    available = speech_providers()
    if not available:
        mode = (settings.STT_PROVIDER or "auto").strip().lower()
        if mode == "nvidia":
            raise SpeechNotConfigured(
                "NVIDIA speech-to-text needs NVIDIA_STT_URL (a self-hosted Speech NIM): NVIDIA's hosted ASR is "
                "gRPC-only. Set it, or use STT_PROVIDER=auto with GROQ_API_KEY.")
        raise SpeechNotConfigured(
            "No speech-to-text provider is configured. Set GROQ_API_KEY (Groq Whisper) or NVIDIA_STT_URL in "
            "backend/.env; until then the browser's built-in speech recognition is used.")

    content_type = base_content_type(content_type) or "audio/webm"
    filename = f"voice.{_EXTENSIONS.get(content_type, 'webm')}"  # format detection keys off the extension
    owns_client = client is None
    client = client or providers.new_client()
    started = time.perf_counter()
    try:
        error: Optional[AssistantError] = None
        for provider in available:
            call = _transcribe_nvidia_nim if provider == "nvidia" else _transcribe_groq
            try:
                text = await call(client, audio, filename, content_type)
            except AssistantError as exc:
                error = error or exc
                continue
            return {"text": text, "provider": provider, "model": _model(provider),
                    "duration_ms": int((time.perf_counter() - started) * 1000)}
        raise error
    finally:
        if owns_client:
            await client.aclose()
