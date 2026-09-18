"""
Dental Coverage Recovery Agent. These tests pin the "does not bullshit" guarantees:
quotes are verified, unknown stays unknown, the model cannot move the outcome, no money is invented.
A tiny fictional policy is used as a fixture; no real payer text lives in the repo and no network is used.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services import patient_registry
from app.services.coverage import analyst, case, packet, plans, policy_store, retrieval

POLICY = """## Policy
### Removal of Impacted Teeth
The removal of bone-impacted teeth may be covered under some Testcare medical plans. Standard HMO plans exclude removal of impacted teeth. Standard PPO plans cover the surgical removal of bone impacted teeth when there is documented recurrent infection.
### Policy Limitations and Exclusions
Dental services provided for the routine care, treatment, or replacement of teeth (e.g., root canals, fillings, crowns, bridges) are generally excluded from coverage. Removal of teeth at risk of infection is not covered under medical plans.
### Treatment of Jaw
Reduction of any facial bone fractures is covered under all Testcare medical plans.
## CPT Codes / ICD-10 Codes
CDT codes covered if selection criteria are met: D7240 Removal of impacted tooth, completely bony.
## Background
A large literature review suggests every dental procedure is medically necessary and should always be covered.
"""
PLAN_EXCLUDING = "Summary of Benefits. " + "General plan wording. " * 12 + "Exclusions: Removal of impacted teeth is not covered under this plan. Oral surgery requires precertification."
PLAN_SILENT = "Summary of Benefits. " + "General plan wording about deductibles and copayments. " * 12


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A one-document policy library and an isolated patient registry."""
    monkeypatch.setenv("MDIN_POLICY_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("MDIN_RUNTIME_REGISTRY", str(tmp_path / "registry.json"))
    registry = {"regions": {"US": {"label": "US", "supported": True}, "UK": {"label": "UK", "supported": False, "note": "Not implemented yet."}},
                "sources": [{"id": "testcare-oral", "region": "US", "insurer": "Testcare", "title": "Testcare oral surgery policy", "kind": "html", "url": "https://example.test/policy"}]}
    monkeypatch.setattr(policy_store, "load_registry", lambda: registry)
    source = registry["sources"][0]
    record = {**source, "ok": True, "fetched_at": "2026-09-01T00:00:00+00:00", "review": "Last Review: 08/01/2026", "chunks": policy_store.chunk_document(source, POLICY)}
    with open(policy_store._paths("testcare-oral")["parsed"], "w") as f:
        json.dump(record, f)
    patient_registry.load_runtime_registry()
    pid = patient_registry.create_patient("Cover", "Agecase", "1975-05-05")["patient_id"]
    plans.set_insurance(pid, dental={"status": "exhausted"}, medical={"insurer": "Testcare", "plan_name": "Choice PPO", "plan_type": "PPO"})
    yield pid
    patient_registry.remove_patient(pid)
    monkeypatch.delenv("MDIN_RUNTIME_REGISTRY")
    patient_registry.load_runtime_registry()


def _llm(monkeypatch, criteria):
    """A model that answers with exactly these criteria (passage ids are resolved by heading)."""
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    def handler(request):
        body = json.loads(request.content)
        prompt = body["contents"][0]["parts"][0]["text"]
        if "PASSAGES" not in prompt:  # the first model call reads the clinical note; leave that to the rule pass
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})
        resolved = []
        for c in criteria:
            marker, fact = c.get("in"), c.get("fact_contains")
            pid = next((line.split(" ")[0] for line in prompt.splitlines() if line.startswith("P") and marker and marker in line), "P1")
            fid = next((line.split(":")[0] for line in prompt.splitlines() if line.startswith("F") and fact and fact in line), None)
            resolved.append({**{k: v for k, v in c.items() if k not in ("in", "fact_contains")}, "passage": pid, "fact": fid})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps({"criteria": resolved, "summary": "s"})}]}}]})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


IMPACTED = {"procedure": "D7240", "diagnosis": "impacted third molar", "region": "US",
            "clinical_note": "Completely bony impacted lower third molar. Recurrent infection with swelling, three episodes."}
SUPPORT = {"in": "Removal of Impacted Teeth", "kind": "supports", "requirement": "PPO plans cover bone impacted teeth with recurrent infection",
           "quote": "Standard PPO plans cover the surgical removal of bone impacted teeth when there is documented recurrent infection.",
           "applies_to_case": True, "met": "yes", "fact_contains": "Infection beyond the tooth"}


# -- the policy store never offers background text as policy ---------------------------------------

def test_background_sections_are_not_retrievable(library):
    chunks = policy_store.all_chunks("US")
    assert chunks and not any("literature review" in c["text"] for c in chunks)
    assert any(c["kind"] == "codes" and "D7240" in c["codes"]["cdt"] for c in chunks)


@pytest.mark.anyio
async def test_retrieval_works_without_an_embedding_key(library):
    found = await retrieval.search("routine crown filling", "US", ["Testcare"], ["D2740"])
    assert found["mode"] == "lexical" and "generally excluded" in found["passages"][0]["text"]


# -- dental first ------------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_active_dental_benefit_never_attempts_the_medical_route(library):
    plans.set_insurance(library, dental={"status": "active"})
    result = await analyst.analyze({**IMPACTED, "patient_id": library})
    assert result["determination"]["outcome"] == "dental_active" and result["criteria"] == []
    assert [s["node"] for s in result["steps"]] == ["dental_benefits", "normal_workflow"]


@pytest.mark.anyio
async def test_unsupported_region_says_so_instead_of_guessing(library):
    result = await analyst.analyze({**IMPACTED, "patient_id": library, "region": "UK"})
    assert result["determination"]["outcome"] == "unsupported_region"


# -- grounding -----------------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_invented_quote_is_dropped_and_cannot_create_a_pathway(library, monkeypatch):
    fake = {**SUPPORT, "quote": "All oral surgery is always covered under every Testcare medical plan without conditions."}
    result = await analyst.analyze({**IMPACTED, "patient_id": library}, client=_llm(monkeypatch, [fake]))
    assert result["dropped_ungrounded"] == 1 and result["criteria"] == []
    assert result["determination"]["outcome"] != "potential_pathway"


@pytest.mark.anyio
async def test_met_without_a_case_fact_becomes_unknown_and_goes_to_review(library, monkeypatch):
    claim = {**SUPPORT, "fact_contains": "this fact does not exist"}
    result = await analyst.analyze({**IMPACTED, "patient_id": library}, client=_llm(monkeypatch, [claim]))
    assert result["criteria"][0]["met"] == "unknown"
    assert result["determination"]["outcome"] == "needs_review" and result["missing_information"]


# -- outcomes --------------------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_supported_case_without_a_plan_document_is_only_unverified(library, monkeypatch):
    result = await analyst.analyze({**IMPACTED, "patient_id": library}, client=_llm(monkeypatch, [dict(SUPPORT)]))
    d = result["determination"]
    assert d["outcome"] == "potential_pathway" and d["plan_verified"] is False and "plan not verified" in d["headline"].lower()
    assert result["criteria"][0]["source"]["url"] == "https://example.test/policy" and result["criteria"][0]["source"]["review"]
    assert result["code_tables"][0]["listed_under"].startswith("CDT codes covered if selection criteria are met")


@pytest.mark.anyio
async def test_member_plan_exclusion_beats_the_payer_policy(library, monkeypatch):
    plans.set_plan_document(library, "SBC", PLAN_EXCLUDING)
    exclusion = {"in": "Member plan document", "kind": "excludes", "requirement": "plan excludes impacted teeth",
                 "quote": "Removal of impacted teeth is not covered under this plan.", "applies_to_case": True, "met": "unknown"}
    result = await analyst.analyze({**IMPACTED, "patient_id": library}, client=_llm(monkeypatch, [dict(SUPPORT), exclusion]))
    assert result["determination"]["outcome"] == "no_pathway" and "plan document excludes" in result["determination"]["reason"]


@pytest.mark.anyio
async def test_plan_verified_only_when_a_plan_document_was_read(library, monkeypatch):
    plans.set_plan_document(library, "SBC", PLAN_SILENT)
    result = await analyst.analyze({**IMPACTED, "patient_id": library}, client=_llm(monkeypatch, [dict(SUPPORT)]))
    assert result["determination"] == {**result["determination"], "outcome": "potential_pathway", "plan_verified": True}


@pytest.mark.anyio
async def test_routine_crown_is_no_pathway_with_the_payers_own_words(library, monkeypatch):
    exclusion = {"in": "Policy Limitations and Exclusions", "kind": "excludes", "requirement": "routine crowns are excluded",
                 "quote": "Dental services provided for the routine care, treatment, or replacement of teeth (e.g., root canals, fillings, crowns, bridges) are generally excluded from coverage.",
                 "applies_to_case": True, "met": "unknown"}
    result = await analyst.analyze({"procedure": "crown", "patient_id": library, "clinical_note": "Fractured cusp, needs a crown."},
                                   client=_llm(monkeypatch, [exclusion]))
    assert result["determination"]["outcome"] == "no_pathway"
    assert "generally excluded" in result["criteria"][0]["quote"]


@pytest.mark.anyio
async def test_without_a_language_model_it_shows_passages_and_asks_a_human(library):
    result = await analyst.analyze({**IMPACTED, "patient_id": library})
    assert result["determination"]["outcome"] == "needs_review" and result["model"] is None
    assert result["passages"] and result["criteria"] == []


@pytest.mark.anyio
async def test_a_risky_medical_history_is_not_a_medical_indication(library, monkeypatch):
    """The case the old billing agent monetised: an extraction for a patient with a stent."""
    patient_registry.add_history_entries(library, [{"type": "condition", "text": "coronary stent"}, {"type": "medication", "text": "clopidogrel"}])
    exclusion = {"in": "Policy Limitations and Exclusions", "kind": "excludes", "requirement": "teeth at risk of infection not covered",
                 "quote": "Removal of teeth at risk of infection is not covered under medical plans.", "applies_to_case": True, "met": "unknown"}
    result = await analyst.analyze({"procedure": "surgical extraction", "patient_id": library, "clinical_note": "Non-restorable tooth 19."},
                                   client=_llm(monkeypatch, [exclusion]))
    assert result["determination"]["outcome"] == "no_pathway"
    assert all(v["value"] is None for v in result["facts"]["flags"].values())  # nothing was inferred from the stent


def test_no_money_and_no_cpt_is_ever_invented(library):
    determination = analyst.determine([], {"pathway": "plan_dependent", "categories": []}, False, True, True)
    blob = json.dumps(determination)
    assert "$" not in blob and "saving" not in blob.lower() and "covered under" not in blob.lower()
    for outcome_fn in (lambda: analyst.determine([], {"pathway": "usually_dental", "categories": []}, False, True, True),):
        assert outcome_fn()["outcome"] == "no_pathway"


# -- case facts ------------------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_unknown_stays_unknown_and_negation_is_respected(library):
    facts = await case.build({"procedure": "D7240", "clinical_note": "Impacted third molar. No trauma. Patient denies any swelling."}, None)
    assert facts["flags"]["impacted_tooth"]["value"] is True
    assert facts["flags"]["trauma"]["value"] is False
    assert facts["flags"]["tmj"]["value"] is None and facts["flags"]["sleep_apnea"]["value"] is None
    staff = await case.build({"procedure": "D7240", "clinical_note": "No trauma.", "flags": {"trauma": True}}, None)
    assert staff["flags"]["trauma"] == {**staff["flags"]["trauma"], "value": True, "by": "staff"}


@pytest.mark.anyio
async def test_restricted_opening_from_an_infection_is_not_a_tmj_case(library):
    facts = await case.build({"procedure": "D7240", "clinical_note": "Pericoronitis with restricted opening."}, None)
    assert facts["flags"]["tmj"]["value"] is None
    assert [c["id"] for c in case.classify(facts)["categories"]] == ["infection"]


# -- packet + API ------------------------------------------------------------------------------------------

@pytest.mark.anyio
async def test_packet_needs_a_named_reviewer_and_cites_the_policy(library, monkeypatch):
    result = await analyst.analyze({**IMPACTED, "patient_id": library}, client=_llm(monkeypatch, [dict(SUPPORT)]))
    packet.remember(result)
    with pytest.raises(ValueError, match="named person"):
        packet.build(library, "")
    doc = packet.build(library, "Dr. Sarah Mitchell")
    assert doc["document_type"] == "Pre-Treatment Estimate Request"
    assert "Standard PPO plans cover the surgical removal" in doc["content_markdown"] and "https://example.test/policy" in doc["content_markdown"]
    assert "not a claim" in doc["content_markdown"] and "certified coder" in doc["content_markdown"]


def test_api_insurance_sources_and_errors(library):
    with TestClient(app) as client:
        sources = client.get("/api/coverage/sources").json()
        assert sources["insurers"] == ["Testcare"] and sources["sources"][0]["cached"] is True and sources["regions"]["UK"]["supported"] is False
        assert client.put(f"/api/coverage/patients/{library}/insurance", json={"dental": {"status": "bogus"}}).status_code == 422
        assert client.put(f"/api/coverage/patients/{library}/insurance", json={"dental": {"status": "denied", "note": "frequency"}}).json()["dental"]["status"] == "denied"
        assert client.get("/api/coverage/patients/nobody/insurance").status_code == 404
        assert client.post("/api/coverage/packet", json={"patient_id": library}).status_code in (404, 422)
        run = client.post("/api/coverage/analyze", json={"patient_id": library, "procedure": "D7240"}).json()
        assert run["determination"]["outcome"] == "needs_review"


@pytest.mark.anyio
async def test_failed_source_fetch_is_reported_not_hidden(library):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    rows = await policy_store.refresh("US", client=client)
    assert rows[0]["ok"] is True and "HTTP 404" in rows[0]["refresh_error"]  # last good copy kept, failure shown
    assert "HTTP 404" in policy_store.status("US")[0]["error"]


def test_ellipsis_quotes_need_every_segment_verbatim_and_in_order():
    text = "This plan covers medically necessary oral surgery performed by a dentist, including treatment of fractures, and surgical removal of impacted teeth."
    ok = analyst._quoted_from
    assert ok("This plan covers medically necessary oral surgery", text)
    assert ok("This plan covers medically necessary oral surgery ... surgical removal of impacted teeth.", text)
    assert ok("This plan covers medically necessary oral surgery… surgical removal of impacted teeth", text)
    assert not ok("surgical removal of impacted teeth ... This plan covers medically necessary oral surgery", text)  # wrong order
    assert not ok("This plan covers medically necessary oral surgery ... and cosmetic veneers", text)               # one segment invented
    assert not ok("This plan covers all dental care", text)
    assert not ok("... teeth", text)                                                                                   # too little to mean anything


@pytest.mark.anyio
async def test_a_general_exception_does_not_turn_routine_care_into_a_review(library, monkeypatch):
    """Found live: a crown for a patient on warfarin went to review because the model noticed the payer's general exception."""
    patient_registry.add_history_entries(library, [{"type": "medication", "text": "warfarin"}])
    exception = {"in": "Removal of Impacted Teeth", "kind": "supports", "requirement": "may be covered under some plans",
                 "quote": "The removal of bone-impacted teeth may be covered under some Testcare medical plans.",
                 "applies_to_case": True, "met": "unknown"}
    exclusion = {"in": "Policy Limitations and Exclusions", "kind": "excludes", "requirement": "routine crowns are excluded",
                 "quote": "are generally excluded from coverage", "applies_to_case": True, "met": "unknown"}
    result = await analyst.analyze({"procedure": "crown", "patient_id": library, "clinical_note": "Fractured cusp, needs a crown."},
                                   client=_llm(monkeypatch, [exception, exclusion]))
    assert result["determination"]["outcome"] == "no_pathway"
    assert "record that and run the check again" in result["determination"]["reason"]
    # ...but the moment staff record a real indication, the same supporting language is weighed normally
    flagged = await analyst.analyze({"procedure": "crown", "patient_id": library, "clinical_note": "Fractured cusp.", "flags": {"trauma": True}},
                                    client=_llm(monkeypatch, [exception, exclusion]))
    assert flagged["determination"]["outcome"] == "needs_review"


def _crit(kind, met, heading, source="pol", plan=False, **extra):
    return {"kind": kind, "met": met, "applies_to_case": True, "requirement": "r", "quote": "q", "fact": None, "negates_pathway": True,
            "source": {"id": source, "heading": heading, "is_member_plan": plan}, **extra}


def test_routes_are_alternatives_one_fully_met_route_is_enough():
    """Found live on a patient with a medical history: the 'integral to medical procedure' route surfaced with an unanswered
    condition and dragged a fully met 'impacted teeth' route into review."""
    plan_dependent = {"pathway": "plan_dependent", "categories": []}
    met_route = _crit("supports", "yes", "Removal of Impacted Teeth")
    other_route = _crit("supports", "unknown", "Dental Services Integral to Medical Procedures")
    assert analyst.determine([met_route, other_route], plan_dependent, False, True, True)["outcome"] == "potential_pathway"
    # ...but a route is only satisfied when ALL of its own conditions are met
    same_route_gap = _crit("supports", "unknown", "Removal of Impacted Teeth")
    assert analyst.determine([met_route, same_route_gap], plan_dependent, False, True, True)["outcome"] == "needs_review"
    assert analyst.determine([_crit("supports", "no", "Removal of Impacted Teeth")], plan_dependent, False, True, True)["outcome"] == "no_pathway"


def test_exclusions_block_unless_clearly_about_another_route():
    plan_dependent = {"pathway": "plan_dependent", "categories": []}
    met_route = _crit("supports", "yes", "Removal of Impacted Teeth")
    doubtful = _crit("excludes", "unknown", "Policy Limitations")                      # negates_pathway defaults to True
    unrelated = _crit("excludes", "unknown", "Dental Services Not Integral", negates_pathway=False)
    same_section = _crit("excludes", "unknown", "Removal of Impacted Teeth", negates_pathway=False)
    from_plan = _crit("excludes", "unknown", "Exclusions", source="plan:x", plan=True, negates_pathway=False)
    assert analyst.determine([met_route, doubtful], plan_dependent, False, True, True)["outcome"] == "needs_review"
    assert analyst.determine([met_route, unrelated], plan_dependent, False, True, True)["outcome"] == "potential_pathway"
    assert analyst.determine([met_route, same_section], plan_dependent, False, True, True)["outcome"] == "needs_review"
    assert analyst.determine([met_route, from_plan], plan_dependent, True, True, True)["outcome"] == "no_pathway"  # the plan always wins
