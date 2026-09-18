"""
API Router for Patient Records: add patients, medical history and previous medical records.

Thin HTTP layer over services/patient_registry.py. Free text is coded deterministically there
(ICD-10-CM / RxNorm / SNOMED / LOINC lexicons); this router never calls an LLM.
"""

from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from ..services import patient_registry, record_intelligence
from ..services.document_ingest import MAX_FILE_BYTES, DocumentError, document_to_text

router = APIRouter()

MAX_ENTRIES = patient_registry.MAX_ENTRIES
MAX_RECORD_CHARS = 200_000  # everything accepted here is persisted to the runtime registry


class HistoryEntry(BaseModel):
    type: Literal["condition", "medication", "allergy", "observation"]
    text: str = Field("", max_length=300, description="Free text, e.g. 'warfarin 5mg daily'. Coded by the lexicon when no code is given")
    code: Optional[str] = Field(None, max_length=32)
    system: Optional[str] = Field(None, max_length=80)
    display: Optional[str] = Field(None, max_length=300)
    onset: Optional[str] = Field(None, max_length=40, description="ISO date: onset, start date or lab date")
    value: Optional[Union[float, str]] = None
    unit: Optional[str] = Field(None, max_length=32)

    @field_validator("value")
    @classmethod
    def _short_value(cls, value):
        if isinstance(value, str) and len(value) > 64:
            raise ValueError("value is limited to 64 characters")
        return value


class PlannedProcedure(BaseModel):
    code: str = Field(..., max_length=16, description="CDT code, e.g. D7140")
    description: Optional[str] = Field(None, max_length=200)
    tooth_number: Optional[str] = Field(None, max_length=8)


class PatientCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(..., min_length=1, max_length=80)
    birth_date: str = Field(..., max_length=32, description="YYYY-MM-DD, not in the future")
    gender: Optional[str] = Field("unknown", max_length=16)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=254)
    planned_procedures: Optional[List[PlannedProcedure]] = Field(None, max_length=40)
    history: Optional[List[HistoryEntry]] = Field(None, max_length=MAX_ENTRIES)


class HistoryRequest(BaseModel):
    entries: List[HistoryEntry] = Field(..., min_length=1, max_length=MAX_ENTRIES)
    source: Optional[str] = Field("manual", max_length=40, pattern=r"^[a-z0-9-]+$")


class ExtractRequest(BaseModel):
    text: str = Field(..., max_length=MAX_RECORD_CHARS)


class ImportRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    text: str = Field(..., min_length=1, max_length=MAX_RECORD_CHARS)
    record_date: Optional[str] = Field(None, max_length=32)
    source_facility: Optional[str] = Field(None, max_length=200)
    entries: Optional[List[HistoryEntry]] = Field(None, max_length=MAX_ENTRIES, description="Entries the user confirmed; omitted = extract from text")


def _dump(entries: Optional[List[HistoryEntry]]) -> Optional[List[Dict[str, Any]]]:
    return None if entries is None else [e.model_dump(exclude_none=True) for e in entries]


def _call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/patients", summary="List Patients")
async def list_patients() -> List[Dict[str, Any]]:
    return patient_registry.list_patients()


@router.post("/patients", status_code=status.HTTP_201_CREATED, summary="Add a Patient (CareStack chart + linked medical record)")
async def create_patient(request: PatientCreate) -> Dict[str, Any]:
    # A bad history entry must fail the request before the patient exists, not after
    _call(patient_registry.validate_entries, _dump(request.history))
    result = _call(
        patient_registry.create_patient,
        request.first_name, request.last_name, request.birth_date, request.gender or "unknown",
        request.phone, request.email,
        [p.model_dump() for p in request.planned_procedures or []],
    )
    if request.history:
        result["history"] = _call(patient_registry.add_history_entries, result["patient_id"], _dump(request.history), "intake")
    return result


@router.get("/patients/{patient_id}", summary="Patient Record (same shape as the assistant's get_patient_history)")
async def get_patient(patient_id: str) -> Dict[str, Any]:
    from ..services.assistant.tools import get_patient_history

    history = await get_patient_history(patient_id)
    if not history.get("found"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=history.get("message"))
    return history


@router.post("/patients/{patient_id}/history", summary="Add Conditions, Medications, Allergies or Lab Values")
async def add_history(patient_id: str, request: HistoryRequest) -> Dict[str, Any]:
    return _call(patient_registry.add_history_entries, patient_id, _dump(request.entries), request.source or "manual")


@router.post("/extract", summary="Preview the Coded Entries Found in Free Text (deterministic)")
async def extract(request: ExtractRequest) -> Dict[str, Any]:
    # Model-assisted classification, grounded and rule-coded; falls back to the rules alone without an LLM
    return await record_intelligence.analyze(request.text)


@router.post("/patients/{patient_id}/import", summary="Import a Previous Medical Record")
async def import_record(patient_id: str, request: ImportRequest) -> Dict[str, Any]:
    return _call(
        patient_registry.import_previous_record,
        patient_id, request.title, request.text, request.record_date, request.source_facility, _dump(request.entries),
    )


# Patients added before the last (dev-server) reload come back before the first request
patient_registry.load_runtime_registry()


# ---------------------------------------------------------------------
# Manual mode: browse, edit and delete every detail of a chart
# ---------------------------------------------------------------------

class PatientUpdate(BaseModel):
    first_name: Optional[str] = Field(None, max_length=80)
    last_name: Optional[str] = Field(None, max_length=80)
    birth_date: Optional[str] = Field(None, max_length=10)
    gender: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=120)
    next_appointment: Optional[str] = Field(None, max_length=40)
    primary_dentist: Optional[str] = Field(None, max_length=120)
    planned_procedures: Optional[List[PlannedProcedure]] = Field(None, max_length=30)


class HistoryEntryUpdate(BaseModel):
    type: Optional[Literal["condition", "medication", "allergy", "observation"]] = None
    text: Optional[str] = Field(None, max_length=300)
    onset: Optional[str] = Field(None, max_length=10)
    value: Optional[Union[float, str]] = None
    unit: Optional[str] = Field(None, max_length=40)


@router.delete("/patients/{patient_id}", summary="Remove a Patient and the Whole Chart")
async def delete_patient(patient_id: str) -> Dict[str, Any]:
    result = _call(patient_registry.delete_patient, patient_id)
    from ..services.coverage import plans  # the member's uploaded plan document goes with the chart
    plans.forget(result["deleted"])
    from ..services import visits
    visits.forget(result["deleted"])
    return result


@router.get("/patients/{patient_id}/chart", summary="Editable Chart (every history item carries its id)")
async def get_chart(patient_id: str) -> Dict[str, Any]:
    return _call(patient_registry.get_chart, patient_id)


@router.patch("/patients/{patient_id}", summary="Edit Patient Details and Treatment Plan")
async def update_patient(patient_id: str, request: PatientUpdate) -> Dict[str, Any]:
    changes = request.model_dump(exclude_none=True)
    return _call(patient_registry.update_patient, patient_id, changes)


@router.patch("/patients/{patient_id}/history/{resource_id}", summary="Edit One History Item")
async def update_history_entry(patient_id: str, resource_id: str, request: HistoryEntryUpdate) -> Dict[str, Any]:
    return _call(patient_registry.update_history_entry, patient_id, resource_id, request.model_dump(exclude_none=True))


@router.delete("/patients/{patient_id}/history/{resource_id}", summary="Remove One History Item")
async def delete_history_entry(patient_id: str, resource_id: str) -> Dict[str, Any]:
    return _call(patient_registry.delete_history_entry, patient_id, resource_id)


@router.post("/extract-file", summary="Read a PDF or Text File and Preview the Coded Entries Found in It")
async def extract_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    data = await file.read(MAX_FILE_BYTES + 1)
    try:
        document = await document_to_text(data, file.filename or "", file.content_type or "")
    except DocumentError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {**document, "filename": file.filename, **await record_intelligence.analyze(document["text"])}
