"""
MAO Assistant: one master tool-calling agent (Gemini, Groq or NVIDIA NIM) with parallel
specialist models, over the MDIN / CareStack application.
"""

from .errors import AssistantError, AssistantNotConfigured, SpeechNotConfigured
from .orchestrator import chat

__all__ = ["chat", "AssistantError", "AssistantNotConfigured", "SpeechNotConfigured"]
