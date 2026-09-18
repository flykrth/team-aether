"""
Manual mode backend: chart editing, PDF/text ingestion, and the Risk Check with literature evidence.
Network is mocked (Europe PMC) or disabled; no test touches seeded patients' data.
"""

import io

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence, patient_registry, risk_check
from app.services.document_ingest import DocumentError, document_to_text


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("MDIN_RUNTIME_REGISTRY", str(tmp_path / "registry.json"))
    patient_registry.load_runtime_registry()
    created = []
    yield created
    for patient_id in created:
        patient_registry.remove_patient(patient_id)
    monkeypatch.delenv("MDIN_RUNTIME_REGISTRY")
    patient_registry.load_runtime_registry()


def _new_patient(created, first="Manual", last="Modecase"):
    patient = patient_registry.create_patient(first, last, "1961-02-03", gender="female")
    created.append(patient["patient_id"])
    return patient["patient_id"]


# -- chart editing -----------------------------------------------------------------------

def test_edit_and_delete_history_items(registry):
    pid = _new_patient(registry)
    patient_registry.add_history_entries(pid, [{"type": "medication", "text": "warfarin"}, {"type": "condition", "text": "hypertension"}])
    chart = patient_registry.get_chart(pid)
    by_type = {e["type"]: e for e in chart["entries"]}
    assert by_type["medication"]["code"] == "11289" and by_type["condition"]["code"] == "I10"

    edited = patient_registry.update_history_entry(pid, by_type["medication"]["resource_id"], {"text": "apixaban", "onset": "2024-05-01"})
    assert edited["resource_id"] == by_type["medication"]["resource_id"]  # same item, re-coded by the lexicon
    assert edited["code"] == "1364430" and edited["onset"] == "2024-05-01" and edited["recognized"]

    patient_registry.delete_history_entry(pid, by_type["condition"]["resource_id"])
    remaining = patient_registry.get_chart(pid)["entries"]
    assert [e["code"] for e in remaining] == ["1364430"]

    with pytest.raises(KeyError):
        patient_registry.delete_history_entry(pid, "does-not-exist")


def test_cannot_edit_another_patients_item(registry):
    first, second = _new_patient(registry), _new_patient(registry, "Other", "Person")
    patient_registry.add_history_entries(first, [{"type": "medication", "text": "warfarin"}])
    item = patient_registry.get_chart(first)["entries"][0]["resource_id"]
    with pytest.raises(KeyError):
        patient_registry.update_history_entry(second, item, {"text": "aspirin"})


def test_edit_patient_details_and_plan(registry):
    pid = _new_patient(registry)
    chart = patient_registry.update_patient(pid, {"last_name": "Renamed", "phone": "555-0199",
                                                  "planned_procedures": [{"code": "D7210", "tooth_number": "19"}]})
    assert chart["name"] == "Manual Renamed" and chart["phone"] == "555-0199"
    assert chart["planned_procedures"][0]["code"] == "D7210"
    with pytest.raises(ValueError):
        patient_registry.update_patient(pid, {"birth_date": "not-a-date"})
    with pytest.raises(ValueError):
        patient_registry.update_patient(pid, {"planned_procedures": [{"code": "EXTRACT"}]})


def test_edits_survive_a_reload(registry):
    pid = _new_patient(registry)
    patient_registry.add_history_entries(pid, [{"type": "medication", "text": "warfarin"}, {"type": "allergy", "text": "penicillin"}])
    entries = {e["type"]: e["resource_id"] for e in patient_registry.get_chart(pid)["entries"]}
    patient_registry.update_history_entry(pid, entries["medication"], {"text": "clopidogrel"})
    patient_registry.delete_history_entry(pid, entries["allergy"])
    patient_registry.update_patient(pid, {"first_name": "Reloaded"})

    patient_registry.load_runtime_registry()  # what a dev-server restart does
    chart = patient_registry.get_chart(pid)
    assert chart["first_name"] == "Reloaded"
    assert [(e["type"], e["code"]) for e in chart["entries"]] == [("medication", "32968")]


def test_chart_endpoints(registry):
    pid = _new_patient(registry)
    with TestClient(app) as client:
        client.post(f"/api/records/patients/{pid}/history", json={"entries": [{"type": "condition", "text": "diabetes"}]})
        chart = client.get(f"/api/records/patients/{pid}/chart").json()
        item = chart["entries"][0]["resource_id"]
        assert client.patch(f"/api/records/patients/{pid}/history/{item}", json={"onset": "2020-01-01"}).json()["onset"] == "2020-01-01"
        assert client.patch(f"/api/records/patients/{pid}", json={"email": "m@example.com"}).json()["email"] == "m@example.com"
        assert client.patch(f"/api/records/patients/{pid}", json={}).status_code == 422
        assert client.delete(f"/api/records/patients/{pid}/history/{item}").status_code == 200
        assert client.delete(f"/api/records/patients/{pid}/history/{item}").status_code == 404
        assert client.get("/api/records/patients/nobody-here/chart").status_code == 404


# -- document ingestion --------------------------------------------------------------------

def _pdf_with_text(text: str) -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.anyio
async def test_pdf_text_layer_is_read_locally():
    pdf = _pdf_with_text("Patient takes warfarin for atrial fibrillation. Allergic to penicillin.")
    document = await document_to_text(pdf, "referral.pdf", "application/pdf")
    assert document["method"] == "pdf-text-layer" and "warfarin" in document["text"]


@pytest.mark.anyio
async def test_scanned_pdf_without_key_explains_itself(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "")
    with pytest.raises(DocumentError, match="scan"):
        await document_to_text(_pdf_with_text(""), "scan.pdf", "application/pdf")


@pytest.mark.anyio
async def test_scanned_pdf_uses_gemini_transcription(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "")
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Patient is on clopidogrel after a coronary stent."}]}}]})

    document = await document_to_text(_pdf_with_text(""), "scan.pdf", "application/pdf",
                                      client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert document["method"] == "gemini-transcription" and "clopidogrel" in document["text"]
    assert seen[0].headers["x-goog-api-key"] == "test-key" and "key=" not in str(seen[0].url)


@pytest.mark.anyio
async def test_scanned_pdf_prefers_nvidia_nemotron_parse(monkeypatch):
    import json as jsonlib
    from app.config import settings
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-test")
    seen = []

    def handler(request):
        seen.append(request)
        body = jsonlib.loads(request.content)
        assert body["model"] == "nvidia/nemotron-parse" and body["tools"][0]["function"]["name"] == "markdown_no_bbox"
        assert body["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")
        blocks = [[{"type": "Title", "text": "Discharge summary"}, {"type": "Text", "text": "Patient takes clopidogrel after a coronary stent."}]]
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": [{"function": {"name": "markdown_no_bbox", "arguments": jsonlib.dumps(blocks)}}]}}]})

    document = await document_to_text(_pdf_with_text(""), "scan.pdf", "application/pdf",
                                      client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert document["method"] == "nvidia-nemotron-parse"
    assert document["text"] == "Discharge summary\nPatient takes clopidogrel after a coronary stent."
    assert len(seen) == 1 and "integrate.api.nvidia.com" in str(seen[0].url)  # Gemini never called
    assert seen[0].headers["authorization"] == "Bearer nvapi-test"


@pytest.mark.anyio
async def test_nvidia_failure_falls_back_to_gemini(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-test")

    def handler(request):
        if "nvidia" in str(request.url):
            return httpx.Response(429, json={"detail": "rate limited"})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "Patient is on warfarin."}]}}]})

    document = await document_to_text(_pdf_with_text(""), "scan.pdf", "application/pdf",
                                      client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert document["method"] == "gemini-transcription" and "warfarin" in document["text"]


@pytest.mark.anyio
async def test_bad_uploads_are_rejected():
    for data, name, kind in [(b"", "a.pdf", "application/pdf"), (b"MZ\x90", "virus.exe", "application/octet-stream"),
                             (b"%PDF-1.4 garbage", "broken.pdf", "application/pdf")]:
        with pytest.raises(DocumentError):
            await document_to_text(data, name, kind)


def test_extract_file_endpoint_codes_the_pdf():
    pdf = _pdf_with_text("Patient takes warfarin for atrial fibrillation. No history of diabetes.")
    with TestClient(app) as client:
        body = client.post("/api/records/extract-file", files={"file": ("referral.pdf", pdf, "application/pdf")}).json()
        assert body["method"] == "pdf-text-layer"
        assert {e["code"] for e in body["entries"]} == {"11289", "I48.91"}
        assert [e["code"] for e in body["excluded"]] == ["E11.9"]  # negated, reported but not added
        assert client.post("/api/records/extract-file", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 422


# -- risk check ------------------------------------------------------------------------------

@pytest.mark.parametrize("text,code", [
    ("surgical extraction of #19", "D7210"), ("pull the tooth", "D7140"), ("place an implant", "D6010"),
    ("deep cleaning", "D4341"), ("routine cleaning", "D1110"), ("D7240 lower right", "D7240"),
])
def test_procedure_resolution(text, code):
    assert risk_check.resolve_procedure(text)["cdt_code"] == code


def test_unknown_procedure_is_treated_as_surgical():
    resolved = risk_check.resolve_procedure("frenuloplasty with laser")
    assert resolved["matched"] is False and resolved["invasive"] is True


@pytest.mark.anyio
async def test_todays_notes_change_the_answer(registry):
    pid = _new_patient(registry)
    patient_registry.add_history_entries(pid, [{"type": "condition", "text": "hypertension"}])

    before = await risk_check.check(pid, "surgical extraction", include_evidence=False, include_ai=False)
    assert before["hazard_level"] == "MODERATE" and not before["physician_clearance_required"]

    after = await risk_check.check(pid, "surgical extraction", include_evidence=False, include_ai=False,
                                   current_notes="Started warfarin last month. Allergic to penicillin. No diabetes.")
    assert after["hazard_level"] == "CRITICAL" and after["physician_clearance_required"]
    rules = {f["rule_id"]: f for f in after["findings"]}
    assert rules["ANTICOAGULANT_HEMORRHAGE"]["from_todays_notes"] is True
    assert rules["DRUG_ALLERGY"]["from_todays_notes"] is True
    assert rules["SYSTEMIC_MODIFIERS"]["from_todays_notes"] is False  # hypertension was already on file
    assert [e["code"] for e in after["excluded_from_notes"]] == ["E11.9"]
    # read-only: nothing from today's notes was written to the chart
    assert [e["code"] for e in patient_registry.get_chart(pid)["entries"]] == ["I10"]


@pytest.mark.anyio
async def test_valve_patient_with_penicillin_allergy_gets_alternative_prophylaxis(registry):
    pid = _new_patient(registry)
    result = await risk_check.check(pid, "extraction", include_evidence=False, include_ai=False,
                                    current_notes="Has a prosthetic heart valve. Allergic to penicillin.")
    prophylaxis = next(f for f in result["findings"] if f["rule_id"] == "ENDOCARDITIS_PROPHYLAXIS")
    assert "NOT amoxicillin" in prophylaxis["recommendations"][0]


def test_quote_is_verbatim_and_relevant():
    abstract = ("<h4>Background</h4>Dental extractions are common. <h4>Conclusions</h4>Continuing dual antiplatelet "
                "therapy during dental extraction did not increase clinically significant bleeding when local hemostatic "
                "measures were used. Funding was provided by a university grant.")
    quote = evidence.pick_quote(abstract, evidence.RULE_QUERIES["CARDIAC_STENT_DAPT"]["keywords"])
    assert quote.startswith("Continuing dual antiplatelet therapy") and quote in evidence._clean(abstract)
    assert evidence.pick_quote("Short. Irrelevant sentence about funding and nothing else at all here.", ("warfarin",)) == ""


@pytest.mark.anyio
async def test_evidence_is_attached_and_network_failure_is_harmless(registry, monkeypatch):
    pid = _new_patient(registry)
    patient_registry.add_history_entries(pid, [{"type": "medication", "text": "warfarin"}])
    evidence._cache.clear()

    def europe_pmc(request):
        assert "europepmc" in str(request.url)
        return httpx.Response(200, json={"resultList": {"result": [{
            "id": "123", "source": "MED", "title": "Anticoagulants and dental extraction.", "pubYear": "2024",
            "journalInfo": {"journal": {"title": "J Dent Res"}}, "authorString": "Doe J.",
            "abstractText": "Patients on warfarin with an INR below 3.5 can undergo dental extraction without interrupting "
                            "anticoagulant therapy when local hemostatic measures are used.",
        }]}})

    ok = await risk_check.check(pid, "extraction", include_ai=False, client=httpx.AsyncClient(transport=httpx.MockTransport(europe_pmc)))
    literature = next(f for f in ok["findings"] if f["rule_id"] == "ANTICOAGULANT_HEMORRHAGE")["literature"]
    assert literature[0]["url"] == "https://europepmc.org/article/MED/123" and "warfarin" in literature[0]["quote"]

    evidence._cache.clear()
    def down(request):
        raise httpx.ConnectError("offline")
    offline = await risk_check.check(pid, "extraction", include_ai=False, client=httpx.AsyncClient(transport=httpx.MockTransport(down)))
    assert offline["hazard_level"] == "CRITICAL" and all(f["literature"] == [] for f in offline["findings"])


def test_risk_endpoint(registry):
    pid = _new_patient(registry)
    with TestClient(app) as client:
        body = client.post("/api/risk/check", json={"patient_id": pid, "procedure": "cleaning", "include_evidence": False, "include_ai": False}).json()
        assert body["hazard_level"] == "LOW" and body["procedure"]["cdt_code"] == "D1110"
        assert client.post("/api/risk/check", json={"patient_id": pid, "procedure": ""}).status_code == 422
        assert len(client.get("/api/risk/procedures").json()["procedures"]) >= 10


def test_same_drug_under_a_different_code_is_not_new():
    on_file = [{"type": "medication", "system": "rx", "code": "855332", "display": "Warfarin Sodium 5 MG"},
               {"type": "allergy", "system": "snomed", "code": "70618001", "display": "Penicillin allergy"}]
    assert risk_check._already_on_file({"type": "medication", "system": "rx", "code": "11289", "display": "Warfarin (Coumadin)"}, on_file)
    assert risk_check._already_on_file({"type": "allergy", "system": "snomed", "code": "91936005", "display": "Allergy to penicillin"}, on_file)
    assert not risk_check._already_on_file({"type": "medication", "system": "rx", "code": "32968", "display": "Clopidogrel (Plavix)"}, on_file)
    # a condition never matches a medication just because a word overlaps
    assert not risk_check._already_on_file({"type": "condition", "system": "icd", "code": "X", "display": "Warfarin overdose"}, on_file)
