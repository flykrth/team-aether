"""
MAO Assistant: tool layer and the Gemini function-calling loop (Gemini API mocked).
The multi-provider master, specialists, widgets and speech live in test_assistant_multi.py.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.assistant import AssistantError, AssistantNotConfigured, chat
from app.services.assistant import tools


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def only_test_keys(monkeypatch):
    """Whatever the developer's .env holds, these tests see no provider unless they set one."""
    for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY", "ASSISTANT_MASTER_PROVIDER", "NVIDIA_STT_URL"):
        monkeypatch.setattr(settings, name, "")


@pytest.fixture
def gemini_key(monkeypatch, only_test_keys):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")


# -- tools ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_patient_history_tool():
    history = await tools.get_patient_history("CS-9921")
    assert history["found"] and history["name"] == "Robert Chen"
    assert [c["code"] for c in history["conditions"]] == ["Z95.5", "I10"]
    assert {m["drug_class"] for m in history["medications"]} == {"antiplatelet"}
    assert history["dental"]["treatment_plan"][0]["cdt_code"] == "D7210"
    assert "raw_fhir_bundle" not in json.dumps(history)


@pytest.mark.anyio
async def test_patient_history_unknown_patient():
    assert (await tools.get_patient_history("nobody-here"))["found"] is False


@pytest.mark.anyio
async def test_risk_assessment_is_read_only():
    carestack = tools.carestack_services()
    before = len(carestack.PATIENT_MEDICAL_ALERTS.get("CS-9921", []))
    result = await tools.assess_clinical_risk("CS-9921", "d7210")
    assert result["hazard_level"] == "CRITICAL" and result["physician_clearance_required"]
    assert len(carestack.PATIENT_MEDICAL_ALERTS.get("CS-9921", [])) == before


@pytest.mark.anyio
async def test_action_tools_drive_the_workflow():
    run = await tools.execute_tool("run_agent_workflow", {"patient_id": "CS-9921", "cdt_code": "D7210"})
    assert run["clearance_status"] == "TRANSMITTED_TO_EHR"
    assert "commercial_claims" not in run and "cross_bill_eligible" not in run  # the billing path is gone
    reply = await tools.execute_tool("submit_physician_reply", {"patient_id": "CS-9921", "reply_text": "Cleared, maintain aspirin."})
    assert reply["appointment"]["status"] == "CLEARED_FOR_CARE"
    again = await tools.execute_tool("submit_physician_reply", {"patient_id": "CS-9921", "reply_text": "Cleared."})
    assert again["ok"] is False


@pytest.mark.anyio
async def test_tool_errors_are_returned_as_data():
    assert "error" in await tools.execute_tool("drop_database", {})
    assert "error" in await tools.execute_tool("get_patient_history", {"wrong": "arg"})


# -- Gemini loop -----------------------------------------------------------------------

def _mock_gemini(script, seen):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append({"headers": request.headers, "url": str(request.url), "body": json.loads(request.content)})
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": script[len(seen) - 1]}}]})
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.anyio
async def test_chat_runs_tool_then_answers(gemini_key):
    seen = []
    call_part = {"functionCall": {"name": "get_patient_history", "args": {"patient_id": "CS-9921"}}, "thoughtSignature": "sig-1"}
    client = _mock_gemini([[call_part], [{"text": "Robert Chen has a recent coronary stent."}]], seen)

    result = await chat([{"role": "user", "content": "What is Robert Chen's history?"}], "CS-9921", client=client)

    assert result["reply"] == "Robert Chen has a recent coronary stent."
    assert result["provider"] == "gemini" and result["specialists"] == []
    assert [w["type"] for w in result["widgets"]] == ["patient_summary"]
    assert result["actions"] == [{"tool": "get_patient_history", "args": {"patient_id": "CS-9921"}, "is_action": False, "ok": True}]
    assert seen[0]["headers"]["x-goog-api-key"] == "test-key" and "key=" not in seen[0]["url"]
    assert "CS-9921" in seen[0]["body"]["systemInstruction"]["parts"][0]["text"]
    follow_up = seen[1]["body"]["contents"]
    assert follow_up[1] == {"role": "model", "parts": [call_part]}  # echoed verbatim incl. thought signature
    tool_response = follow_up[2]["parts"][0]["functionResponse"]
    assert tool_response["name"] == "get_patient_history" and tool_response["response"]["name"] == "Robert Chen"


@pytest.mark.anyio
async def test_chat_stops_after_max_tool_rounds(gemini_key):
    seen = []
    loop_forever = [[{"functionCall": {"name": "list_patients", "args": {}}}]] * 20
    result = await chat([{"role": "user", "content": "loop"}], client=_mock_gemini(loop_forever, seen))
    assert len(seen) == 8 and "ran out of tool steps" in result["reply"]


@pytest.mark.anyio
async def test_chat_surfaces_api_errors(gemini_key):
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda r: httpx.Response(400, json={"error": {"message": "API key not valid."}})))
    with pytest.raises(AssistantError, match="400. API key not valid"):
        await chat([{"role": "user", "content": "hi"}], client=client)


@pytest.mark.anyio
async def test_chat_requires_key():
    with pytest.raises(AssistantNotConfigured):
        await chat([{"role": "user", "content": "hi"}])


def test_endpoints_without_key():
    with TestClient(app) as client:
        status = client.get("/api/assistant/status").json()
        assert status["configured"] is False and status["provider"] is None
        assert len(status["tools"]) == len(tools.TOOL_DECLARATIONS) == 24
        resp = client.post("/api/assistant/chat", json={"messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 503 and "GEMINI_API_KEY" in resp.json()["detail"]


@pytest.mark.anyio
async def test_transient_gemini_errors_are_retried(gemini_key, monkeypatch):
    from app.services.assistant import gemini
    monkeypatch.setattr(gemini, "RETRY_DELAYS", (0, 0))
    statuses = iter([503, 429, 200])
    calls = []

    def handler(request):
        status = next(statuses)
        calls.append(status)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "This model is currently experiencing high demand."}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Back."}]}}]})

    result = await chat([{"role": "user", "content": "hi"}], client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert result["reply"] == "Back." and calls == [503, 429, 200]


@pytest.mark.anyio
async def test_persistent_gemini_outage_still_surfaces(gemini_key, monkeypatch):
    from app.services.assistant import gemini
    monkeypatch.setattr(gemini, "RETRY_DELAYS", (0, 0))
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503, json={"error": {"message": "high demand"}})))
    with pytest.raises(AssistantError, match="503"):
        await chat([{"role": "user", "content": "hi"}], client=client)
