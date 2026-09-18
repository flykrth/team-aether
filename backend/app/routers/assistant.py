"""
API Router for the MAO Assistant: one master tool-calling agent (Gemini, Groq or NVIDIA NIM) with
parallel specialist models. It answers questions about patients and the application, takes actions
through the same services the UI uses, and transcribes voice input.
"""

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request, status
from starlette.datastructures import UploadFile
from pydantic import BaseModel, Field

from ..services.assistant import AssistantError, AssistantNotConfigured, SpeechNotConfigured, chat
from ..services.assistant import providers, speech
from ..services.assistant.tools import ACTION_TOOLS, TOOL_DECLARATIONS

router = APIRouter()


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatAttachment(BaseModel):
    filename: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1, max_length=200_000)


class ChatRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1, description="Conversation so far, ending with the user's message")
    patient_id: Optional[str] = Field(None, description="Patient currently open in the app, for 'this patient' questions")
    attachments: List[ChatAttachment] = Field(default_factory=list, max_length=3, description="Documents attached in this conversation (text already extracted by /api/records/extract-file)")


@router.get("/status", summary="Assistant Status")
async def assistant_status() -> Dict[str, Any]:
    master = providers.select_master()
    return {
        "configured": master is not None,
        "provider": master,
        "model": providers.provider_model(master) if master else None,
        "providers": {
            name: {"configured": providers.is_configured(name), "model": providers.provider_model(name)}
            for name in providers.PROVIDER_ORDER
        },
        "speech": speech.speech_status(),
        "tools": [{"name": d["name"], "is_action": d["name"] in ACTION_TOOLS} for d in TOOL_DECLARATIONS],
    }


@router.post("/chat", summary="Chat with the MAO Assistant")
async def assistant_chat(request: ChatRequest) -> Dict[str, Any]:
    try:
        return await chat([m.model_dump() for m in request.messages[-30:]], request.patient_id,
                          attachments=[a.model_dump() for a in request.attachments])
    except AssistantNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except AssistantError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


_TRANSCRIBE_BODY = {"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
    "type": "object", "required": ["file"],
    "properties": {"file": {"type": "string", "format": "binary", "description": "audio/webm, audio/wav, audio/mp4 or audio/ogg"}},
}}}}}


@router.post("/transcribe", summary="Transcribe a voice clip", openapi_extra=_TRANSCRIBE_BODY)
async def assistant_transcribe(request: Request) -> Dict[str, Any]:
    # Takes the raw Request so an oversized upload is refused from its Content-Length, BEFORE the
    # multipart body is received and spooled to disk (a declared UploadFile parameter is parsed first).
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > speech.MAX_AUDIO_BYTES + 64 * 1024:
        raise HTTPException(status_code=413, detail="Audio clip is larger than 15 MB.")
    try:
        form = await request.form(max_files=1, max_fields=4)
    except Exception:
        raise HTTPException(status_code=422, detail="Send the clip as multipart/form-data in a field named 'file'.")
    file = form.get("file")
    if not isinstance(file, UploadFile):
        raise HTTPException(status_code=422, detail="Send the clip as multipart/form-data in a field named 'file'.")
    content_type = speech.base_content_type(file.content_type)
    if content_type not in speech.ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415,
                            detail=f"Unsupported audio type '{content_type or 'unknown'}'. Send webm, wav, mp4 or ogg audio.")
    audio = await file.read(speech.MAX_AUDIO_BYTES + 1)
    if len(audio) > speech.MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio clip is larger than 15 MB.")
    if not audio:
        raise HTTPException(status_code=422, detail="Audio clip is empty.")
    try:
        return await speech.transcribe(audio, content_type)
    except SpeechNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except AssistantError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
