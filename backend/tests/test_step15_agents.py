"""
Step 15: the four specialized MAO agents and the LangGraph state graph.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.agent_state import create_initial_state, validate_state
from app.services.agent_supervisor import AgenticSupervisor, route_after_risk
from app.services.agents import ClinicalRiskAgent, IntakeAgent, MedicalClearanceAgent

ENDORSEMENT = "Cleared for extractions, keep epinephrine minimal, limit to 2 carpules 1:100k epi, maintain Aspirin"
NARRATIVE = "Patient reports taking Alendronate for 4 years, had a cardiac stent placed 8 months ago"


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _state_with(concepts, cdt="D7210"):
    state = create_initial_state("unit-test", cdt_codes=[cdt])
    state["medical_records"]["normalized_concepts"] = concepts
    return state


# -- Intake ---------------------------------------------------------------------

def test_intake_narrative_normalization():
    concepts = IntakeAgent().extract_from_narrative(NARRATIVE, today=date(2026, 9, 18))
    by_code = {c["code"]: c for c in concepts}
    assert set(by_code) == {"Z95.5", "46041"}
    assert by_code["46041"]["drug_class"] == "bisphosphonate"
    assert by_code["46041"]["duration_text"] == "for 4 years"
    assert by_code["Z95.5"]["onset"] == "2026-01-21"  # 8 * 30 days before today


@pytest.mark.anyio
async def test_intake_unlinked_patient_uses_conversational_extraction():
    state = create_initial_state("no-such-patient", cdt_codes=["D7210"], simulation={"intake_narrative": NARRATIVE})
    update = await IntakeAgent()(state)
    assert update["intake_status"] == "CONVERSATIONAL_EXTRACTED"
    assert any(c.startswith("Z95.5") for c in update["medical_records"]["conditions"])


@pytest.mark.anyio
async def test_intake_without_any_data_stays_pending():
    update = await IntakeAgent()(create_initial_state("no-such-patient"))
    assert update["intake_status"] == "PENDING"
    assert update["medical_records"]["normalized_concepts"] == []


# -- Risk -------------------------------------------------------------------------

STENT = {"type": "condition", "system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "Z95.5", "display": "Coronary stent"}


def test_risk_recent_stent_is_critical_for_surgery_only():
    recent = dict(STENT, onset=date.today().replace(day=1).isoformat())
    agent = ClinicalRiskAgent()
    surgical = agent.evaluate(_state_with([recent]), "D7210")
    assert surgical["hazard_level"] == "CRITICAL"
    assert any("2 carpules" in r for r in surgical["clinical_recommendations"])
    assert agent.evaluate(_state_with([recent]), "D1110")["hazard_level"] == "MODERATE"


def test_risk_old_stent_is_not_critical():
    old = dict(STENT, onset="2015-01-01")
    assert ClinicalRiskAgent().evaluate(_state_with([old]), "D7210")["hazard_level"] == "MODERATE"


def test_risk_bisphosphonate_and_anticoagulant_rules():
    meds = [
        {"type": "medication", "code": "46041", "display": "Alendronate (Fosamax)"},
        {"type": "medication", "code": "11289", "display": "Warfarin (Coumadin)"},
    ]
    result = ClinicalRiskAgent().evaluate(_state_with(meds), "D7240")
    assert result["hazard_level"] == "CRITICAL"
    assert result["triggered_rules"] == ["BISPHOSPHONATE_MRONJ", "ANTICOAGULANT_HEMORRHAGE"]


def test_risk_clean_history_is_low():
    assert ClinicalRiskAgent().evaluate(_state_with([]), "D7210")["hazard_level"] == "LOW"


# -- Clearance ----------------------------------------------------------------------

def test_parse_physician_endorsement_spec_example():
    parsed = MedicalClearanceAgent().parse_physician_endorsement(ENDORSEMENT)
    assert parsed["restrictions"] == ["LIMIT_EPINEPHRINE_2_CARPULES", "MAINTAIN_ASPIRIN"]
    assert parsed["decision"] == "APPROVED_WITH_CONDITIONS"
    assert parsed["hold_medications"] is False


@pytest.mark.parametrize("text,decision,expected", [
    ("Approved. Hold warfarin for 48 hours, INR target below 2.5.", "APPROVED_WITH_CONDITIONS", ["HOLD_WARFARIN_48H"]),
    ("Cleared. Do not stop Plavix. No epinephrine.", "APPROVED_WITH_CONDITIONS", ["AVOID_EPINEPHRINE", "MAINTAIN_CLOPIDOGREL"]),
    ("Patient is cleared for the procedure.", "APPROVED", []),
    ("Not cleared - defer procedure until 12 months post-stent.", "REJECTED", []),
    ("Will review the chart next week.", "UNDETERMINED", []),
])
def test_parse_physician_endorsement_variants(text, decision, expected):
    parsed = MedicalClearanceAgent().parse_physician_endorsement(text)
    assert parsed["decision"] == decision
    assert parsed["restrictions"] == expected


@pytest.mark.parametrize("text", [
    "I do not approve this procedure. Rejected.", "Not approved.", "Patient is not OK to proceed",
    "Request declined; he is not approved until INR < 3", "Rejected - too risky.", "I can't clear him for surgery.",
    "Extraction is contraindicated at this time.", "I refuse to approve this.",
])
def test_negated_approvals_are_never_approved(text):
    agent = MedicalClearanceAgent()
    assert agent.parse_physician_endorsement(text)["decision"] == "REJECTED"
    state = create_initial_state("CS-9921", cdt_codes=["D7210"])
    state["clearance_status"] = "TRANSMITTED_TO_EHR"
    assert agent.ingest_physician_response(state, text).get("clearance_status") != "CLEARED"


@pytest.mark.parametrize("text", ["Cleared to proceed. Do not stop aspirin.", "Do not hold warfarin, ok to proceed.",
                                  "Not contraindicated. Cleared.", "Patient may proceed; don't stop Plavix."])
def test_maintain_instructions_do_not_read_as_rejections(text):
    assert MedicalClearanceAgent().parse_physician_endorsement(text)["decision"].startswith("APPROVED")


def test_parse_extracts_inr_and_hold_flag():
    parsed = MedicalClearanceAgent().parse_physician_endorsement("Approved. Hold warfarin for 48 hours, INR target below 2.5.")
    assert parsed["hold_medications"] is True and parsed["inr_target"] == "<2.5"


def test_rejected_response_never_clears_appointment():
    state = create_initial_state("CS-9921", cdt_codes=["D7210"])
    state["clearance_status"] = "TRANSMITTED_TO_EHR"
    update = MedicalClearanceAgent().ingest_physician_response(state, "Not cleared, defer surgery.")
    assert "clearance_status" not in update
    assert update["appointment"]["status"] == "REQUIRES_ACTION"
    assert update["clearance_protocol"]["requires_staff_review"] is True


def test_escalation_only_after_48_hours():
    agent = MedicalClearanceAgent()
    state = create_initial_state("CS-9921", cdt_codes=["D7210"])
    state["clearance_status"] = "TRANSMITTED_TO_EHR"
    assert agent.check_escalation(state, 47) == {}
    update = agent.check_escalation(state, 49)
    assert update["clearance_protocol"]["escalation"]["patient_nudge_sms"]["status"] == "simulated_sent"
    assert update["appointment"]["front_desk_flag"] is True
    # idempotent: an escalated thread is not nudged twice
    assert agent.check_escalation({**state, **update}, 60) == {}


# -- Graph ----------------------------------------------------------------------------

def test_route_after_risk_fans_out_in_parallel():
    assert route_after_risk({"clearance_status": "REQUIRED_PENDING"}) == ["clearance_agent"]
    assert route_after_risk({"clearance_status": "NOT_REQUIRED"}) == []


@pytest.mark.anyio
async def test_robert_chen_full_run_then_physician_reply():
    supervisor = AgenticSupervisor()
    thread = await supervisor.run("CS-9921", ["D7210"])
    assert thread.status == "COMPLETED", thread.error
    state = thread.state
    validate_state(state)

    assert state["patient_name"] == "Robert Chen" and state["dob"] == "1965-08-14"
    assert state["intake_status"] == "PORTAL_LINKED"
    assert [c.split()[0] for c in state["medical_records"]["conditions"]] == ["Z95.5", "I10"]
    risk = state["risk_evaluations"][-1]
    assert risk["hazard_level"] == "CRITICAL" and "CARDIAC_STENT_DAPT" in risk["triggered_rules"]
    assert risk["sticky_alert"]["status"] == "posted_to_chart"
    assert state["clearance_status"] == "TRANSMITTED_TO_EHR"
    assert state["assigned_medical_md"]["name"] == "Dr. Kenneth Vance, MD"
    assert state["assigned_medical_md"]["facility"] == "Metropolitan Heart Center"
    assert "Z95.5" in state["clearance_protocol"]["clinical_justification"]
    # A stent is a reason for caution, not a reason to bill medical: the state carries no billing claim at all
    assert "commercial_claims" not in state and "cross_bill_eligible" not in state

    thread = await supervisor.ingest_physician_response("CS-9921", ENDORSEMENT)
    state = thread.state
    assert state["clearance_status"] == "APPROVED_WITH_CONDITIONS"
    assert state["appointment"]["status"] == "CLEARED_FOR_CARE"
    assert state["clearance_protocol"]["restrictions"] == ["LIMIT_EPINEPHRINE_2_CARPULES", "MAINTAIN_ASPIRIN"]
    assert state["clearance_protocol"]["signed_by"] == "Dr. Kenneth Vance, MD"

    with pytest.raises(ValueError):  # nothing left awaiting a reply
        await supervisor.ingest_physician_response("CS-9921", ENDORSEMENT)


def test_run_simulation_endpoint():
    with TestClient(app) as client:
        resp = client.post("/api/agents/run-simulation", json={"patient_id": "CS-9921", "cdt_code": "D7210"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "COMPLETED"
        assert body["state"]["clearance_status"] == "TRANSMITTED_TO_EHR"
        assert {l["agent_name"] for l in body["state"]["agent_logs"]} == {
            "Intake Agent", "Clinical Risk Agent", "Medical Clearance Agent",
        }

        reply = client.post("/api/agents/clearance-response/CS-9921", json={"text": ENDORSEMENT})
        assert reply.status_code == 200
        assert reply.json()["state"]["appointment"]["status"] == "CLEARED_FOR_CARE"
        assert client.post("/api/agents/clearance-response/CS-9921", json={"text": ENDORSEMENT}).status_code == 409
        assert client.post("/api/agents/clearance-response/nobody", json={"text": "ok"}).status_code == 404
