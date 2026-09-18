"""
API Router for the visit workflow: patient -> history -> risk check -> procedure -> insurance.
The risk check (/api/risk/check) and the insurance check (/api/coverage/analyze) record themselves on the visit;
this router reads the visit and moves it along.
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..services import visits
from ..services.coverage import plans

router = APIRouter()


def _guard(call, *args):
    try:
        return call(*args)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


class ProcedureDone(BaseModel):
    outcome_note: str = Field("", max_length=1000, description="Anything worth keeping about how the procedure went")


def _view(patient_id: str) -> Dict[str, Any]:
    return {"visit": visits.current(patient_id), "next_step": visits.next_step(patient_id),
            "insurance": plans.get_insurance(patient_id), "past_visits": [v for v in visits.history(patient_id) if v["stage"] == "closed"][:5]}


@router.get("/patients/{patient_id}", summary="The Visit in Progress, What Comes Next, and the Patient's Insurance")
async def get_visit(patient_id: str) -> Dict[str, Any]:
    return _guard(_view, patient_id)


@router.post("/patients/{patient_id}/procedure-done", summary="Mark the Procedure as Carried Out")
async def procedure_done(patient_id: str, request: ProcedureDone) -> Dict[str, Any]:
    _guard(visits.mark_procedure_done, patient_id, request.outcome_note)
    return _view(patient_id)


@router.post("/patients/{patient_id}/close", summary="Close the Visit")
async def close_visit(patient_id: str) -> Dict[str, Any]:
    _guard(visits.close, patient_id)
    return _view(patient_id)
