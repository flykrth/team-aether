"""
Turns an uploaded previous record (PDF or text file) into plain text for the deterministic extractor.

1. Text files are decoded directly.
2. PDFs with a text layer are read locally with pypdf: nothing leaves the machine.
3. Scanned PDFs (no text layer) need OCR. In order of preference:
   a. NVIDIA Nemotron Parse (nvidia/nemotron-parse on NIM), a document-parsing model. It accepts page
      images only, so pages are rendered to PNG with pypdfium2 and parsed concurrently.
   b. Gemini's document understanding, which takes the PDF directly.
   Either model only transcribes; diagnoses and drugs are still coded by the rule-based extractor
   afterwards, so a transcription error can drop a finding but cannot invent a coded one that is not
   in the lexicon.
"""

import asyncio
import base64
import io
import json
from typing import Any, Dict, List

import httpx

from ..config import settings

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
MIN_TEXT_LAYER_CHARS = 40  # below this a PDF is treated as scanned
MAX_OCR_PAGES = 8          # NIM free tier is ~40 requests/minute per model
OCR_RENDER_SCALE = 2.0     # 144 DPI: legible for OCR, ~100-400 KB per page as PNG
TEXT_TYPES = {"text/plain", "text/markdown", "application/json", "text/csv"}
TEXT_SUFFIXES = (".txt", ".md", ".json", ".csv")

_TRANSCRIBE_PROMPT = (
    "Transcribe all text in this medical document verbatim, in reading order. Output plain text only. "
    "Do not summarize, interpret, correct, translate or add anything that is not written in the document. "
    "If a word is illegible write [illegible]."
)


class DocumentError(ValueError):
    """The upload cannot be read (wrong type, empty, too large, no text and no OCR available)."""


def _pdf_text_layer(data: bytes) -> Dict[str, Any]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise DocumentError("This PDF is password-protected. Remove the password and upload it again.")
        pages = [page.extract_text() or "" for page in reader.pages]
    except DocumentError:
        raise
    except (PdfReadError, ValueError, KeyError, OSError) as exc:
        raise DocumentError(f"This file could not be read as a PDF ({exc.__class__.__name__}).") from exc
    return {"text": "\n\n".join(p.strip() for p in pages if p.strip()), "pages": len(pages)}


async def _gemini_transcribe(data: bytes, client: httpx.AsyncClient) -> str:
    response = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        json={
            "contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": "application/pdf", "data": base64.b64encode(data).decode()}},
                {"text": _TRANSCRIBE_PROMPT},
            ]}],
            "generationConfig": {"temperature": 0},
        },
    )
    if response.status_code != 200:
        raise DocumentError(f"The scanned PDF could not be transcribed (Gemini returned {response.status_code}).")
    parts = ((response.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


def _render_pages(data: bytes) -> List[bytes]:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(data)
    try:
        pages = []
        for index in range(min(len(document), MAX_OCR_PAGES)):
            buffer = io.BytesIO()
            document[index].render(scale=OCR_RENDER_SCALE).to_pil().convert("RGB").save(buffer, format="PNG", optimize=True)
            pages.append(buffer.getvalue())
        return pages
    finally:
        document.close()


def _parse_blocks(arguments: Any) -> str:
    """Nemotron Parse returns its result as tool-call arguments: a (possibly nested) JSON list of {text, type, bbox?}."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except ValueError:
            return arguments.strip()
    blocks: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if isinstance(node.get("text"), str) and node["text"].strip():
                blocks.append(node["text"].strip())
            else:
                for value in node.values():
                    if isinstance(value, (list, dict)):
                        walk(value)

    walk(arguments)
    return "\n".join(blocks)


async def _nvidia_parse_page(png: bytes, client: httpx.AsyncClient) -> str:
    response = await client.post(
        f"{settings.NVIDIA_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.NVIDIA_API_KEY}", "Accept": "application/json"},
        json={
            "model": settings.NVIDIA_PARSE_MODEL,
            "tools": [{"type": "function", "function": {"name": "markdown_no_bbox"}}],
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}},
            ]}],
            "temperature": 0.0,
            "max_tokens": 4096,
        },
    )
    if response.status_code != 200:
        raise DocumentError(f"NVIDIA Nemotron Parse returned {response.status_code}.")
    message = ((response.json().get("choices") or [{}])[0].get("message") or {})
    calls = message.get("tool_calls") or []
    if calls:
        return _parse_blocks((calls[0].get("function") or {}).get("arguments"))
    return (message.get("content") or "").strip()


async def _nvidia_transcribe(data: bytes, client: httpx.AsyncClient) -> str:
    pages = await asyncio.to_thread(_render_pages, data)
    texts = await asyncio.gather(*(_nvidia_parse_page(png, client) for png in pages))
    return "\n\n".join(t for t in texts if t)


def ocr_providers() -> List[str]:
    """OCR engines available for scanned PDFs, in the order they are tried."""
    wanted = (settings.DOCUMENT_OCR_PROVIDER or "auto").lower()
    available = [name for name, key in (("nvidia", settings.NVIDIA_API_KEY), ("gemini", settings.GEMINI_API_KEY)) if key]
    return available if wanted == "auto" else [name for name in available if name == wanted]


async def _ocr(data: bytes, client: httpx.AsyncClient) -> Dict[str, str]:
    engines = {"nvidia": (_nvidia_transcribe, "nvidia-nemotron-parse"), "gemini": (_gemini_transcribe, "gemini-transcription")}
    providers = ocr_providers()
    if not providers:
        raise DocumentError(
            "This PDF is a scan with no text layer. Add NVIDIA_API_KEY (Nemotron Parse) or GEMINI_API_KEY to read "
            "scanned documents, or paste the text instead."
        )
    last_error: Exception = DocumentError("The scanned PDF could not be read.")
    for provider in providers:  # a failing engine falls through to the next one
        transcribe, method = engines[provider]
        try:
            text = await transcribe(data, client)
            if text.strip():
                return {"text": text, "method": method}
            last_error = DocumentError("No readable text was found in this scanned PDF.")
        except (DocumentError, httpx.HTTPError, ValueError, KeyError) as exc:
            last_error = exc if isinstance(exc, DocumentError) else DocumentError(
                f"The scanned PDF could not be transcribed ({exc.__class__.__name__}).")
    raise last_error


async def document_to_text(data: bytes, filename: str, content_type: str, client: httpx.AsyncClient = None) -> Dict[str, Any]:
    """Returns {text, method: "text-file"|"pdf-text-layer"|"nvidia-nemotron-parse"|"gemini-transcription", pages, truncated}."""
    if not data:
        raise DocumentError("The file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise DocumentError("The file is larger than 10 MB.")

    name = (filename or "").lower()
    kind = (content_type or "").split(";")[0].strip().lower()
    is_pdf = data[:5] == b"%PDF-" or kind == "application/pdf" or name.endswith(".pdf")

    if is_pdf:
        layer = _pdf_text_layer(data)
        text, method, pages = layer["text"], "pdf-text-layer", layer["pages"]
        if len(text) < MIN_TEXT_LAYER_CHARS:
            owns_client = client is None
            client = client or httpx.AsyncClient(timeout=90.0)
            try:
                result = await _ocr(data, client)
                text, method = result["text"], result["method"]
            finally:
                if owns_client:
                    await client.aclose()
    elif kind in TEXT_TYPES or name.endswith(TEXT_SUFFIXES):
        text, method, pages = data.decode("utf-8", errors="replace"), "text-file", None
    else:
        raise DocumentError("Unsupported file type. Upload a PDF, .txt, .md, .json or .csv file.")

    text = text.replace("\x00", "").strip()
    if not text:
        raise DocumentError("No readable text was found in this file.")
    return {"text": text[:MAX_TEXT_CHARS], "method": method, "pages": pages, "truncated": len(text) > MAX_TEXT_CHARS}
