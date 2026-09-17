"""
CDS Hooks specification models for Clinical Decision Support.
Re-exports standard models from backend.app.models.cds_hooks with backward compatibility aliases.
"""

from ..models.cds_hooks import (
    CDSSource,
    CDSSuggestionAction,
    CDSSuggestion,
    CDSLink,
    CDSCard,
    CDSService,
    CDSServiceDiscovery,
    CDSRequest,
    CDSResponse,
)

# Backward-compatibility aliases for legacy Phase 1 / Phase 2 schemas
CDSDiscoveryResponse = CDSServiceDiscovery
CDSHookRequest = CDSRequest
CDSHookResponse = CDSResponse

__all__ = [
    "CDSSource",
    "CDSSuggestionAction",
    "CDSSuggestion",
    "CDSLink",
    "CDSCard",
    "CDSService",
    "CDSServiceDiscovery",
    "CDSRequest",
    "CDSResponse",
    "CDSDiscoveryResponse",
    "CDSHookRequest",
    "CDSHookResponse",
]
