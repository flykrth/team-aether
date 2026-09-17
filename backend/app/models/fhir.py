"""
HL7 FHIR R4 Standard Data Models for the Medical-Dental Interoperability Node (MDIN).
Implemented with Pydantic v2 for strict type safety, automatic validation,
and seamless JSON serialization/deserialization.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict


class FHIRBaseModel(BaseModel):
    """Base model allowing standard FHIR extensions and meta attributes."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Coding(FHIRBaseModel):
    """
    HL7 FHIR R4 Coding data type.
    A reference to a code defined by a terminology system (e.g. SNOMED-CT, ICD-10, LOINC, RxNorm).
    """
    system: Optional[str] = Field(None, description="Identity of the terminology system (URI/URL)")
    version: Optional[str] = Field(None, description="Version of the system - if relevant")
    code: Optional[str] = Field(None, description="Symbol in syntax defined by the system")
    display: Optional[str] = Field(None, description="Representation defined by the system")
    userSelected: Optional[bool] = Field(None, description="If this coding was chosen directly by the user")


class CodeableConcept(FHIRBaseModel):
    """
    HL7 FHIR R4 CodeableConcept data type.
    A concept that may be defined by a formal reference to a terminology or ontology or may be provided by text.
    """
    coding: List[Coding] = Field(default_factory=list, description="Code defined by a terminology system")
    text: Optional[str] = Field(None, description="Plain text representation of the concept")

    def get_code(self, system: Optional[str] = None) -> Optional[str]:
        """Convenience method to retrieve the primary code or match by terminology system."""
        for c in self.coding:
            if system is None or (c.system and system in c.system):
                return c.code
        return None

    def get_display(self) -> str:
        """Returns the text or first display value."""
        if self.text:
            return self.text
        for c in self.coding:
            if c.display:
                return c.display
        return "Unknown Concept"


class Reference(FHIRBaseModel):
    """
    HL7 FHIR R4 Reference data type.
    A reference from one resource to another (e.g., Patient/patient-001).
    """
    reference: Optional[str] = Field(None, description="Literal reference, Relative, internal or absolute URL")
    type: Optional[str] = Field(None, description="Type the reference refers to (e.g. Patient)")
    identifier: Optional[Dict[str, Any]] = Field(None, description="Logical reference, when literal reference is not known")
    display: Optional[str] = Field(None, description="Text alternative for the resource")


class Identifier(FHIRBaseModel):
    """
    HL7 FHIR R4 Identifier data type.
    An identifier intended for computation (MRN, SSN, Driver's License, etc.).
    """
    use: Optional[str] = Field(None, description="usual | official | temp | secondary | old")
    type: Optional[CodeableConcept] = Field(None, description="Description of identifier")
    system: Optional[str] = Field(None, description="The namespace for the identifier value")
    value: Optional[str] = Field(None, description="The value that is unique within the system")


class HumanName(FHIRBaseModel):
    """
    HL7 FHIR R4 HumanName data type.
    Name of a human or other person with text, family, and given name components.
    """
    use: Optional[str] = Field(None, description="usual | official | temp | nickname | anonymous | old | maiden")
    text: Optional[str] = Field(None, description="Text representation of the full name")
    family: Optional[str] = Field(None, description="Family name (often called 'Surname')")
    given: List[str] = Field(default_factory=list, description="Given names (not always 'first'). Includes middle names")
    prefix: List[str] = Field(default_factory=list, description="Parts that come before the name")
    suffix: List[str] = Field(default_factory=list, description="Parts that come after the name")

    def full_name(self) -> str:
        """Returns concatenated full name string."""
        if self.text:
            return self.text
        parts = []
        if self.prefix:
            parts.extend(self.prefix)
        if self.given:
            parts.extend(self.given)
        if self.family:
            parts.append(self.family)
        if self.suffix:
            parts.extend(self.suffix)
        return " ".join(parts).strip()


class ContactPoint(FHIRBaseModel):
    """HL7 FHIR R4 ContactPoint data type (telecom, phone, email, fax)."""
    system: Optional[str] = Field(None, description="phone | fax | email | pager | url | sms | other")
    value: Optional[str] = Field(None, description="The actual contact point details")
    use: Optional[str] = Field(None, description="home | work | temp | old | mobile")
    rank: Optional[int] = Field(None, description="Specify preferred order of use (1 = highest)")


class Address(FHIRBaseModel):
    """HL7 FHIR R4 Address data type."""
    use: Optional[str] = Field(None, description="home | work | temp | old | billing")
    type: Optional[str] = Field(None, description="postal | physical | both")
    text: Optional[str] = Field(None, description="Text representation of the address")
    line: List[str] = Field(default_factory=list, description="Street name, number, direction & P.O. Box etc.")
    city: Optional[str] = Field(None, description="Name of city, town etc.")
    state: Optional[str] = Field(None, description="Sub-unit of country (state, province, county)")
    postalCode: Optional[str] = Field(None, description="Postal code for area")
    country: Optional[str] = Field(None, description="Country (can be ISO 3166 2 or 3 letter code)")


class Patient(FHIRBaseModel):
    """
    HL7 FHIR R4 Patient Resource.
    Demographics and administrative information about an individual receiving care.
    """
    resourceType: str = Field("Patient", description="HL7 FHIR Resource Type")
    id: str = Field(..., description="Logical id of this artifact")
    identifier: List[Identifier] = Field(default_factory=list, description="An identifier for this patient (e.g. MRN)")
    active: Optional[bool] = Field(True, description="Whether this patient record is in active use")
    name: List[HumanName] = Field(default_factory=list, description="A name associated with the individual")
    telecom: List[ContactPoint] = Field(default_factory=list, description="A contact detail for the individual")
    gender: Optional[str] = Field(None, description="male | female | other | unknown")
    birthDate: Optional[str] = Field(None, description="The date of birth for the individual (YYYY-MM-DD)")
    address: List[Address] = Field(default_factory=list, description="An address for the individual")

    def get_full_name(self) -> str:
        """Helper to get primary display name."""
        if self.name:
            return self.name[0].full_name()
        return f"Patient {self.id}"

    def get_mrn(self) -> Optional[str]:
        """Helper to extract MRN identifier if present."""
        for ident in self.identifier:
            if ident.value:
                return ident.value
        return self.id


class Condition(FHIRBaseModel):
    """
    HL7 FHIR R4 Condition Resource.
    Detailed information about conditions, problems or diagnoses for clinical correlation.
    """
    resourceType: str = Field("Condition", description="HL7 FHIR Resource Type")
    id: str = Field(..., description="Logical id of this artifact")
    clinicalStatus: Optional[CodeableConcept] = Field(None, description="active | recurrence | relapse | inactive | remission | resolved")
    verificationStatus: Optional[CodeableConcept] = Field(None, description="unconfirmed | provisional | differential | confirmed | refuted | entered-in-error")
    category: List[CodeableConcept] = Field(default_factory=list, description="problem-list-item | encounter-diagnosis")
    severity: Optional[CodeableConcept] = Field(None, description="Subjective severity of condition")
    code: Optional[CodeableConcept] = Field(None, description="Identification of the condition, problem or diagnosis (SNOMED-CT / ICD-10)")
    subject: Reference = Field(..., description="Who has the condition? Reference to Patient")
    onsetDateTime: Optional[str] = Field(None, description="Estimated or actual date, date-time, or age")
    recordedDate: Optional[str] = Field(None, description="Date record was first recorded")
    note: List[Dict[str, Any]] = Field(default_factory=list, description="Additional information about the Condition")

    def is_active(self) -> bool:
        """Check if condition clinicalStatus is active."""
        if not self.clinicalStatus:
            return True
        for c in self.clinicalStatus.coding:
            if c.code and c.code.lower() in ["active", "recurrence", "relapse"]:
                return True
        return False


class MedicationRequest(FHIRBaseModel):
    """
    HL7 FHIR R4 MedicationRequest Resource.
    An order or request for supply of medication and instructions for administration.
    """
    resourceType: str = Field("MedicationRequest", description="HL7 FHIR Resource Type")
    id: str = Field(..., description="Logical id of this artifact")
    status: str = Field("active", description="active | on-hold | cancelled | completed | entered-in-error | stopped | draft | unknown")
    statusReason: Optional[CodeableConcept] = Field(None, description="Reason for current status")
    intent: str = Field("order", description="proposal | plan | order | original-order | reflex-order | filler-order | instance-order | option")
    category: List[CodeableConcept] = Field(default_factory=list, description="Type of medication usage (inpatient, outpatient, community)")
    priority: Optional[str] = Field(None, description="routine | urgent | asap | stat")
    medicationCodeableConcept: Optional[CodeableConcept] = Field(None, description="Medication prescription details (RxNorm code/display)")
    medicationReference: Optional[Reference] = Field(None, description="Reference to Medication resource")
    subject: Reference = Field(..., description="Who or what medication request is for (Patient reference)")
    authoredOn: Optional[str] = Field(None, description="When request was initially authored")
    requester: Optional[Reference] = Field(None, description="Who/What ordered the medication")
    dosageInstruction: List[Dict[str, Any]] = Field(default_factory=list, description="How the medication should be taken")

    def is_active(self) -> bool:
        """Check if medication request status is active."""
        return self.status.lower() in ["active", "order"]


class AllergyIntoleranceReaction(FHIRBaseModel):
    """HL7 FHIR R4 AllergyIntolerance Reaction component."""
    substance: Optional[CodeableConcept] = Field(None, description="Specific substance or pharmaceutical agent")
    manifestation: List[CodeableConcept] = Field(default_factory=list, description="Clinical symptoms/signs associated with the Event")
    description: Optional[str] = Field(None, description="Description of the event as a whole")
    onset: Optional[str] = Field(None, description="Date(/time) when manifestations showed")
    severity: Optional[str] = Field(None, description="mild | moderate | severe (of the event as a whole)")
    exposureRoute: Optional[CodeableConcept] = Field(None, description="How the subject was exposed to the substance")


class AllergyIntolerance(FHIRBaseModel):
    """
    HL7 FHIR R4 AllergyIntolerance Resource.
    Risk of harmful reaction to a substance (medication, food, latex, etc.).
    """
    resourceType: str = Field("AllergyIntolerance", description="HL7 FHIR Resource Type")
    id: str = Field(..., description="Logical id of this artifact")
    clinicalStatus: Optional[CodeableConcept] = Field(None, description="active | inactive | resolved")
    verificationStatus: Optional[CodeableConcept] = Field(None, description="unconfirmed | confirmed | refuted | entered-in-error")
    type: Optional[str] = Field(None, description="allergy | intolerance - Underlying mechanism")
    category: List[str] = Field(default_factory=list, description="food | medication | environment | biologic")
    criticality: Optional[str] = Field(None, description="low | high | unable-to-assess")
    code: Optional[CodeableConcept] = Field(None, description="Code that identifies the allergy or intolerance (SNOMED-CT)")
    patient: Reference = Field(..., description="Who the sensitivity is for (Patient reference)")
    recordedDate: Optional[str] = Field(None, description="Date first version of the resource was recorded")
    reaction: List[AllergyIntoleranceReaction] = Field(default_factory=list, description="Adverse Reaction Events linked to exposure")


class Observation(FHIRBaseModel):
    """
    HL7 FHIR R4 Observation Resource.
    Measurements and simple assertions made about a patient (e.g. HbA1c, INR, Blood Pressure).
    """
    resourceType: str = Field("Observation", description="HL7 FHIR Resource Type")
    id: str = Field(..., description="Logical id of this artifact")
    status: str = Field("final", description="registered | preliminary | final | amended | corrected | cancelled | entered-in-error | unknown")
    category: List[CodeableConcept] = Field(default_factory=list, description="Classification of type of observation (laboratory, vital-signs)")
    code: CodeableConcept = Field(..., description="Type of observation (code / LOINC)")
    subject: Reference = Field(..., description="Who and/or what the observation is about (Patient reference)")
    effectiveDateTime: Optional[str] = Field(None, description="Clinically relevant time/time-period for observation")
    issued: Optional[str] = Field(None, description="Date/Time this version was made available")
    valueQuantity: Optional[Dict[str, Any]] = Field(None, description="Actual result (value, unit, system, code)")
    valueCodeableConcept: Optional[CodeableConcept] = Field(None, description="Actual result as code")
    valueString: Optional[str] = Field(None, description="Actual result as string")
    referenceRange: List[Dict[str, Any]] = Field(default_factory=list, description="Provides guide for interpretation of result")


class BundleEntrySearch(FHIRBaseModel):
    """HL7 FHIR R4 search metadata in BundleEntry."""
    mode: Optional[str] = Field("match", description="match | include | outcome")
    score: Optional[float] = Field(None, description="Search ranking/match score (0 to 1)")


class BundleEntry(FHIRBaseModel):
    """
    HL7 FHIR R4 BundleEntry component.
    An entry in a bundle resource - will contain a resource or information about a resource.
    """
    fullUrl: Optional[str] = Field(None, description="URI for resource (Absolute URL or urn:uuid)")
    resource: Optional[Dict[str, Any]] = Field(None, description="A resource in the bundle")
    search: Optional[BundleEntrySearch] = Field(None, description="Search related information")


class BundleLink(FHIRBaseModel):
    """HL7 FHIR R4 link element for pagination/search."""
    relation: str = Field(..., description="self | next | prev | first | last")
    url: str = Field(..., description="Target URL")


class Bundle(FHIRBaseModel):
    """
    HL7 FHIR R4 Bundle Resource.
    A container for a collection of resources (e.g. searchset, collection, document, transaction).
    """
    resourceType: str = Field("Bundle", description="HL7 FHIR Resource Type")
    id: Optional[str] = Field(None, description="Logical id of this artifact")
    type: str = Field("searchset", description="document | message | transaction | transaction-response | batch | batch-response | history | searchset | collection")
    timestamp: Optional[str] = Field(None, description="When the bundle was assembled")
    total: Optional[int] = Field(None, description="If search, the total number of matches")
    link: List[BundleLink] = Field(default_factory=list, description="Links related to this Bundle")
    entry: List[BundleEntry] = Field(default_factory=list, description="Entry in the bundle - will have a resource or information")


class CapabilityStatement(FHIRBaseModel):
    """HL7 FHIR R4 CapabilityStatement Resource."""
    resourceType: str = Field("CapabilityStatement", description="HL7 FHIR Resource Type")
    status: str = Field("active", description="draft | active | retired | unknown")
    name: str = Field("MDIN_CapabilityStatement", description="Name for this capability statement")
    title: str = Field("Medical-Dental Interoperability Node FHIR Server", description="Human-friendly name")
    fhirVersion: str = Field("4.0.1", description="FHIR Version the system uses")
    format: List[str] = Field(default_factory=lambda: ["json"], description="formats supported (xml | json | etc.)")
    rest: List[Dict[str, Any]] = Field(default_factory=list, description="If the endpoint is a RESTful one")
