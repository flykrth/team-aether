"""
API Router for Step 14: CareStack Multi-Agent Orchestrator (MAO).
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
