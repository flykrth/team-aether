"""
API Router for the Dental Coverage Recovery Agent: when a patient's dental benefit cannot pay, is there a
legitimate medical-benefit pathway for the proposed service under this patient's plan?
Everything it says about coverage is quoted from published payer policy or the member's own plan document.
"""

import asyncio
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ..services.coverage import analyst, embeddings, packet, plans, policy_store, retrieval
from ..services.document_ingest import MAX_FILE_BYTES, DocumentError, document_to_text

router = APIRouter()
_index_task: Optional[asyncio.Task] = None


def _guard(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _start_indexing(region: str) -> None:
    global _index_task
    if _index_task is None or _index_task.done():
        _index_task = asyncio.create_task(retrieval.build_index(region))


class DentalBenefit(BaseModel):
    status: Literal["active", "expired", "exhausted", "denied", "none", "unknown"]
    carrier: str = Field("", max_length=120)
    note: str = Field("", max_length=300)


class MedicalPlan(BaseModel):
    insurer: str = Field("", max_length=120)
    plan_name: str = Field("", max_length=120)
    plan_type: str = Field("", max_length=40)
    member_id: str = Field("", max_length=60)


class InsuranceUpdate(BaseModel):
    dental: Optional[DentalBenefit] = None
    medical: Optional[MedicalPlan] = None


class CaseForm(BaseModel):
    patient_id: str = Field(..., max_length=80)
    region: str = Field("US", max_length=4)
    procedure: str = Field(..., min_length=2, max_length=300)
    diagnosis: str = Field("", max_length=300)
    diagnosis_codes: str = Field("", max_length=120)
    imaging: str = Field("", max_length=400)
    symptoms: list[str] = Field(default_factory=list, max_length=12)
    clinical_note: str = Field("", max_length=8000)
    flags: Dict[str, Optional[bool]] = Field(default_factory=dict, description="Staff answers; null or absent = not known")


class PacketRequest(BaseModel):
    patient_id: str = Field(..., max_length=80)
    reviewed_by: str = Field("", max_length=120)


@router.get("/sources", summary="Policy Library: What Is Cached, How Old It Is, What Failed")
async def sources(region: str = "US") -> Dict[str, Any]:
    registry = policy_store.load_registry()
    return {"regions": registry["regions"], "region": region, "insurers": plans.insurers(region),
            "sources": policy_store.status(region), "index": retrieval.index_status(),
            "embedding_provider": embeddings.provider(), "case_flags": {k: v[0] for k, v in analyst.case_facts.FLAGS.items()}}


@router.post("/sources/refresh", summary="Re-download the Published Policies and Re-index Them")
async def refresh_sources(region: str = "US") -> Dict[str, Any]:
    rows = await policy_store.refresh(region)
    _start_indexing(region)  # metered embedding runs in the background; search works meanwhile
    return {"refreshed": len([r for r in rows if r.get("ok")]), "failed": [{"id": r["id"], "error": r.get("error")} for r in rows if not r.get("ok")],
            "sources": policy_store.status(region), "index": retrieval.index_status()}


@router.get("/patients/{patient_id}/insurance", summary="Dental Benefit Status, Medical Plan and Plan Document")
async def get_insurance(patient_id: str) -> Dict[str, Any]:
    return _guard(plans.get_insurance, patient_id)


@router.put("/patients/{patient_id}/insurance", summary="Set Dental Benefit Status and Medical Plan")
async def put_insurance(patient_id: str, request: InsuranceUpdate) -> Dict[str, Any]:
    return _guard(plans.set_insurance, patient_id, request.dental.model_dump() if request.dental else None,
                  request.medical.model_dump() if request.medical else None)


@router.post("/patients/{patient_id}/plan-document", summary="Upload the Member's Plan Document (SBC / Certificate of Coverage)")
async def upload_plan_document(patient_id: str, file: UploadFile = File(...), title: str = Form("")) -> Dict[str, Any]:
    data = await file.read(MAX_FILE_BYTES + 1)
    try:
        document = await document_to_text(data, file.filename or "", file.content_type or "")
    except DocumentError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _guard(plans.set_plan_document, patient_id, title or (file.filename or "Plan document"), document["text"], document["method"])


@router.delete("/patients/{patient_id}/plan-document", summary="Remove the Uploaded Plan Document")
async def delete_plan_document(patient_id: str) -> Dict[str, Any]:
    return _guard(plans.remove_plan_document, patient_id)


@router.post("/analyze", summary="Run the Coverage Recovery Decision Tree for One Case")
async def analyze(form: CaseForm) -> Dict[str, Any]:
    try:
        result = await analyst.analyze(form.model_dump())
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'\""))
    if result.get("facts"):
        packet.remember(result)
    return result


@router.post("/packet", summary="Produce the Pre-treatment Estimate Request or the Patient Explanation")
async def make_packet(request: PacketRequest) -> Dict[str, Any]:
    chart_id = _guard(plans._resolve, request.patient_id)
    return _guard(packet.build, chart_id, request.reviewed_by)
