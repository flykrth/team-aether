"""
API Router for Steps 14-15: CareStack Multi-Agent Orchestrator (MAO).
Exposes the Agentic Supervisor: event/webhook ingestion, shared state retrieval and the
Server-Sent Events execution stream the frontend uses to render real-time agent reasoning.
"""

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..services.agent_supervisor import agent_supervisor

router = APIRouter()


class AgentEventRequest(BaseModel):
    """CareStack appointment booking or webhook event that triggers a supervisor thread."""
    event_type: str = Field("appointment.booked", description="e.g. appointment.booked, treatment_plan.procedure_added")
    patient_id: str = Field(..., description="CareStack or EHR patient ID, e.g. CS-9921 / pat-chen")
    cdt_codes: List[str] = Field(default_factory=list, description="Scheduled CDT procedure codes")
    timestamp: Optional[str] = Field(None, description="Appointment timestamp (ISO 8601)")
    operatory: Optional[str] = Field(None, description="Assigned operatory")


@router.get("/status", summary="Supervisor Status", description="Agent graph topology, engine and active threads.")
async def supervisor_status() -> Dict[str, Any]:
    return agent_supervisor.describe()


@router.post(
    "/events",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit CareStack Event",
    description="Queues an appointment booking / webhook event for autonomous background processing.",
)
async def submit_agent_event(event: AgentEventRequest) -> Dict[str, Any]:
    try:
        thread = await agent_supervisor.submit_event(event.event_type, event.model_dump(exclude={"event_type"}))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "thread_id": thread.thread_id,
        "patient_id": thread.patient_id,
        "status": thread.status,
        "stream_url": f"/api/agents/stream/{thread.patient_id}",
    }


@router.get("/state/{patient_id}", summary="Get Shared MAO State")
async def get_agent_state(patient_id: str) -> Dict[str, Any]:
    thread = agent_supervisor.get_thread(patient_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"No supervisor thread for patient '{patient_id}'")
    return thread.summary()


@router.get(
    "/stream/{patient_id}",
    summary="Stream Agent Execution (SSE)",
    description=(
        "Server-Sent Events stream of the patient's active supervisor thread: replays steps already "
        "executed, then follows live until the thread completes. If no thread exists and `cdt_code` "
        "is supplied, a new thread is started."
    ),
)
async def stream_agent_execution(
    patient_id: str,
    cdt_code: Optional[str] = Query(None, description="Start a new thread for this CDT code if none exists"),
):
    if agent_supervisor.get_thread(patient_id) is None:
        if not cdt_code:
            raise HTTPException(status_code=404, detail=f"No supervisor thread for patient '{patient_id}'")
        await agent_supervisor.submit_event("manual.run", {"patient_id": patient_id, "cdt_code": cdt_code})

    async def event_source():
        async for event in agent_supervisor.stream(patient_id):
            yield f"event: {event['type']}\nid: {event['sequence']}\ndata: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


class SimulationRequest(BaseModel):
    """Full multi-agent run for one patient / procedure."""
    patient_id: str = Field(..., description="CareStack or EHR patient ID, e.g. CS-9921")
    cdt_code: str = Field(..., description="Planned CDT procedure code, e.g. D7210")
    intake_narrative: Optional[str] = Field(None, description="Free-text intake response for conversational extraction")
    hours_since_dispatch: Optional[float] = Field(None, description="Simulate elapsed hours without a physician reply (>48 escalates)")
    physician_response: Optional[str] = Field(None, description="Simulate the physician's free-text endorsement")


class PhysicianResponseRequest(BaseModel):
    text: str = Field(..., description="Physician's free-text clearance reply")
    signed_by: Optional[str] = Field(None, description="Defaults to the assigned physician")


@router.post(
    "/run-simulation",
    summary="Run Full Multi-Agent Simulation",
    description=(
        "Runs Intake -> Risk -> (Clearance || Billing) to completion for one patient and returns the final "
        "shared state. The run is also replayable from the SSE stream endpoint."
    ),
)
async def run_simulation(request: SimulationRequest) -> Dict[str, Any]:
    thread = await agent_supervisor.run(
        request.patient_id,
        [request.cdt_code],
        trigger="manual.run",
        simulation=request.model_dump(include={"intake_narrative", "hours_since_dispatch", "physician_response"}),
    )
    if thread.status == "FAILED":
        raise HTTPException(status_code=500, detail=f"Supervisor thread failed: {thread.error}")
    return thread.summary()


@router.post(
    "/clearance-response/{patient_id}",
    summary="Ingest Physician Clearance Response",
    description="Clearance agent parses the physician's reply into structured restrictions and clears the appointment.",
)
async def ingest_clearance_response(patient_id: str, payload: PhysicianResponseRequest) -> Dict[str, Any]:
    try:
        thread = await agent_supervisor.ingest_physician_response(patient_id, payload.text, payload.signed_by)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return thread.summary()


@router.post(
    "/check-escalations",
    summary="Run Clearance Escalation Sweep",
    description="Escalates every clearance request unanswered for more than 48 hours (nudge SMS + front-desk flag).",
)
async def check_escalations(
    hours_since_dispatch: Optional[float] = Query(None, description="Override elapsed hours for demo purposes"),
) -> Dict[str, Any]:
    escalated = agent_supervisor.check_escalations(hours_since_dispatch)
    return {"escalated": [t.patient_id for t in escalated]}
