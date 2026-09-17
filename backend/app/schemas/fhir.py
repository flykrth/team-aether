"""
FHIR R4 standard schemas for Medical EHR Interoperability.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FHIRCoding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None


class FHIRCodeableConcept(BaseModel):
    coding: List[FHIRCoding] = Field(default_factory=list)
    text: Optional[str] = None


class FHIRPatient(BaseModel):
    resourceType: str = "Patient"
    id: str
    active: bool = True
    name: List[Dict[str, Any]] = Field(default_factory=list)
    gender: Optional[str] = None
    birthDate: Optional[str] = None
    telecom: List[Dict[str, Any]] = Field(default_factory=list)


class FHIRCondition(BaseModel):
    resourceType: str = "Condition"
    id: str
    clinicalStatus: Optional[Dict[str, Any]] = None
    verificationStatus: Optional[Dict[str, Any]] = None
    code: FHIRCodeableConcept
    subject: Dict[str, str]
    onsetDateTime: Optional[str] = None


class FHIRObservation(BaseModel):
    resourceType: str = "Observation"
    id: str
    status: str = "final"
    code: FHIRCodeableConcept
    subject: Dict[str, str]
    valueQuantity: Optional[Dict[str, Any]] = None
    valueString: Optional[str] = None
    effectiveDateTime: Optional[str] = None


class FHIRAllergyIntolerance(BaseModel):
    resourceType: str = "AllergyIntolerance"
    id: str
    clinicalStatus: Optional[Dict[str, Any]] = None
    criticality: Optional[str] = None
    code: FHIRCodeableConcept
    patient: Dict[str, str]


class FHIRCapabilityStatement(BaseModel):
    resourceType: str = "CapabilityStatement"
    status: str = "active"
    name: str = "MDIN_CapabilityStatement"
    title: str = "Medical-Dental Interoperability Node FHIR Server"
    fhirVersion: str = "4.0.1"
    format: List[str] = ["json"]
    rest: List[Dict[str, Any]] = Field(default_factory=list)
