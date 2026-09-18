"""
API Router for the manual-mode Risk Check: history on file + today's notes + a planned procedure
-> risks the doctor might miss, with literature quotes. Read-only: nothing is written to the chart.
"""

from typing import Any, Dict, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services import input_check, risk_check

router = APIRouter()


class RiskCheckRequest(BaseModel):
    patient_id: str = Field(..., max_length=80)
    procedure: str = Field(..., min_length=2, max_length=300, description="In the doctor's words or a CDT code")
    current_notes: str = Field("", max_length=8000, description="What the doctor learned today, free text")
    include_evidence: bool = True
    include_ai: bool = True


@router.post("/check", summary="Check a Planned Procedure Against the Patient's History")
async def risk_check_endpoint(request: RiskCheckRequest) -> Dict[str, Any]:
    return await risk_check.check(**request.model_dump())


@router.get("/procedures", summary="Procedure Phrases the Risk Check Understands")
async def procedures() -> Dict[str, Any]:
    return {"procedures": [{"cdt_code": code, "label": label} for _, code, label in risk_check.PROCEDURE_LEXICON]}


class InputCheckRequest(BaseModel):
    field: Literal["procedure", "notes"]
    text: str = Field("", max_length=8000)


@router.post("/validate-input", summary="Spell-fix and Sanity-check a Typed or Dictated Risk Check Field")
async def validate_input(request: InputCheckRequest) -> Dict[str, Any]:
    return await input_check.check(request.field, request.text)
