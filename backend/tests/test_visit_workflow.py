"""
The whole workflow, end to end: add a patient -> history -> risk check (starts the visit and keeps the context)
-> procedure done -> insurance (dental first, then a medical pathway) -> document -> close.
Once over the API as the UI uses it, once through the assistant's tools as the chat uses them.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import patient_registry, visits
from app.services.assistant import tools
from app.services.assistant.context import turn_attachments, turn_last_user_message
from app.services.coverage import plans, policy_store

POLICY = """## Policy
### Removal of Impacted Teeth
Standard PPO plans cover the surgical removal of bone impacted teeth when there is documented recurrent infection.
### Policy Limitations and Exclusions
Dental services provided for the routine care, treatment, or replacement of teeth (e.g., fillings, crowns) are generally excluded from coverage.
"""
NOTES = "Completely bony impacted lower third molar. Recurrent infection with swelling. Started warfarin last month."


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("MDIN_POLICY_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("MDIN_RUNTIME_REGISTRY", str(tmp_path / "registry.json"))
    registry = {"regions": {"US": {"label": "US", "supported": True}},
                "sources": [{"id": "testcare", "region": "US", "insurer": "Testcare", "title": "Testcare oral surgery policy", "kind": "html", "url": "https://example.test/p"}]}
    monkeypatch.setattr(policy_store, "load_registry", lambda: registry)
    source = registry["sources"][0]
    with open(policy_store._paths("testcare")["parsed"], "w") as f:
        json.dump({**source, "ok": True, "fetched_at": "2026-09-01T00:00:00+00:00", "review": "Last Review: 08/01/2026",
                   "chunks": policy_store.chunk_document(source, POLICY)}, f)
    patient_registry.load_runtime_registry()
    created = []
    yield created
    for pid in created:
        plans.forget(pid); visits.forget(pid); patient_registry.remove_patient(pid)
    monkeypatch.delenv("MDIN_RUNTIME_REGISTRY")
    patient_registry.load_runtime_registry()


def _model(monkeypatch):
    """A model that, asked to analyse passages, cites the impacted-teeth sentence against the infection fact."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    quote = "Standard PPO plans cover the surgical removal of bone impacted teeth when there is documented recurrent infection."

    def handler(request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        if "PASSAGES" not in prompt:
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})
        pid = next(l.split(" ")[0] for l in prompt.splitlines() if l.startswith("P") and "Removal of Impacted Teeth" in l)
        fid = next(l.split(":")[0] for l in prompt.splitlines() if l.startswith("F") and "Infection beyond the tooth" in l)
        body = {"criteria": [{"passage": pid, "quote": quote, "kind": "supports", "requirement": "PPO covers impacted teeth with infection",
                              "applies_to_case": True, "met": "yes", "fact": fid}], "summary": "s"}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(body)}]}}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: real(transport=httpx.MockTransport(handler)))


def test_whole_workflow_over_the_api(world, monkeypatch):
    _model(monkeypatch)
    with TestClient(app) as client:
        # 1. add the patient, 2. load history
        pid = client.post("/api/records/patients", json={"first_name": "Flow", "last_name": "Through", "birth_date": "1970-01-01"}).json()["patient_id"]
        world.append(pid)
        client.post(f"/api/records/patients/{pid}/history", json={"entries": [{"type": "condition", "text": "hypertension"}]})
        assert client.get(f"/api/visits/patients/{pid}").json()["next_step"]["stage"] == "none"
        assert client.post(f"/api/visits/patients/{pid}/procedure-done", json={}).status_code == 409  # nothing to mark done yet

        # 3. risk check: starts the visit and keeps what was said
        risk = client.post("/api/risk/check", json={"patient_id": pid, "procedure": "D7240 bony impacted third molar", "current_notes": NOTES,
                                                    "include_evidence": False, "include_ai": False}).json()
        assert risk["hazard_level"] == "CRITICAL" and risk["visit"]["stage"] == "risk_checked"
        view = client.get(f"/api/visits/patients/{pid}").json()
        assert view["visit"]["todays_notes"] == NOTES and view["visit"]["risk"]["physician_clearance_required"] is True
        assert "clearance" in view["next_step"]["next"].lower()

        # 4. the procedure happens
        view = client.post(f"/api/visits/patients/{pid}/procedure-done", json={"outcome_note": "Uneventful."}).json()
        assert view["next_step"]["stage"] == "procedure_done" and "dental benefit" in view["next_step"]["next"]

        # 5a. dental benefit active -> bill dental, no medical question asked
        client.put(f"/api/coverage/patients/{pid}/insurance", json={"dental": {"status": "active"}})
        assert client.post("/api/coverage/analyze", json={"patient_id": pid}).json()["determination"]["outcome"] == "dental_active"

        # 5b. dental exhausted -> medical pathway, WITHOUT retyping the procedure or the notes: the visit supplies them
        client.put(f"/api/coverage/patients/{pid}/insurance", json={"dental": {"status": "exhausted"}, "medical": {"insurer": "Testcare", "plan_type": "PPO"}})
        result = client.post("/api/coverage/analyze", json={"patient_id": pid}).json()
        assert result["facts"]["procedure"]["cdt_code"] == "D7240" and "Recurrent infection" in result["facts"]["clinical_note"]
        assert result["determination"]["outcome"] == "potential_pathway"
        assert result["visit"]["stage"] == "insurance_checked" and result["visit"]["insurance"]["medical_insurer"] == "Testcare"

        # 6. paperwork, then close
        document = client.post("/api/coverage/packet", json={"patient_id": pid, "reviewed_by": "Dr. Mitchell"}).json()
        assert document["document_type"] == "Pre-Treatment Estimate Request"
        view = client.post(f"/api/visits/patients/{pid}/close", json={}).json()
        assert view["visit"] is None and view["past_visits"][0]["documents"][0]["document_id"] == document["document_id"]
        assert client.post("/api/coverage/analyze", json={"patient_id": pid}).status_code == 422  # no visit, no procedure: says so


@pytest.mark.anyio
async def test_whole_workflow_through_the_chat_tools(world, monkeypatch):
    _model(monkeypatch)
    run = tools.execute_tool
    created = await run("create_patient", {"first_name": "Chat", "last_name": "Driven", "birth_date": "1968-02-02",
                                           "history": [{"type": "condition", "text": "hypertension"}]})
    pid = created["patient_id"]; world.append(pid)

    risk = await run("assess_clinical_risk", {"patient_id": pid, "procedure": "remove the bony impacted wisdom tooth", "todays_notes": NOTES})
    assert risk["hazard_level"] == "CRITICAL" and risk["next_step"]["stage"] == "risk_checked"

    assert (await run("get_visit", {"patient_id": pid}))["visit"]["procedure"]["cdt_code"] == "D7240"
    assert (await run("mark_procedure_done", {"patient_id": pid}))["next_step"]["stage"] == "procedure_done"

    saved = await run("set_patient_insurance", {"patient_id": pid, "dental_status": "exhausted", "medical_insurer": "testcare", "plan_type": "PPO"})
    assert saved["insurance"] == {"dental_status": "exhausted", "medical_insurer": "Testcare", "plan_type": "PPO", "plan_document": None}

    coverage = await run("check_medical_coverage_pathway", {"patient_id": pid})   # no procedure passed: the visit has it
    assert coverage["outcome"] == "potential_pathway" and coverage["policy_quotes"][0]["url"] == "https://example.test/p"

    assert (await run("create_coverage_document", {"patient_id": pid}))["ok"] is False           # nobody signed it off
    assert (await run("create_coverage_document", {"patient_id": pid, "reviewed_by": "Dr. Mitchell"}))["ok"] is True
    assert (await run("close_visit", {"patient_id": pid}))["visit"] is None


@pytest.mark.anyio
async def test_plan_document_from_chat_needs_the_user_to_ask(world):
    pid = patient_registry.create_patient("Plan", "Attach", "1980-03-03")["patient_id"]; world.append(pid)
    attachment = [{"filename": "sbc.pdf", "text": "Summary of Benefits. " + "Plan wording. " * 30}]
    tokens = (turn_attachments.set(attachment), turn_last_user_message.set("what does this say?"))
    try:
        assert (await tools.execute_tool("attach_plan_document", {"patient_id": pid}))["ok"] is False
        turn_last_user_message.set("use this as her plan document")
        assert (await tools.execute_tool("attach_plan_document", {"patient_id": pid}))["insurance"]["plan_document"] == "sbc.pdf"
    finally:
        turn_attachments.reset(tokens[0]); turn_last_user_message.reset(tokens[1])


def test_a_different_procedure_starts_a_new_visit(world):
    pid = patient_registry.create_patient("Two", "Visits", "1980-04-04")["patient_id"]; world.append(pid)
    first = visits.record_risk_check(pid, {"procedure": {"cdt_code": "D7240", "label": "Impacted"}, "hazard_level": "LOW", "physician_clearance_required": False}, "a")
    same = visits.record_risk_check(pid, {"procedure": {"cdt_code": "D7240", "label": "Impacted"}, "hazard_level": "LOW", "physician_clearance_required": False}, "b")
    other = visits.record_risk_check(pid, {"procedure": {"cdt_code": "D2740", "label": "Crown"}, "hazard_level": "LOW", "physician_clearance_required": False}, "c")
    assert first["visit_id"] == same["visit_id"] != other["visit_id"] and same["todays_notes"] == "b"
    assert [v["stage"] for v in visits.history(pid)] == ["risk_checked", "closed"]


def test_every_widget_type_has_a_title_and_a_card():
    """Found live: two new widget types had no title and the chat turn crashed."""
    import os, re
    from app.services.assistant import orchestrator
    assert set(orchestrator.WIDGET_TYPES.values()) <= set(orchestrator._WIDGET_TITLES)
    registry = open(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src", "components", "assistant", "widgets", "index.jsx")).read()
    block = registry[registry.index("export const WIDGET_REGISTRY"):registry.index("};", registry.index("export const WIDGET_REGISTRY"))]
    assert set(orchestrator.WIDGET_TYPES.values()) <= set(re.findall(r"^\s*([a-z_]+):", block, re.M))


@pytest.mark.anyio
async def test_no_paperwork_for_a_case_that_needs_review(world):
    pid = patient_registry.create_patient("Needs", "Review", "1981-05-05")["patient_id"]; world.append(pid)
    visits.record_risk_check(pid, {"procedure": {"cdt_code": "D7240", "label": "Impacted", "input": "D7240"}, "hazard_level": "LOW", "physician_clearance_required": False}, "")
    visits.mark_procedure_done(pid)
    visits.record_insurance_check(pid, {"determination": {"outcome": "needs_review", "headline": "Needs human review", "reason": "r"},
                                        "insurance": {"dental": {"status": "exhausted"}, "medical": {"insurer": "Testcare"}}, "criteria": []})
    refused = await tools.execute_tool("create_coverage_document", {"patient_id": pid, "reviewed_by": "Dr. Mitchell"})
    assert refused["ok"] is False and "NOT a confirmed pathway" in refused["message"]
    assert visits.current(pid)["stage"] == "procedure_done"  # a review outcome does not settle insurance


@pytest.mark.anyio
async def test_the_model_cannot_invent_a_procedure_code(world):
    """Found live: the model passed 'D7241', which the user never said, and the outcome changed with it."""
    from app.services.assistant.context import turn_user_text
    pid = patient_registry.create_patient("Code", "Guard", "1982-06-06")["patient_id"]; world.append(pid)
    said = "She needs a completely bony impacted third molar taken out."
    tokens = (turn_user_text.set(said), turn_last_user_message.set(said))
    try:
        invented = await tools.execute_tool("assess_clinical_risk", {"patient_id": pid, "procedure": "D7241"})
        assert invented["cdt_code"] == "D7240"           # resolved from the user's words by the rules, not the model's code
        mixed = await tools.execute_tool("assess_clinical_risk", {"patient_id": pid, "procedure": "surgical extraction (D7241) of impacted wisdom tooth"})
        assert mixed["cdt_code"] == "D7240"
        turn_user_text.set("Check the risk for a D7210."); turn_last_user_message.set("Check the risk for a D7210.")
        assert (await tools.execute_tool("assess_clinical_risk", {"patient_id": pid, "procedure": "D7210"}))["cdt_code"] == "D7210"  # the user said it
    finally:
        turn_user_text.reset(tokens[0]); turn_last_user_message.reset(tokens[1])


@pytest.mark.anyio
async def test_the_no_pathway_explanation_can_be_filed_from_chat(world, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    real = httpx.AsyncClient
    quote = "Dental services provided for the routine care, treatment, or replacement of teeth (e.g., fillings, crowns) are generally excluded from coverage."

    def handler(request):
        prompt = json.loads(request.content)["contents"][0]["parts"][0]["text"]
        if "PASSAGES" not in prompt:
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})
        pid_ = next(l.split(" ")[0] for l in prompt.splitlines() if l.startswith("P") and "Limitations" in l)
        body = {"criteria": [{"passage": pid_, "quote": quote, "kind": "excludes", "requirement": "routine care excluded", "applies_to_case": True, "met": "unknown"}]}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(body)}]}}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: real(transport=httpx.MockTransport(handler)))
    pid = patient_registry.create_patient("Crown", "Case", "1983-07-07")["patient_id"]; world.append(pid)
    await tools.execute_tool("assess_clinical_risk", {"patient_id": pid, "procedure": "crown"})
    await tools.execute_tool("mark_procedure_done", {"patient_id": pid})
    await tools.execute_tool("set_patient_insurance", {"patient_id": pid, "dental_status": "denied", "medical_insurer": "Testcare"})
    assert (await tools.execute_tool("check_medical_coverage_pathway", {"patient_id": pid}))["outcome"] == "no_pathway"
    document = await tools.execute_tool("create_coverage_document", {"patient_id": pid})
    assert document["ok"] is True and document["document_type"] == "Coverage Explanation" and "generally excluded" in document["preview"]
