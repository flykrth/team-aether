"""
CDS Hooks v1.0 specification models for Clinical Decision Support.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CDSSource(BaseModel):
    label: str
    url: Optional[str] = None
    icon: Optional[str] = None


class CDSSuggestion(BaseModel):
    label: str
    uuid: Optional[str] = None
    actions: List[Dict[str, Any]] = Field(default_factory=list)


class CDSCard(BaseModel):
    summary: str
    indicator: str = Field(..., description="info, warning, critical")
    detail: Optional[str] = None
    source: CDSSource
    suggestions: List[CDSSuggestion] = Field(default_factory=list)
    selectionBehavior: Optional[str] = None
    links: List[Dict[str, str]] = Field(default_factory=list)


class CDSService(BaseModel):
    hook: str
    title: str
    description: str
    id: str
    prefetch: Optional[Dict[str, str]] = None


class CDSDiscoveryResponse(BaseModel):
    services: List[CDSService]


class CDSHookRequest(BaseModel):
    hook: str
    hookInstance: str
    fhirServer: Optional[str] = None
    fhirAuthorization: Optional[Dict[str, Any]] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    prefetch: Optional[Dict[str, Any]] = None


class CDSHookResponse(BaseModel):
    cards: List[CDSCard] = Field(default_factory=list)
