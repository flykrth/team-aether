"""
HL7 CDS Hooks v1.0 / v2.0 Specification Pydantic Models.
Provides standard clinical decision support data structures for service discovery,
hook requests, contextual evaluation, and card responses.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class CDSBaseModel(BaseModel):
    """Base model allowing standard CDS Hooks extensions and meta attributes."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class CDSService(CDSBaseModel):
    """Metadata describing a registered CDS Service."""
    hook: str = Field(..., description="The hook this service subscribes to, e.g. 'patient-view', 'order-select'")
    title: str = Field(..., description="Human-readable name of the CDS service")
    description: str = Field(..., description="Human-readable description of what the service does")
    id: str = Field(..., description="Unique identifier for this service endpoint")
    prefetch: Optional[Dict[str, str]] = Field(None, description="FHIR read/search templates for prefetch data")
    usageRequirements: Optional[str] = Field(None, description="Human-readable description of requirements")


class CDSServiceDiscovery(CDSBaseModel):
    """Discovery response containing list of registered CDS Services."""
    services: List[CDSService] = Field(default_factory=list, description="List of registered CDS services")


class CDSRequest(CDSBaseModel):
    """Request payload sent by EHR/PMS client when invoking a CDS hook."""
    hook: str = Field(..., description="The hook that was triggered")
    hookInstance: str = Field(..., description="UUID for this specific hook invocation")
    fhirServer: Optional[str] = Field(None, description="Base URL of the FHIR server")
    fhirAuthorization: Optional[Dict[str, Any]] = Field(None, description="OAuth2 authorization details")
    context: Dict[str, Any] = Field(default_factory=dict, description="Hook-specific contextual data")
    prefetch: Optional[Dict[str, Any]] = Field(None, description="Prefetched FHIR resources keyed by prefetch tokens")


class CDSSuggestionAction(CDSBaseModel):
    """Action object within a CDS Card suggestion (create, update, or delete)."""
    type: str = Field(..., description="Type of action: 'create', 'update', or 'delete'")
    description: str = Field(..., description="Human-readable description of the suggested action")
    resource: Optional[Dict[str, Any]] = Field(None, description="FHIR resource to create or update")


class CDSSuggestion(CDSBaseModel):
    """Suggestion object allowing clinician to accept automated clinical actions."""
    label: str = Field(..., description="Human-readable label for the suggestion action button")
    uuid: Optional[str] = Field(None, description="Unique identifier for this suggestion")
    actions: List[CDSSuggestionAction] = Field(default_factory=list, description="List of actions to take")
    isRecommended: Optional[bool] = Field(None, description="Whether this is the recommended action")


class CDSLink(CDSBaseModel):
    """External link or SMART on FHIR App launch object."""
    label: str = Field(..., description="Human-readable label for the link")
    url: str = Field(..., description="URL to launch (absolute web URL or SMART app launch URL)")
    type: str = Field("absolute", description="Type of link: 'absolute' or 'smart'")
    appContext: Optional[str] = Field(None, description="Context parameters passed to SMART app")


class CDSSource(CDSBaseModel):
    """Source attribution for a CDS Card."""
    label: str = Field(..., description="Short name of the clinical sponsor, authority, or rule engine")
    url: Optional[str] = Field(None, description="Link to sponsor website or clinical guideline")
    icon: Optional[str] = Field(None, description="Icon URL for source branding")
    topic: Optional[Dict[str, Any]] = Field(None, description="FHIR CodeableConcept indicating topic")


class CDSCard(CDSBaseModel):
    """Clinical Decision Support Card returned to EHR/PMS."""
    summary: str = Field(
        ...,
        max_length=140,
        description="Headline summary of the card, strictly capped at 140 characters per CDS Hooks spec",
    )
    detail: Optional[str] = Field(None, description="Markdown-formatted detailed clinical explanation and guidance")
    indicator: Literal["info", "warning", "critical"] = Field(
        ..., description="Urgency / severity of the card: 'info', 'warning', or 'critical'"
    )
    source: CDSSource = Field(..., description="Source attribution for this card")
    suggestions: List[CDSSuggestion] = Field(default_factory=list, description="List of automated suggestions")
    selectionBehavior: Optional[str] = Field(
        None, description="Intended selection behavior for suggestions: 'at-most-one' or 'any'"
    )
    links: List[CDSLink] = Field(default_factory=list, description="External or SMART App launch links")
    uuid: Optional[str] = Field(None, description="Unique identifier for this card")


class CDSResponse(CDSBaseModel):
    """Container model returning CDS cards in response to hook invocation."""
    cards: List[CDSCard] = Field(default_factory=list, description="List of CDS decision support cards")
