"""
Gemini function-calling loop for the MAO Assistant.

Talks to the Gemini REST API directly over httpx (no SDK dependency). Model turns are appended to
the conversation verbatim, which preserves the thought signatures Gemini 3 models require when a
function call is answered.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx

from ...config import settings
from .errors import AssistantError, AssistantNotConfigured
from .prompts import SYSTEM_PROMPT, build_system_prompt  # noqa: F401  (SYSTEM_PROMPT re-exported)
from .tools import ACTION_TOOLS, TOOL_DECLARATIONS, execute_tool

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_TOOL_ROUNDS = 8
RETRY_DELAYS = (1.0, 2.5)  # seconds before the 2nd and 3rd attempt on a transient 429/500/503
MAX_TOOL_RESULT_CHARS = 12000


def is_configured() -> bool:
    return bool(settings.GEMINI_API_KEY)


def _to_contents(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    contents = []
    for message in messages:
        text = (message.get("content") or "").strip()
        if text:
            contents.append({"role": "model" if message.get("role") == "assistant" else "user", "parts": [{"text": text}]})
    return contents


async def _generate(client: httpx.AsyncClient, contents: List[Dict[str, Any]], system: str,
                    with_tools: bool = True) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.2},
    }
    if with_tools:
        body["tools"] = [{"functionDeclarations": TOOL_DECLARATIONS}]
    # 503 "high demand" and 429 are usually gone within a second or two. The request is a pure function of the
    # conversation (no tool has run for it yet), so repeating it is safe.
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            response = await client.post(
                GEMINI_URL.format(model=settings.GEMINI_MODEL),
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                json=body,
            )
        except httpx.HTTPError as exc:
            raise AssistantError(f"Could not reach the Gemini API: {exc.__class__.__name__}") from exc
        if response.status_code not in (429, 500, 503) or attempt == len(RETRY_DELAYS):
            break
        await asyncio.sleep(RETRY_DELAYS[attempt])

    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except ValueError:
            detail = ""
        raise AssistantError(f"Gemini API returned {response.status_code}. {detail}".strip())
    return response.json()


async def complete(client: httpx.AsyncClient, system: str, user: str) -> str:
    """One tool-less completion, used when Gemini serves as a specialist."""
    data = await _generate(client, [{"role": "user", "parts": [{"text": user}]}], system, with_tools=False)
    parts = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


async def chat(
    messages: List[Dict[str, str]],
    focus_patient_id: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """
    Runs one assistant turn: the model may call tools for several rounds before answering.
    Returns {"reply", "actions": [{tool, args, is_action, ok}], "model"}.
    """
    if not is_configured():
        raise AssistantNotConfigured("GEMINI_API_KEY is not set. Add it to backend/.env and restart the backend.")

    contents = _to_contents(messages)
    if not contents or contents[-1]["role"] != "user":
        raise AssistantError("The conversation must end with a user message.")

    system = build_system_prompt(focus_patient_id)

    actions: List[Dict[str, Any]] = []
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=60.0)
    try:
        for _ in range(MAX_TOOL_ROUNDS):
            data = await _generate(client, contents, system)
            candidate = (data.get("candidates") or [{}])[0]
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            calls = [p["functionCall"] for p in parts if "functionCall" in p]

            if not calls:
                reply = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
                if not reply:
                    reason = candidate.get("finishReason") or (data.get("promptFeedback") or {}).get("blockReason")
                    reply = f"I couldn't produce an answer for that ({reason or 'empty response'}). Try rephrasing."
                return {"reply": reply, "actions": actions, "model": settings.GEMINI_MODEL}

            contents.append({"role": "model", "parts": parts})  # verbatim: keeps thought signatures
            responses = []
            for call in calls:
                name, args = call.get("name", ""), dict(call.get("args") or {})
                result = await execute_tool(name, args)
                actions.append({
                    "tool": name,
                    "args": args,
                    "is_action": name in ACTION_TOOLS,
                    "ok": "error" not in result and result.get("ok", True) is not False,
                })
                payload = json.dumps(result, default=str)
                if len(payload) > MAX_TOOL_RESULT_CHARS:
                    result = {"truncated": True, "data": payload[:MAX_TOOL_RESULT_CHARS]}
                responses.append({"functionResponse": {"name": name, "response": result}})
            contents.append({"role": "user", "parts": responses})

        return {
            "reply": "I ran out of tool steps before finishing. Here is what I did so far; ask me to continue.",
            "actions": actions,
            "model": settings.GEMINI_MODEL,
        }
    finally:
        if owns_client:
            await client.aclose()
