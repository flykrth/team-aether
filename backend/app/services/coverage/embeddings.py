"""
Embeddings for the policy RAG index, through a hosted API (no local model download):
Gemini `gemini-embedding-2`, or NVIDIA `llama-nemotron-embed-1b-v2` on NIM. With neither key the
retriever falls back to lexical search, and says so.
"""

import asyncio
from typing import List, Optional

import httpx

from ...config import settings

DIMENSIONS = 768
BATCH = 80


def provider() -> Optional[str]:
    wanted = (settings.EMBEDDING_PROVIDER or "auto").lower()
    available = [name for name, key in (("gemini", settings.GEMINI_API_KEY), ("nvidia", settings.NVIDIA_API_KEY)) if key]
    if wanted != "auto":
        return wanted if wanted in available else None
    return available[0] if available else None


def model_name(name: Optional[str] = None) -> str:
    name = name or provider()
    return {"gemini": settings.GEMINI_EMBED_MODEL, "nvidia": settings.NVIDIA_EMBED_MODEL}.get(name or "", "")


class RateLimited(RuntimeError):
    def __init__(self, retry_after: float):
        super().__init__(f"embedding quota reached; retry in {retry_after:.0f}s")
        self.retry_after = retry_after


async def _post(client: httpx.AsyncClient, url: str, headers: dict, body: dict) -> dict:
    response = await client.post(url, headers=headers, json=body, timeout=90.0)
    if response.status_code == 429:
        # Free tiers meter embeddings per minute (Gemini: 100 items/min). The API says how long to wait.
        delay = 60.0
        try:
            for detail in response.json().get("error", {}).get("details", []):
                if "retryDelay" in detail:
                    delay = float(str(detail["retryDelay"]).rstrip("s")) + 1.0
        except ValueError:
            pass
        raise RateLimited(delay)
    if response.status_code != 200:
        raise RuntimeError(f"embedding API returned {response.status_code}")
    return response.json()


async def _gemini(texts: List[str], is_query: bool, client: httpx.AsyncClient) -> List[List[float]]:
    model = settings.GEMINI_EMBED_MODEL
    # gemini-embedding-2 takes the task as an instruction in the text rather than a task_type field
    prefix = "task: search result | query: " if is_query else "title: payer medical policy | text: "
    data = await _post(
        client, f"https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents",
        {"x-goog-api-key": settings.GEMINI_API_KEY},
        {"requests": [{"model": f"models/{model}", "content": {"parts": [{"text": prefix + t[:7000]}]},
                       "output_dimensionality": DIMENSIONS} for t in texts]},
    )
    return [e["values"] for e in data["embeddings"]]


async def _nvidia(texts: List[str], is_query: bool, client: httpx.AsyncClient) -> List[List[float]]:
    data = await _post(
        client, f"{settings.NVIDIA_BASE_URL.rstrip('/')}/embeddings",
        {"Authorization": f"Bearer {settings.NVIDIA_API_KEY}"},
        {"model": settings.NVIDIA_EMBED_MODEL, "input": [t[:7000] for t in texts],
         "input_type": "query" if is_query else "passage", "truncate": "END", "dimensions": DIMENSIONS},
    )
    return [row["embedding"] for row in sorted(data["data"], key=lambda r: r["index"])]


async def embed(texts: List[str], is_query: bool = False, client: Optional[httpx.AsyncClient] = None) -> List[List[float]]:
    name = provider()
    if not name:
        raise RuntimeError("no embedding provider configured")
    call = _gemini if name == "gemini" else _nvidia
    owns = client is None
    client = client or httpx.AsyncClient()
    try:
        vectors: List[List[float]] = []
        for start in range(0, len(texts), BATCH):
            vectors.extend(await call(texts[start:start + BATCH], is_query, client))
        return vectors
    finally:
        if owns:
            await client.aclose()
