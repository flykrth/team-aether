"""
Patient Records: registry service, /api/records router and the assistant record tools.

Every test runs against a tmp registry file and removes what it added, so the seeded patient
counts the rest of the suite relies on are untouched.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import carestack_mock
from app.schemas.carestack import CareStackPatient
from app.services import patient_registry as registry
from app.services.agent_supervisor import AgenticSupervisor
from app.services.assistant import record_tools, tools
from app.services.fhir_client import PATIENT_ALIASES, fhir_client

client = TestClient(app)

WARFARIN_AFIB = [{"type": "medication", "text": "warfarin 5mg daily"}, {"type": "condition", "text": "atrial fibrillation"}]


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _snapshot():
    return {
        "patients": [p.id for p in carestack_mock.MOCK_PATIENTS],
        "fhir": {k: [r.get("id") for r in v] for k, v in fhir_client._local_cache.items()},
        "fhir_aliases": json.loads(json.dumps(PATIENT_ALIASES)),
        "cs_aliases": dict(carestack_mock.CARESTACK_PATIENT_ALIASES),
        "documents": {k: len(v) for k, v in carestack_mock.CARESTACK_PATIENT_DOCUMENTS.items()},
    }


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Tmp registry file + a hard guarantee that the shared in-memory stores end up as they started."""
    monkeypatch.setenv(registry.REGISTRY_ENV, str(tmp_path / "runtime_registry.json"))
    registry.load_runtime_registry()
    before = _snapshot()
    yield tmp_path / "runtime_registry.json"
    for patient_id in [p["id"] for p in registry._state["patients"]] + ["CS-7707", "CS-9921"]:
        registry.remove_patient(patient_id)
    carestack_mock.MOCK_PATIENTS[:] = [p for p in carestack_mock.MOCK_PATIENTS if p.id != "CS-7707"]
    assert _snapshot() == before
    monkeypatch.delenv(registry.REGISTRY_ENV)
    registry.load_runtime_registry()
    assert registry._state_path is None  # under pytest the real registry file is never in play


def _new_patient(**overrides):
    args = dict(first_name="Priya", last_name="Nair", birth_date="1961-02-03", gender="female",
                planned_procedures=[{"code": "D7140", "tooth_number": "30"}])
    return registry.create_patient(**{**args, **overrides})


# -- create -----------------------------------------------------------------------------

def test_create_patient_lands_in_both_systems():
    created = _new_patient(phone="555-0177")
    assert created["already_existed"] is False
    assert created["patient_id"].startswith("CS-") and created["mrn"].startswith("MRN-")
    assert created["planned_procedures"] == [
        {"code": "D7140", "description": "Extraction, erupted tooth or exposed root", "tooth_number": "30"}
    ]

    for key in (created["patient_id"], created["patient_id"].lower(), created["mrn"]):
        assert carestack_mock._find_carestack_patient(key).last_name == "Nair"
        info = registry.clearance_service()._resolve_patient_info(key)
        assert info["name"] == "Priya Nair" and info["fhir_patient"]["birthDate"] == "1961-02-03"

    listed = {p["patient_id"]: p for p in registry.list_patients()}
    assert listed[created["patient_id"]]["medical_record_linked"] is True
    assert listed[created["patient_id"]]["planned_procedures"] == ["D7140 Extraction, erupted tooth or exposed root"]
    assert listed["CS-9921"]["name"] == "Robert Chen"


def test_duplicate_patient_is_returned_not_duplicated():
    first = _new_patient()
    again = _new_patient(first_name=" priya ", last_name="NAIR")
    assert again["already_existed"] is True and again["patient_id"] == first["patient_id"]
    assert sum(p.last_name == "Nair" for p in carestack_mock.MOCK_PATIENTS) == 1
    # same name, different birth date is a different person
    other = _new_patient(birth_date="1990-10-10")
    assert other["already_existed"] is False and other["patient_id"] != first["patient_id"]


def test_new_ids_never_collide_with_digit_matching():
    ids = [_new_patient(first_name=name)["patient_id"] for name in ("Pa", "Pb", "Pc")]
    assert len(set(ids)) == 3
    for patient_id in ids:
        assert carestack_mock._find_carestack_patient(patient_id).id == patient_id


@pytest.mark.parametrize("overrides", [{"birth_date": "03/02/1961"}, {"first_name": " "}, {"planned_procedures": [{"code": "extraction"}]}])
def test_create_patient_rejects_bad_input(overrides):
    with pytest.raises(ValueError):
        _new_patient(**overrides)
    assert not registry._state["patients"]


# -- history ------------------------------------------------------------------------------

def test_history_is_coded_by_lexicon_and_unrecognized_passes_through():
    patient_id = _new_patient()["patient_id"]
    result = registry.add_history_entries(patient_id, WARFARIN_AFIB + [
        {"type": "allergy", "text": "penicillin"},
        {"type": "condition", "text": "gout"},
        {"type": "observation", "text": "INR", "value": 2.8, "onset": "2026-09-01"},
        {"type": "condition", "text": "sarcoidosis", "code": "D86.9"},
    ])
    codes = {e["text"]: (e.get("system"), e.get("code")) for e in result["added"]}
    assert codes["warfarin 5mg daily"] == (registry.RXNORM_SYSTEM, "11289")
    assert codes["atrial fibrillation"] == (registry.ICD10_SYSTEM, "I48.91")
    assert codes["penicillin"] == (registry.SNOMED_SYSTEM, "91936005")
    assert codes["INR"] == (registry.LOINC_SYSTEM, "6301-6")
    assert codes["sarcoidosis"] == (registry.ICD10_SYSTEM, "D86.9")  # explicit user code is kept
    assert [e["text"] for e in result["unrecognized"]] == ["gout"] and codes["gout"] == (None, None)

    info = registry.clearance_service()._resolve_patient_info(patient_id)
    fhir_id = info["fhir_patient"]["id"]
    gout = next(c for c in info["conditions"] if c["code"]["text"] == "gout")
    assert "coding" not in gout["code"] and gout["subject"]["reference"] == f"Patient/{fhir_id}"
    assert info["allergies"][0]["patient"]["reference"] == f"Patient/{fhir_id}"
    assert info["medications"][0]["resourceType"] == "MedicationRequest" and "authoredOn" not in info["medications"][0]
    inr = fhir_client._local_cache["Observation"][-1]
    assert inr["valueQuantity"]["value"] == 2.8 and inr["effectiveDateTime"].startswith("2026-09-01")


def test_history_dedupes_against_record_and_within_request():
    patient_id = _new_patient()["patient_id"]
    first = registry.add_history_entries(patient_id, WARFARIN_AFIB + [{"type": "medication", "text": "Coumadin"}, {"type": "condition", "text": "gout"}])
    assert len(first["added"]) == 3 and [e["text"] for e in first["skipped_duplicates"]] == ["Coumadin"]
    second = registry.add_history_entries(patient_id, WARFARIN_AFIB + [{"type": "condition", "text": "Gout"}, {"type": "condition", "text": "asthma"}])
    assert [e["code"] for e in second["added"]] == ["J45.909"] and len(second["skipped_duplicates"]) == 3
    # seeded EHR data is deduped too (Robert Chen already has hypertension I10)
    seeded = registry.add_history_entries("CS-9921", [{"type": "condition", "text": "high blood pressure"}])
    assert not seeded["added"] and seeded["skipped_duplicates"][0]["code"] == "I10"


def test_drug_typed_as_condition_is_filed_as_medication():
    patient_id = _new_patient()["patient_id"]
    added = registry.add_history_entries(patient_id, [{"type": "condition", "text": "takes Eliquis"}])["added"]
    assert added[0]["type"] == "medication" and added[0]["code"] == "1364430"


def test_carestack_only_patient_gets_a_fhir_record():
    carestack_mock.MOCK_PATIENTS.append(CareStackPatient(
        id="CS-7707", mrn="MRN-7707", first_name="Walk", last_name="In", birth_date="1980-05-05", gender="male"))
    assert registry.clearance_service()._resolve_patient_info("CS-7707")["fhir_patient"] is None

    result = registry.add_history_entries("CS-7707", [{"type": "medication", "text": "alendronate"}])
    assert result["patient_id"] == "CS-7707" and result["added"][0]["code"] == "46041"
    info = registry.clearance_service()._resolve_patient_info("cs-7707")
    assert info["fhir_patient"]["name"][0]["family"] == "In" and len(info["medications"]) == 1


def test_unknown_patient_and_bad_entries():
    with pytest.raises(KeyError):
        registry.add_history_entries("CS-0000404", WARFARIN_AFIB)
    patient_id = _new_patient()["patient_id"]
    with pytest.raises(ValueError):
        registry.add_history_entries(patient_id, [{"type": "procedure", "text": "appendectomy"}])
    with pytest.raises(ValueError):
        registry.add_history_entries(patient_id, [{"type": "condition", "text": ""}])


# -- extract / import ------------------------------------------------------------------------

RECORD_TEXT = (
    "Discharge summary. History of atrial fibrillation, on warfarin for 3 years. "
    "Also has asthma and sarcoidosis. HbA1c 7.4% in March; INR was 2.8. Allergic to latex. INR to be rechecked in 3 weeks."
)


def test_extract_is_deterministic_and_lexicon_only():
    entries = registry.extract_entries_from_text(RECORD_TEXT)["entries"]
    assert entries == registry.extract_entries_from_text(RECORD_TEXT)["entries"]
    assert [(e["type"], e["code"]) for e in entries] == [
        ("condition", "I48.91"), ("medication", "11289"), ("condition", "J45.909"),
        ("observation", "4548-4"), ("observation", "6301-6"), ("allergy", "300916003"),
    ]
    by_code = {e["code"]: e for e in entries}
    assert by_code["4548-4"]["value"] == 7.4 and by_code["6301-6"]["value"] == 2.8  # "in 3 weeks" is not a result
    assert by_code["11289"]["onset"] and "warfarin" in by_code["11289"]["evidence"]
    assert "sarcoidosis" not in json.dumps(entries)  # unknown to the lexicon: never guessed
    assert registry.extract_entries_from_text("")["entries"] == []


def test_import_saves_document_and_adds_entries():
    patient_id = _new_patient()["patient_id"]
    result = registry.import_previous_record(patient_id, "Cardiology discharge", RECORD_TEXT, "2026-03-14", "St. Mary's")
    assert len(result["added"]) == 6 and not result["unrecognized"]

    patient = carestack_mock._find_carestack_patient(patient_id)
    document = patient.attached_documents[0]
    assert document["document_id"] == result["document_id"]
    assert document["document_type"] == "Previous Medical Record" and document["file_content"] == RECORD_TEXT
    assert document["metadata"]["source_facility"] == "St. Mary's" and document["metadata"]["record_date"] == "2026-03-14"

    # confirmed entries replace extraction; re-import of known items is all duplicates
    confirmed = registry.import_previous_record(patient_id, "Same again", RECORD_TEXT, entries=[{"type": "condition", "text": "asthma"}])
    assert not confirmed["added"] and len(confirmed["skipped_duplicates"]) == 1
    assert len(patient.attached_documents) == 2
    with pytest.raises(ValueError):
        registry.import_previous_record(patient_id, "Empty", "   ")


# -- persistence -------------------------------------------------------------------------------

def test_persistence_round_trip(isolated_registry):
    patient_id = _new_patient()["patient_id"]
    registry.import_previous_record(patient_id, "Old chart", "Takes warfarin. Has atrial fibrillation.")
    saved = json.loads(isolated_registry.read_text())
    assert [p["id"] for p in saved["patients"]] == [patient_id] and len(saved["documents"]) == 1

    # simulate the dev-server reload: wipe memory, keep the file
    isolated_registry.write_text(json.dumps(saved))
    registry.remove_patient(patient_id)
    assert carestack_mock._find_carestack_patient(patient_id) is None
    isolated_registry.write_text(json.dumps(saved))

    assert registry.load_runtime_registry() == {"patients": 1, "fhir_resources": 3, "documents": 1}
    registry.load_runtime_registry()  # idempotent
    patient = carestack_mock._find_carestack_patient(patient_id)
    assert patient.first_name == "Priya" and len(patient.attached_documents) == 1
    info = registry.clearance_service()._resolve_patient_info(patient_id)
    assert [m["medicationCodeableConcept"]["coding"][0]["code"] for m in info["medications"]] == ["11289"]
    assert sum(p.id == patient_id for p in carestack_mock.MOCK_PATIENTS) == 1
    # and the next new patient does not reuse the restored number
    assert _new_patient(first_name="Second")["patient_id"] != patient_id


def test_corrupt_registry_file_is_ignored(isolated_registry):
    isolated_registry.write_text("{not json")
    assert registry.load_runtime_registry()["patients"] == 0
    assert _new_patient()["already_existed"] is False


# -- agents + assistant integration ----------------------------------------------------------------

@pytest.mark.anyio
async def test_new_patient_is_immediately_usable_by_the_agents():
    patient_id = _new_patient()["patient_id"]
    registry.add_history_entries(patient_id, WARFARIN_AFIB)

    thread = await AgenticSupervisor().run(patient_id, ["D7140"])
    assert thread.state["intake_status"] == "PORTAL_LINKED" and thread.state["patient_name"] == "Priya Nair"
    assert thread.state["risk_evaluations"][0]["hazard_level"] == "CRITICAL"
    assert thread.state["clearance_status"] == "TRANSMITTED_TO_EHR"

    history = await tools.get_patient_history(patient_id)
    assert history["found"] and history["medical_record_linked"]
    assert [c["code"] for c in history["conditions"]] == ["I48.91"]
    assert history["medications"][0]["code"] == "11289" and history["medications"][0]["drug_class"] == "anticoagulant"


@pytest.mark.anyio
async def test_record_tools_contract():
    assert record_tools.RECORD_ACTION_TOOLS == set(record_tools.RECORD_TOOL_FUNCTIONS) == {
        "create_patient", "add_medical_history", "import_previous_record"}
    declarations = {d["name"]: d for d in record_tools.RECORD_TOOL_DECLARATIONS}
    assert declarations["create_patient"]["parameters"]["required"] == ["first_name", "last_name", "birth_date"]
    assert "date of birth" in declarations["create_patient"]["description"]
    assert all(d["description"].startswith("ACTION.") and "onfirm" in d["description"] for d in declarations.values())

    created = await record_tools.create_patient("Omar", "Haddad", "1975-07-07", history=[{"type": "medication", "text": "Xarelto"}])
    assert created["ok"] and created["history"]["added"][0]["code"] == "1114195"
    added = await record_tools.add_medical_history(created["patient_id"], [{"type": "condition", "text": "diabetic"}])
    assert added["ok"] and added["added"][0]["code"] == "E11.9"
    imported = await record_tools.import_previous_record(created["patient_id"], "Referral", "Known hypertension, takes lisinopril.")
    assert imported["ok"] and {e["code"] for e in imported["added"]} == {"I10", "29046"}

    # failures come back as data the model can act on
    assert (await record_tools.add_medical_history("CS-0000404", WARFARIN_AFIB))["ok"] is False
    assert (await record_tools.add_medical_history(created["patient_id"], []))["ok"] is False
    assert (await record_tools.create_patient("Omar", "Haddad", "July 1975"))["ok"] is False


# -- router ---------------------------------------------------------------------------------------------

def test_router_create_list_get():
    response = client.post("/api/records/patients", json={
        "first_name": "Lena", "last_name": "Okafor", "birth_date": "1958-11-30", "gender": "female",
        "planned_procedures": [{"code": "D7210", "tooth_number": "17"}],
        "history": [{"type": "medication", "text": "Plavix"}, {"type": "condition", "text": "lupus"}],
    })
    assert response.status_code == 201
    body = response.json()
    assert body["already_existed"] is False and [e["text"] for e in body["history"]["unrecognized"]] == ["lupus"]
    patient_id = body["patient_id"]

    listed = client.get("/api/records/patients").json()
    assert {"patient_id", "mrn", "name", "birth_date", "gender", "next_appointment", "planned_procedures",
            "medical_record_linked"} <= set(listed[0])
    assert any(p["patient_id"] == patient_id and p["medical_record_linked"] for p in listed)

    record = client.get(f"/api/records/patients/{patient_id}").json()
    assert record["found"] and record["name"] == "Lena Okafor"
    assert record["medications"][0]["drug_class"] == "antiplatelet"
    assert record["dental"]["treatment_plan"][0]["cdt_code"] == "D7210"

    duplicate = client.post("/api/records/patients", json={"first_name": "Lena", "last_name": "Okafor", "birth_date": "1958-11-30"})
    assert duplicate.status_code == 201 and duplicate.json()["already_existed"] is True


def test_router_history_extract_import():
    patient_id = client.post("/api/records/patients", json={"first_name": "Lena", "last_name": "Okafor", "birth_date": "1958-11-30"}).json()["patient_id"]

    history = client.post(f"/api/records/patients/{patient_id}/history", json={"entries": WARFARIN_AFIB, "source": "front-desk"})
    assert history.status_code == 200 and len(history.json()["added"]) == 2

    preview = client.post("/api/records/extract", json={"text": RECORD_TEXT})
    assert preview.status_code == 200 and len(preview.json()["entries"]) == 6

    kept = [e for e in preview.json()["entries"] if e["code"] != "J45.909"]  # user unticked asthma
    imported = client.post(f"/api/records/patients/{patient_id}/import", json={
        "title": "Discharge", "text": RECORD_TEXT, "record_date": "2026-03-14", "entries": kept})
    assert imported.status_code == 200
    body = imported.json()
    assert body["document_id"].startswith("DOC-")
    assert {e["code"] for e in body["added"]} == {"4548-4", "6301-6", "300916003"}
    assert {e["code"] for e in body["skipped_duplicates"]} == {"I48.91", "11289"}
    assert "J45.909" not in json.dumps(client.get(f"/api/records/patients/{patient_id}").json()["conditions"])


def test_router_error_paths():
    assert client.get("/api/records/patients/CS-0000404").status_code == 404
    assert client.post("/api/records/patients/CS-0000404/history", json={"entries": WARFARIN_AFIB}).status_code == 404
    assert client.post("/api/records/patients/CS-0000404/import", json={"title": "x", "text": "warfarin"}).status_code == 404
    assert client.post("/api/records/patients/CS-9921/history", json={"entries": []}).status_code == 422
    assert client.post("/api/records/patients/CS-9921/history", json={"entries": [{"type": "surgery", "text": "x"}]}).status_code == 422
    assert client.post("/api/records/patients/CS-9921/import", json={"title": "x", "text": ""}).status_code == 422
    assert client.post("/api/records/patients", json={"first_name": "A", "last_name": "B", "birth_date": "yesterday"}).status_code == 422
    assert client.post("/api/records/patients", json={"first_name": "A"}).status_code == 422
    assert "records_patients" in client.get("/").json()["endpoints"]


# -- Review hardening ---------------------------------------------------------------

def test_extraction_excludes_negated_family_and_discontinued_statements():
    text = ("No history of atrial fibrillation. Denies taking warfarin. Father had type 2 diabetes. "
            "No known allergy to penicillin. Stopped clopidogrel in 2019. No history of diabetes, hypertension and asthma.")
    result = registry.extract_entries_from_text(text)
    assert result["entries"] == []
    reasons = {e["code"]: e["reason"] for e in result["excluded"]}
    assert reasons["I48.91"] == "negated" and reasons["11289"] == "negated" and reasons["32968"] == "discontinued"
    assert "family history" in reasons.values() and reasons["J45.909"] == "negated"
    assert registry.extract_entries_from_text("Family history: mother had atrial fibrillation")["entries"] == []


def test_extraction_keeps_positive_statements_next_to_negated_ones():
    result = registry.extract_entries_from_text(
        "No aspirin, takes warfarin for atrial fibrillation. Type 2 diabetes without complications, not well controlled, hypertension.")
    assert {e["code"] for e in result["entries"]} >= {"11289", "I48.91", "E11.9", "I10"}
    assert [e["display"] for e in result["excluded"]] == ["Aspirin"]


def test_unreviewed_import_is_charted_unconfirmed_and_reports_exclusions():
    patient_id = _new_patient()["patient_id"]
    result = registry.import_previous_record(patient_id, "Old note", "Takes warfarin. Denies diabetes.")
    assert result["verification"] == "unconfirmed" and [e["code"] for e in result["added"]] == ["11289"]
    assert [e["code"] for e in result["excluded"]] == ["E11.9"]
    reviewed = registry.import_previous_record(patient_id, "Old note 2", "x", entries=[{"type": "condition", "text": "asthma"}])
    assert reviewed["verification"] == "confirmed"
    statuses = {r["code"]["coding"][0]["code"]: r["verificationStatus"]["coding"][0]["code"]
                for r in fhir_client._local_cache["Condition"] if r["id"] in {e["resource_id"] for e in reviewed["added"]}}
    assert statuses == {"J45.909": "confirmed"}


def test_history_batch_is_all_or_nothing():
    patient_id = _new_patient()["patient_id"]
    with pytest.raises(ValueError):
        registry.add_history_entries(patient_id, [{"type": "condition", "text": "asthma"},
                                                  {"type": "condition", "text": "copd", "onset": "last year"}])
    assert client.get(f"/api/records/patients/{patient_id}").json()["conditions"] == []
    # the assistant path drops the unusable date instead of failing the batch
    lenient = registry.add_history_entries(patient_id, [{"type": "condition", "text": "copd", "onset": "last year"}], lenient_dates=True)
    assert lenient["added"][0]["code"] == "J44.9" and "onset" not in lenient["added"][0] and lenient["onset_dropped"]


def test_failed_import_and_failed_create_leave_nothing_behind():
    patient_id = _new_patient()["patient_id"]
    bad = client.post(f"/api/records/patients/{patient_id}/import",
                      json={"title": "t", "text": "x", "entries": [{"type": "condition", "text": "x", "onset": "nope"}]})
    assert bad.status_code == 422
    assert carestack_mock._find_carestack_patient(patient_id).attached_documents == [] and registry._state["documents"] == []
    created = client.post("/api/records/patients", json={"first_name": "Ab", "last_name": "Cd", "birth_date": "1980-01-01",
                                                         "history": [{"type": "condition", "text": "asthma", "onset": "bad"}]})
    assert created.status_code == 422
    assert not any(p["name"] == "Ab Cd" for p in registry.list_patients())


def test_similar_names_never_cross_link_charts():
    park = _new_patient(first_name="Sam", last_name="Park")["patient_id"]
    parker = _new_patient(first_name="Sam", last_name="Parker")["patient_id"]
    registry.add_history_entries(parker, [{"type": "medication", "text": "warfarin"}])
    resolve = registry.clearance_service()._resolve_patient_info
    assert resolve(park)["medications"] == [] and len(resolve(parker)["medications"]) == 1
    assert resolve("sam park").get("fhir_patient") is None  # names are not FHIR aliases
    assert registry.find_patient_id_by_name("sam park") == park
    assert not any(" " in alias for aliases in registry._state["fhir_aliases"].values() for alias in aliases)


@pytest.mark.parametrize("overrides", [
    {"first_name": "CS-9921"}, {"last_name": "x" * 81}, {"first_name": "<img src=x>"},
    {"birth_date": "2999-01-01"}, {"birth_date": "1961-02-03junk"}, {"birth_date": "1850-01-01"},
])
def test_create_patient_rejects_id_like_names_and_impossible_birth_dates(overrides):
    before = [c["display"] for c in client.get("/api/records/patients/CS-9921").json()["conditions"]]
    with pytest.raises(ValueError):
        _new_patient(**overrides)
    assert [c["display"] for c in client.get("/api/records/patients/CS-9921").json()["conditions"]] == before
    assert registry.create_patient("José", "O'Neil-Smith", "1970-01-01")["already_existed"] is False


def test_explicit_code_must_be_well_formed_and_agree_with_the_text():
    patient_id = _new_patient()["patient_id"]
    for entry in ({"type": "condition", "text": "headache", "code": "banana"},
                  {"type": "condition", "text": "asthma", "code": "I48.91"},
                  {"type": "condition", "text": "asthma", "code": "J45.909", "system": "http://evil.example/codes"}):
        with pytest.raises(ValueError):
            registry.add_history_entries(patient_id, [entry])
    ok = registry.add_history_entries(patient_id, [{"type": "condition", "text": "type 2 diabetes", "code": "E11.65"}])
    assert ok["added"][0]["code"] == "E11.65" and ok["added"][0]["coded_by"] == "user"


@pytest.mark.anyio
async def test_assistant_tool_ignores_codes_the_user_never_typed():
    from app.services.assistant.context import turn_user_text

    patient_id = _new_patient()["patient_id"]
    token = turn_user_text.set("she has a headache, and atrial fibrillation coded I48.91")
    try:
        result = await record_tools.add_medical_history(patient_id, [
            {"type": "condition", "text": "headache", "code": "G43.909", "system": "x", "display": "Migraine"},
            {"type": "condition", "text": "atrial fibrillation", "code": "I48.91"},
        ])
    finally:
        turn_user_text.reset(token)
    by_text = {e["text"]: e for e in result["added"]}
    assert "code" not in by_text["headache"] and result["codes_ignored"] == ["G43.909"]
    assert [e["text"] for e in result["unrecognized"]] == ["headache"]
    assert by_text["atrial fibrillation"]["code"] == "I48.91"


def test_integer_and_float_lab_values_are_the_same_result():
    patient_id = _new_patient()["patient_id"]
    entry = {"type": "observation", "text": "HbA1c", "value": 7, "onset": "2026-01-01"}
    assert len(registry.add_history_entries(patient_id, [entry])["added"]) == 1
    again = registry.add_history_entries(patient_id, [dict(entry, value=7.0)])
    assert again["added"] == [] and len(again["skipped_duplicates"]) == 1
    registry.add_history_entries(patient_id, [{"type": "observation", "text": "INR", "value": "pending"}])
    values = {o["test"]: o["value"] for o in client.get(f"/api/records/patients/{patient_id}").json()["observations"]}
    assert values["INR"] == "pending"


@pytest.mark.parametrize("content", ['[1, 2]', '{"patients": null}', '{"patients": [{"id": "CS-3001"}]}',
                                     '{"fhir": [{"resourceType": "Condition"}]}', '{not json'])
def test_malformed_registry_file_is_ignored_not_fatal(isolated_registry, content):
    isolated_registry.write_text(content)
    assert registry.load_runtime_registry() == {"patients": 0, "fhir_resources": 0, "documents": 0}


def test_records_api_bounds_its_inputs():
    assert client.post("/api/records/patients", json={"first_name": "A" * 5000, "last_name": "B", "birth_date": "1980-01-01"}).status_code == 422
    patient_id = _new_patient()["patient_id"]
    too_many = [{"type": "condition", "text": f"item {i}"} for i in range(registry.MAX_ENTRIES + 1)]
    assert client.post(f"/api/records/patients/{patient_id}/history", json={"entries": too_many}).status_code == 422
    assert client.post(f"/api/records/patients/{patient_id}/history",
                       json={"entries": [{"type": "condition", "text": "asthma"}], "source": "Bad Source!"}).status_code == 422


def test_every_lexicon_concept_survives_the_explicit_code_validation():
    """The records panel sends previewed entries back with their lexicon code: none may be refused."""
    for _, template in registry.NARRATIVE_LEXICON + registry.SUPPLEMENTAL_LEXICON:
        entry, recognized = registry._normalize_entry({"type": template["type"], "text": template["display"],
                                                       "code": template["code"], "system": template["system"]})
        assert recognized and entry["code"] == template["code"].upper()
    for _, lab in registry.LAB_LEXICON:
        registry._normalize_entry({"type": "observation", "text": lab["text"], "code": lab["code"], "value": 1})
