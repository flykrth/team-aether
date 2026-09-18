"""
Per-turn context shared between the orchestrator and the tools, carried in contextvars so the
provider loops (gemini.py, providers.py) do not need to know about widgets or specialists.
"""

from contextvars import ContextVar
from typing import Any, Dict, List, Optional

import httpx

# Every tool call of the current turn as {tool, args, result}; the orchestrator builds widgets from it.
turn_recorder: ContextVar[Optional[List[Dict[str, Any]]]] = ContextVar("assistant_turn_recorder", default=None)
# HTTP client of the current turn, so consult_specialists is mockable the same way chat(client=...) is.
turn_client: ContextVar[Optional[httpx.AsyncClient]] = ContextVar("assistant_turn_client", default=None)
# Provider running the master loop, so specialists fan out to the *other* providers.
turn_master: ContextVar[Optional[str]] = ContextVar("assistant_turn_master", default=None)
# Text of the user's messages in this conversation. Record tools keep a model-supplied code only if
# the user actually typed it; None outside a chat turn.
turn_user_text: ContextVar[Optional[str]] = ContextVar("assistant_turn_user_text", default=None)
# Documents the user attached in this conversation as [{filename, text}]. Kept out of turn_user_text on
# purpose: a code printed inside an uploaded PDF was not typed by the user.
turn_attachments: ContextVar[Optional[List[Dict[str, str]]]] = ContextVar("assistant_turn_attachments", default=None)
# The user's latest message on its own: consent to chart an attachment must be in what they just typed.
turn_last_user_message: ContextVar[Optional[str]] = ContextVar("assistant_turn_last_user_message", default=None)


def record_tool_call(tool: str, args: Dict[str, Any], result: Dict[str, Any]) -> None:
    recorder = turn_recorder.get()
    if recorder is not None:
        recorder.append({"tool": tool, "args": args, "result": result})
