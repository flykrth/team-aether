"""Exceptions shared by every assistant provider."""


class AssistantError(Exception):
    """The model call failed (network, quota, bad key)."""


class AssistantNotConfigured(AssistantError):
    """No LLM provider key is set."""


class SpeechNotConfigured(AssistantError):
    """No speech-to-text provider is set up."""
