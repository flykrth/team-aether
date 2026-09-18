"""
Step 14: Central Agentic Supervisor and shared MAO state.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.agent_state import create_initial_state, validate_state
from app.services.agent_supervisor import AgenticSupervisor


def test_initial_state_validates():
    state = create_initial_state("CS-9921", cdt_codes=["d7210"])
    model = validate_state(state)
    assert model.appointment.cdt_codes == ["D7210"]
    assert model.intake_status == "PENDING"
    assert model.clearance_status == "NOT_REQUIRED"
    assert state["agent_logs"] == [] and state["risk_evaluations"] == []


def test_invalid_state_rejected():
    state = dict(create_initial_state("CS-9921"))
    state["clearance_status"] = "BOGUS"
    with pytest.raises(ValidationError):
        validate_state(state)


@pytest.mark.anyio
async def test_high_risk_patient_routes_through_clearance():
    thread = await AgenticSupervisor().run("pat-1", ["D7140"])
    assert thread.status == "COMPLETED", thread.error
    state = thread.state
    assert state["intake_status"] == "PORTAL_LINKED"
    assert state["risk_evaluations"][0]["hazard_level"] == "CRITICAL"
    assert state["clearance_status"] == "TRANSMITTED_TO_EHR"
    assert state["appointment"]["status"] == "REQUIRES_ACTION"
    assert state["assigned_medical_md"]["npi"]
    steps = [e["node"] for e in thread.events if e["type"] == "agent_step"]
    assert steps == ["intake_agent", "risk_agent", "clearance_agent"]


@pytest.mark.anyio
async def test_non_invasive_visit_skips_clearance():
    thread = await AgenticSupervisor().run("pat-1", ["D1110"])
    assert thread.state["clearance_status"] == "NOT_REQUIRED"
    assert "clearance_agent" not in [e["node"] for e in thread.events]


@pytest.mark.anyio
async def test_deterministic_fallback_matches_langgraph():
    fallback = AgenticSupervisor()
    fallback.graph, fallback.engine = None, "deterministic"
    a = (await fallback.run("pat-1", ["D7140"])).state
    b = (await AgenticSupervisor().run("pat-1", ["D7140"])).state
    assert a["clearance_status"] == b["clearance_status"]
    assert sorted(l["action"] for l in a["agent_logs"]) == sorted(l["action"] for l in b["agent_logs"])


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_event_and_stream_endpoints():
    with TestClient(app) as client:
        assert client.get("/api/agents/status").json()["background_worker_running"] is True
        assert client.get("/api/agents/stream/nobody").status_code == 404
        assert client.post("/api/agents/events", json={"event_type": "nope", "patient_id": "pat-1"}).status_code == 400

        resp = client.post("/api/agents/events", json={"patient_id": "pat-1", "cdt_codes": ["D7140"]})
        assert resp.status_code == 202

        with client.stream("GET", "/api/agents/stream/pat-1") as stream:
            body = "".join(stream.iter_text())
        assert "event: thread_started" in body
        assert "event: thread_completed" in body
        assert body.count("event: agent_step") == 3

        state = client.get("/api/agents/state/pat-1").json()
        assert state["status"] == "COMPLETED"
        assert state["state"]["clearance_status"] == "TRANSMITTED_TO_EHR"
