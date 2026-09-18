"""
Patient Registry: add patients, medical history and previous records at runtime.

A new patient is written to BOTH sides of the node so every existing reader keeps working:
  - CareStack simulator  -> carestack_mock.MOCK_PATIENTS (+ CARESTACK_PATIENT_ALIASES)
  - Medical record (FHIR) -> fhir_client._local_cache (+ fhir_client.PATIENT_ALIASES)
medical_clearance_service._resolve_patient_info() merges the two, so the MAO agents and the
assistant see a registry patient exactly like a seeded one.

Coding is deterministic. Free text is normalized with the Intake agent's lexicon plus the small
supplement below; text that matches nothing is stored uncoded (code.text only) and reported back
as unrecognized. Nothing here calls an LLM, so a diagnosis code can never be invented.

Runtime additions are persisted to app/data/runtime_registry.json (override: MDIN_RUNTIME_REGISTRY)
and re-applied on load, because the dev server reloads the process on every file change.
"""

import json
import os
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .agents.base import ICD10_SYSTEM, RXNORM_SYSTEM, SNOMED_SYSTEM, carestack_services, clearance_service
from .agents.intake_agent import NARRATIVE_LEXICON, IntakeAgent
from .fhir_client import PATIENT_ALIASES, fhir_client, resolve_patient_aliases

LOINC_SYSTEM = "http://loinc.org"
UCUM_SYSTEM = "http://unitsofmeasure.org"
REGISTRY_ENV = "MDIN_RUNTIME_REGISTRY"
DEFAULT_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "runtime_registry.json")
PREVIOUS_RECORD_DOCUMENT_TYPE = "Previous Medical Record"

ENTRY_TYPES = ("condition", "medication", "allergy", "observation")
DEFAULT_SYSTEM = {"condition": ICD10_SYSTEM, "medication": RXNORM_SYSTEM, "allergy": SNOMED_SYSTEM, "observation": LOINC_SYSTEM}
_RESOURCE_TYPE = {"condition": "Condition", "medication": "MedicationRequest",
                  "allergy": "AllergyIntolerance", "observation": "Observation"}

# Supplements the Intake agent's NARRATIVE_LEXICON (same shape) with common history items.
# RxNorm codes are ingredient-level RxCUIs.
SUPPLEMENTAL_LEXICON = [
    # Dentally relevant drugs and conditions: newer antiplatelets (bleeding) and immunosuppression (infection, healing)
    (r"\bticagrelor\b|\bbrilinta\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "1116632", "display": "Ticagrelor (Brilinta)", "drug_class": "antiplatelet"}),
    (r"\bprasugrel\b|\beffient\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "613391", "display": "Prasugrel (Effient)", "drug_class": "antiplatelet"}),
    (r"\bmethotrexate\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "6851", "display": "Methotrexate", "drug_class": "immunosuppressant"}),
    (r"\brheumatoid arthritis\b", {"type": "condition", "system": ICD10_SYSTEM, "code": "M06.9", "display": "Rheumatoid arthritis, unspecified"}),
    (r"\bhyperlipid(a)?emia\b|\bhigh cholesterol\b", {"type": "condition", "system": ICD10_SYSTEM, "code": "E78.5", "display": "Hyperlipidemia, unspecified"}),
    (r"\basthma\b", {"type": "condition", "system": ICD10_SYSTEM, "code": "J45.909", "display": "Unspecified asthma, uncomplicated"}),
    (r"\bcopd\b|\bchronic obstructive pulmonary\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "J44.9", "display": "Chronic obstructive pulmonary disease, unspecified"}),
    (r"\bchronic kidney disease\b|\bckd\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "N18.9", "display": "Chronic kidney disease, unspecified"}),
    (r"\b(congestive )?heart failure\b|\bchf\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "I50.9", "display": "Heart failure, unspecified"}),
    (r"\bhypothyroid(ism)?\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "E03.9", "display": "Hypothyroidism, unspecified"}),
    (r"\bepilepsy\b|\bseizure disorder\b",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "G40.909", "display": "Epilepsy, unspecified, not intractable"}),
    (r"\b(prosthetic|artificial|mechanical) heart valve\b|\bheart valve replace",
     {"type": "condition", "system": ICD10_SYSTEM, "code": "Z95.2", "display": "Presence of prosthetic heart valve"}),
    (r"\bdabigatran\b|\bpradaxa\b",
     {"type": "medication", "system": RXNORM_SYSTEM, "code": "1037042", "display": "Dabigatran (Pradaxa)", "drug_class": "anticoagulant"}),
    (r"\bmetformin\b|\bglucophage\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "6809", "display": "Metformin"}),
    (r"\blisinopril\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "29046", "display": "Lisinopril"}),
    (r"\batorvastatin\b|\blipitor\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "83367", "display": "Atorvastatin (Lipitor)"}),
    (r"\bamlodipine\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "17767", "display": "Amlodipine"}),
    (r"\bmetoprolol\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "6918", "display": "Metoprolol"}),
    (r"\blevothyroxine\b|\bsynthroid\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "10582", "display": "Levothyroxine"}),
    (r"\bprednisone\b", {"type": "medication", "system": RXNORM_SYSTEM, "code": "8640", "display": "Prednisone"}),
    (r"\blatex\b.{0,20}\ballerg|\ballerg\w*\s+to\s+latex\b",
     {"type": "allergy", "system": SNOMED_SYSTEM, "code": "300916003", "display": "Latex allergy"}),
]

# (regex, LOINC concept). A number following the name within the clause becomes the value.
LAB_LEXICON = [
    (r"\bhba1c\b|\bhemoglobin a1c\b|\ba1c\b",
     {"code": "4548-4", "display": "Hemoglobin A1c/Hemoglobin.total in Blood", "text": "HbA1c", "unit": "%"}),
    (r"\binr\b", {"code": "6301-6", "display": "INR in Platelet poor plasma by Coagulation assay", "text": "INR", "unit": "{INR}"}),
    (r"\bplatelets?( count)?\b",
     {"code": "777-3", "display": "Platelets [#/volume] in Blood by Automated count", "text": "Platelet count", "unit": "10*3/uL"}),
    (r"\begfr\b", {"code": "33914-3", "display": "Glomerular filtration rate/1.73 sq M.predicted", "text": "eGFR", "unit": "mL/min/{1.73_m2}"}),
    (r"\bcreatinine\b", {"code": "2160-0", "display": "Creatinine [Mass/volume] in Serum or Plasma", "text": "Creatinine", "unit": "mg/dL"}),
]

KNOWN_SYSTEMS = {
    "condition": (ICD10_SYSTEM, SNOMED_SYSTEM),
    "medication": (RXNORM_SYSTEM,),
    "allergy": (SNOMED_SYSTEM, RXNORM_SYSTEM),
    "observation": (LOINC_SYSTEM,),
}
_CODE_FORMAT = {
    ICD10_SYSTEM: r"[A-TV-Z]\d[0-9A-Z](\.[0-9A-Z]{1,4})?",
    RXNORM_SYSTEM: r"\d{1,8}",
    SNOMED_SYSTEM: r"\d{6,18}",
    LOINC_SYSTEM: r"\d{1,7}-\d",
}
# Letters (any script), spaces, dot, apostrophe, hyphen. No digits: a name must never look like an ID.
_NAME = r"[^\W\d_](?:[^\W\d_]|[ .'\-]){0,79}"
MAX_ENTRIES = 200

# Context guards for record extraction: a concept that follows one of these in its clause is not an
# active finding of this patient. Checked deterministically; excluded items are reported, not dropped silently.
_GUARDS = [
    ("negated", r"\b(no|not|denies|denied|deny|negative for|without|ruled out|rule out|r/o|never|nkda|nka|free of|absence of)\b|n't\b"),
    ("family history", r"\b(family history|family hx|fh:|fhx|mother|father|brother|sister|sibling|parents?|grand(mother|father)|aunt|uncle|son|daughter)\b"),
    ("discontinued", r"\b(stopped|discontinued|d/c'?e?d|former(ly)?|previously on|no longer|ceased|weaned off|came off|completed (a )?course)\b"),
]
# A sub-clause with none of these is a list continuation ("no diabetes, hypertension") and inherits the guard
_AFFIRMATIVE = r"\b(takes?|taking|is on|on|has|have|had|diagnosed|history of|hx of|started|uses?|using|prescribed|continues?|currently|allergic)\b"
_SENTENCE_SPLIT = r"[.;\n](?!\d)|\b(?:but|however|except|although)\b"
_SUBCLAUSE_SPLIT = r",(?!\d)|\band\b"

_RESULT = r"\s*(?:level|result|value)?\s*(?:of|is|was|at|:|=)?\s*(\d+(?:\.\d+)?)"
_CLAUSE_SPLIT = r"[,.;\n](?!\d)|\band\b"  # keeps decimals like "9.2" intact


# =====================================================================
# Persistence
# =====================================================================

def _empty_state() -> Dict[str, Any]:
    return {
        "version": 1, "patients": [], "fhir": [], "fhir_aliases": {}, "cs_aliases": {}, "documents": [],
        # Edits to data this registry did not create (seeded demo patients): applied on top at load
        "fhir_overrides": {}, "fhir_deleted": [], "patient_overrides": {},
    }


_state: Dict[str, Any] = _empty_state()
_state_path: Optional[str] = ""  # "" = never loaded; None = persistence disabled


def _registry_path() -> Optional[str]:
    """
    Registry file in effect. Under pytest the real file is never touched unless a test opts in
    with MDIN_RUNTIME_REGISTRY: a dev-created patient must not leak into the suite, and a test
    patient must not leak into the demo.
    """
    override = os.environ.get(REGISTRY_ENV)
    if override:
        return override
    return None if "pytest" in sys.modules else DEFAULT_REGISTRY_FILE


def _save() -> None:
    if not _state_path:
        return
    os.makedirs(os.path.dirname(os.path.abspath(_state_path)), exist_ok=True)
    tmp_path = f"{_state_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(_state, f, indent=2)
    os.replace(tmp_path, _state_path)


def _apply_state() -> None:
    """Re-applies persisted additions to the in-memory stores; anything already present is left alone."""
    carestack = carestack_services()
    from ..schemas.carestack import CareStackPatient

    known_ids = {p.id for p in carestack.MOCK_PATIENTS}
    for record in _state["patients"]:
        if record["id"] not in known_ids:
            carestack.MOCK_PATIENTS.append(CareStackPatient(**record))
    for alias, cs_id in _state["cs_aliases"].items():
        carestack.CARESTACK_PATIENT_ALIASES.setdefault(alias, cs_id)
    for canonical, aliases in _state["fhir_aliases"].items():
        aliases[:] = [a for a in aliases if _is_id_alias(a)]  # registries written before name aliases were dropped
        current = PATIENT_ALIASES.setdefault(canonical, [])
        # IDs and MRNs only: resolve_patient_aliases matches by substring, so a name alias could cross-link charts
        current.extend(a for a in aliases if a not in current)
    for resource in _state["fhir"]:
        bucket = fhir_client._local_cache.setdefault(resource["resourceType"], [])
        if not any(r.get("id") == resource["id"] for r in bucket):
            bucket.append(resource)
    _apply_edits()
    for doc in _state["documents"]:
        patient = next((p for p in carestack.MOCK_PATIENTS if p.id == doc["patient_id"]), None)
        if patient and not any(d.get("document_id") == doc["document_id"] for d in patient.attached_documents):
            patient.attached_documents.append(doc)
            for key in (patient.id, patient.mrn):
                carestack.CARESTACK_PATIENT_DOCUMENTS.setdefault(key, []).append(doc)


def load_runtime_registry() -> Dict[str, int]:
    """(Re)loads the registry file in effect and applies it. Safe to call repeatedly."""
    global _state, _state_path
    _state_path = _registry_path()
    _state = _empty_state()
    if _state_path and os.path.exists(_state_path):
        try:
            with open(_state_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("registry root must be an object")
            for key, default in _empty_state().items():
                if key in loaded and key != "version":
                    if not isinstance(loaded[key], type(default)):
                        raise ValueError(f"'{key}' must be a {type(default).__name__}")
                    _state[key] = loaded[key]
        except (OSError, ValueError) as exc:
            print(f"[MDIN PatientRegistry] Ignoring unreadable registry {_state_path}: {exc}")
            _state = _empty_state()
    try:
        _apply_state()
    except Exception as exc:  # hand-edited file of the wrong shape must not take the backend down
        print(f"[MDIN PatientRegistry] Ignoring malformed registry {_state_path}: {exc.__class__.__name__}: {exc}")
        _state = _empty_state()
    return {"patients": len(_state["patients"]), "fhir_resources": len(_state["fhir"]), "documents": len(_state["documents"])}


def _ensure_loaded() -> None:
    if _state_path == "" or _state_path != _registry_path():
        load_runtime_registry()


# =====================================================================
# Helpers
# =====================================================================

def _digits(value: str) -> str:
    return "".join(c for c in value or "" if c.isdigit()).lstrip("0")


def _next_patient_number() -> int:
    """_find_carestack_patient also matches on bare digits, so the number must be unused by any ID or MRN."""
    carestack = carestack_services()
    used = {_digits(p.id) for p in carestack.MOCK_PATIENTS} | {_digits(p.mrn) for p in carestack.MOCK_PATIENTS}
    number = 3001
    while str(number) in used:
        number += 1
    return number


def _is_id_alias(alias: str) -> bool:
    return bool(re.fullmatch(r"(cs|mrn)-\d+", alias or ""))


def _valid_date(value: Optional[str], field: str) -> str:
    raw = (value or "").strip()
    raw = raw[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}T[\d:.+\-Zz]+", raw) else raw  # a full timestamp is fine
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            raise ValueError
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        raise ValueError(f"{field} must be an ISO date (YYYY-MM-DD), got '{str(value)[:40]}'")


def _valid_name(value: Optional[str], field: str) -> str:
    name = re.sub(r"\s+", " ", (value or "").strip())
    if not name:
        raise ValueError("first_name and last_name are required")
    if not re.fullmatch(_NAME, name):
        raise ValueError(f"{field} may only contain letters, spaces, apostrophes, dots and hyphens (max 80 characters)")
    return name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _track_fhir(resource: Dict[str, Any]) -> None:
    fhir_client._local_cache.setdefault(resource["resourceType"], []).append(resource)
    _state["fhir"].append(resource)


def _link_aliases(fhir_id: str, aliases: List[str]) -> None:
    current = PATIENT_ALIASES.setdefault(fhir_id, [])
    persisted = _state["fhir_aliases"].setdefault(fhir_id, [])
    for alias in aliases:
        if alias not in current:
            current.append(alias)
        if alias not in persisted:
            persisted.append(alias)


def _patient_summary(patient, already_existed: bool) -> Dict[str, Any]:
    return {
        "patient_id": patient.id,
        "mrn": patient.mrn,
        "name": f"{patient.first_name} {patient.last_name}",
        "birth_date": patient.birth_date,
        "gender": patient.gender,
        "already_existed": already_existed,
        "planned_procedures": [
            {"code": t.code, "description": t.description, "tooth_number": t.tooth_number}
            for t in patient.active_treatment_plan
        ],
    }


def _build_procedures(planned_procedures: Optional[List[Any]]) -> list:
    carestack = carestack_services()
    from ..schemas.carestack import DentalProcedure

    catalog = {c.Code: c.Description for c in carestack.MOCK_PROCEDURE_CODES}
    procedures = []
    for item in planned_procedures or []:
        item = {"code": item} if isinstance(item, str) else dict(item or {})
        code = str(item.get("code") or item.get("cdt_code") or "").upper().strip()
        if not re.fullmatch(r"D\d{4}", code):
            raise ValueError(f"'{code or item}' is not a CDT procedure code (expected e.g. D7140)")
        procedures.append(DentalProcedure(
            code=code,
            description=item.get("description") or catalog.get(code) or f"Dental procedure {code}",
            tooth_number=str(item["tooth_number"]) if item.get("tooth_number") else None,
            status="proposed",
        ))
    return procedures


# =====================================================================
# Patients
# =====================================================================

def create_patient(
    first_name: str,
    last_name: str,
    birth_date: str,
    gender: str = "unknown",
    phone: Optional[str] = None,
    email: Optional[str] = None,
    planned_procedures: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    _ensure_loaded()
    carestack = carestack_services()
    from ..schemas.carestack import CareStackPatient

    first_name, last_name = _valid_name(first_name, "first_name"), _valid_name(last_name, "last_name")
    birth_date = _valid_date(birth_date, "birth_date")
    if birth_date > date.today().isoformat() or birth_date < "1900-01-01":
        raise ValueError(f"birth_date must be between 1900-01-01 and today, got '{birth_date}'")
    gender = (gender or "unknown").lower().strip()
    if gender not in ("male", "female", "other", "unknown"):
        gender = "unknown"
    procedures = _build_procedures(planned_procedures)

    for existing in carestack.MOCK_PATIENTS:
        if (existing.first_name.lower(), existing.last_name.lower(), existing.birth_date) == (
            first_name.lower(), last_name.lower(), birth_date
        ):
            return _patient_summary(existing, already_existed=True)

    number = _next_patient_number()
    patient = CareStackPatient(
        id=f"CS-{number}",
        mrn=f"MRN-{number}",
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        gender=gender,
        email=email or None,
        phone=phone or None,
        next_appointment=f"{(date.today() + timedelta(days=7)).isoformat()} 09:00:00" if procedures else None,
        primary_dentist="Dr. Sarah Jenkins, DDS",
        active_treatment_plan=procedures,
    )
    carestack.MOCK_PATIENTS.append(patient)
    _state["patients"].append(patient.model_dump(exclude={"attached_documents", "medical_clearance"}))

    cs_aliases = {patient.id.lower(): patient.id, patient.mrn.lower(): patient.id}
    carestack.CARESTACK_PATIENT_ALIASES.update(cs_aliases)
    _state["cs_aliases"].update(cs_aliases)

    _create_fhir_patient(patient)
    _save()
    return _patient_summary(patient, already_existed=False)


def _create_fhir_patient(patient) -> Dict[str, Any]:
    """Medical-record twin of a CareStack patient, cross-linked through PATIENT_ALIASES."""
    fhir_id = f"rec-{_digits(patient.id) or uuid.uuid4().hex[:8]}"
    telecom = [{"system": s, "value": v} for s, v in (("phone", patient.phone), ("email", patient.email)) if v]
    resource = {
        "resourceType": "Patient",
        "id": fhir_id,
        "meta": {"source": "mao-patient-registry"},
        "identifier": [
            {"system": "urn:mdin:mrn", "value": patient.mrn, "use": "official"},
            {"system": "urn:carestack:patient-id", "value": patient.id, "use": "secondary"},
        ],
        "active": True,
        "name": [{"use": "official", "family": patient.last_name, "given": [patient.first_name]}],
        "gender": patient.gender or "unknown",
        "birthDate": patient.birth_date,
        **({"telecom": telecom} if telecom else {}),
    }
    _track_fhir(resource)
    # No name alias: resolve_patient_aliases matches by substring, so "Sam Park" would also resolve
    # "Sam Parker". Names are resolved by exact match in find_patient_id_by_name() instead.
    _link_aliases(fhir_id, [patient.id.lower(), patient.mrn.lower()])
    return resource


def _resolve_targets(patient_id: str) -> Tuple[Any, Dict[str, Any], str]:
    """(CareStack patient or None, FHIR Patient, display name); creates the FHIR Patient when missing."""
    carestack = carestack_services()
    info = clearance_service()._resolve_patient_info(patient_id)
    cs_patient = info.get("cs_patient") or carestack._find_carestack_patient(patient_id)
    fhir_patient = info.get("fhir_patient")
    if not cs_patient and not fhir_patient and find_patient_id_by_name(patient_id):
        return _resolve_targets(find_patient_id_by_name(patient_id))
    if not cs_patient and not fhir_patient:
        raise KeyError(f"No CareStack or EHR record matches '{patient_id}'")
    if not fhir_patient and cs_patient:
        # The CareStack ID may be aliased to an EHR record under another key
        fhir_patient = clearance_service()._resolve_patient_info(cs_patient.id).get("fhir_patient")
    if not fhir_patient:
        fhir_patient = _create_fhir_patient(cs_patient)
    elif cs_patient and fhir_patient["id"].lower() not in resolve_patient_aliases(cs_patient.id):
        # Matched through an identifier only: link the IDs so subject references resolve
        _link_aliases(fhir_patient["id"].lower(), [cs_patient.id.lower(), cs_patient.mrn.lower()])
    name = f"{cs_patient.first_name} {cs_patient.last_name}" if cs_patient else info.get("name", "")
    return cs_patient, fhir_patient, name


def find_patient_id_by_name(name: str) -> Optional[str]:
    """CareStack ID for an exact, unambiguous "First Last" match; None otherwise. Never a substring match."""
    wanted = re.sub(r"\s+", " ", (name or "").strip().lower())
    matches = [p.id for p in carestack_services().MOCK_PATIENTS if f"{p.first_name} {p.last_name}".lower() == wanted]
    return matches[0] if len(matches) == 1 else None


def list_patients() -> List[Dict[str, Any]]:
    _ensure_loaded()
    carestack = carestack_services()
    resolve = clearance_service()._resolve_patient_info
    return [
        {
            "patient_id": p.id,
            "mrn": p.mrn,
            "name": f"{p.first_name} {p.last_name}",
            "birth_date": p.birth_date,
            "gender": p.gender,
            "next_appointment": p.next_appointment,
            "planned_procedures": [f"{t.code} {t.description}" for t in p.active_treatment_plan],
            "medical_record_linked": bool(resolve(p.id).get("fhir_patient")),
        }
        for p in carestack.MOCK_PATIENTS
    ]


# =====================================================================
# Deterministic coding
# =====================================================================

def _lexicon_matches(text: str) -> List[Dict[str, Any]]:
    lowered = text.lower()
    return [dict(t) for pattern, t in NARRATIVE_LEXICON + SUPPLEMENTAL_LEXICON if re.search(pattern, lowered)]


def _lab_match(text: str) -> Optional[Dict[str, Any]]:
    """LOINC concept named in the text, with "value" when a result directly follows the name ("INR of 2.8")."""
    lowered = text.lower()
    for pattern, lab in LAB_LEXICON:
        if re.search(pattern, lowered):
            result = re.search(f"(?:{pattern})" + _RESULT, lowered)
            return dict(lab, **({"value": float(result.group(result.lastindex))} if result else {}))
    return None


def _validated_code(raw: Dict[str, Any], entry_type: str, text: str) -> Tuple[str, str]:
    """
    (code, system) of an explicitly supplied code. The code must be well-formed for a known system
    and must not contradict what the lexicon makes of the text ("headache" + I48.91 is refused).
    """
    code = str(raw["code"]).strip().upper()
    system = str(raw.get("system") or DEFAULT_SYSTEM[entry_type]).strip()
    if system not in KNOWN_SYSTEMS[entry_type]:
        raise ValueError(f"'{system[:60]}' is not an accepted code system for a {entry_type}")
    if not re.fullmatch(_CODE_FORMAT[system], code):
        raise ValueError(f"'{code[:32]}' is not a well-formed code for {system}")
    if entry_type == "observation":
        lab = _lab_match(text) if text else None
        expected = [lab["code"]] if lab and system == LOINC_SYSTEM else []
    else:
        expected = [m["code"] for m in _lexicon_matches(text) if m["type"] == entry_type and m["system"] == system]
    # ICD-10: a more specific code in the same category (E11.65 for "type 2 diabetes") is not a contradiction
    same = (lambda a, b: a[:3] == b[:3]) if system == ICD10_SYSTEM else (lambda a, b: a == b)
    if expected and not any(same(code, e.upper()) for e in expected):
        raise ValueError(f"code {code} does not match '{text[:60]}' (the lexicon codes it as {', '.join(expected)}); "
                         "fix the code or leave it blank to use the lexicon")
    return code, system


def _normalize_entry(raw: Dict[str, Any], lenient_dates: bool = False) -> Tuple[Dict[str, Any], bool]:
    """
    Returns (entry with type/text/code/system/display resolved, recognized).
    lenient_dates: a non-ISO onset ("last year", from a model) is dropped and reported, not fatal.
    """
    if not isinstance(raw, dict):
        raise ValueError("each entry must be an object with a type and text")
    entry_type = str(raw.get("type") or "").lower().strip()
    text = str(raw.get("text") or raw.get("display") or "").strip()
    if entry_type not in ENTRY_TYPES:
        raise ValueError(f"entry type must be one of {', '.join(ENTRY_TYPES)}, got '{raw.get('type')}'")
    if not text and not raw.get("code"):
        raise ValueError("each entry needs text or a code")

    entry: Dict[str, Any] = {"type": entry_type, "text": text}
    for key in ("onset", "value", "unit"):
        if raw.get(key) not in (None, ""):
            entry[key] = raw[key]
    if entry.get("onset"):
        try:
            entry["onset"] = _valid_date(str(entry["onset"]), "onset")
        except ValueError:
            if not lenient_dates:
                raise
            entry["onset_dropped"] = str(entry.pop("onset"))[:40]

    if raw.get("code"):  # explicit user input wins over the lexicon, once it passes validation
        code, system = _validated_code(raw, entry_type, text)
        entry.update(code=code, system=system, display=str(raw.get("display") or text or code), coded_by="user")
        entry["text"] = text or entry["display"]
        return entry, True

    if entry_type == "observation":
        lab = _lab_match(text)
        if lab:
            entry.update(code=lab["code"], system=LOINC_SYSTEM, display=lab["display"], text=lab["text"], coded_by="lexicon")
            entry.setdefault("unit", lab["unit"])
            if "value" in lab:
                entry.setdefault("value", lab["value"])
        return entry, bool(lab)

    # "penicillin" typed into the allergy list has no "allergic to" around it
    matches = _lexicon_matches(text) or (_lexicon_matches(f"allergy to {text}") if entry_type == "allergy" else [])
    match = next((m for m in matches if m["type"] == entry_type), matches[0] if matches else None)
    if not match:
        return entry, False
    # A drug typed under conditions (or vice versa) is filed under what it actually is
    entry.update(type=match["type"], code=match["code"], system=match["system"], display=match["display"], coded_by="lexicon")
    return entry, True


def _value_key(value: Any) -> str:
    """7, 7.0 and "7" are the same result."""
    try:
        return str(float(value))
    except (TypeError, ValueError):
        return str(value)


def _entry_key(entry: Dict[str, Any]) -> Tuple:
    identity = (entry.get("system"), entry["code"]) if entry.get("code") else ("text", entry["text"].lower())
    if entry["type"] == "observation":
        return (entry["type"], *identity, _value_key(entry.get("value")), entry.get("onset") or date.today().isoformat())
    return (entry["type"], *identity)


def _existing_keys(fhir_id: str) -> set:
    def from_concept(kind: str, concept: Dict[str, Any], extra: tuple = ()) -> List[Tuple]:
        keys = [(kind, c.get("system"), c.get("code"), *extra) for c in concept.get("coding") or []]
        if concept.get("text"):
            keys.append((kind, "text", concept["text"].lower(), *extra))
        return keys

    keys: set = set()
    info = clearance_service()._resolve_patient_info(fhir_id)
    for cond in info["conditions"]:
        keys.update(from_concept("condition", cond.get("code") or {}))
    for med in info["medications"]:
        keys.update(from_concept("medication", med.get("medicationCodeableConcept") or {}))
    for allergy in info["allergies"]:
        keys.update(from_concept("allergy", allergy.get("code") or {}))
    for obs in fhir_client._local_cache.get("Observation", []):
        if (obs.get("subject") or {}).get("reference", "").split("/")[-1].lower() == fhir_id.lower():
            value = (obs.get("valueQuantity") or {}).get("value", obs.get("valueString"))
            extra = (_value_key(value), (obs.get("effectiveDateTime") or "")[:10] or None)
            keys.update(from_concept("observation", obs.get("code") or {}, extra))
    return keys


def _to_fhir(entry: Dict[str, Any], fhir_id: str, patient_name: str, source: str, confirmed: bool = True) -> Dict[str, Any]:
    # Lexicon-coded items carry the canonical display (the Risk agent keys off it); labs keep their short name
    canonical = entry.get("coded_by") == "lexicon" and entry["type"] != "observation"
    concept: Dict[str, Any] = {"text": entry["display"] if canonical else entry["text"]}
    if entry.get("code"):
        concept["coding"] = [{"system": entry["system"], "code": entry["code"], "display": entry["display"]}]
    subject = {"reference": f"Patient/{fhir_id}", "display": patient_name}
    base = {
        "resourceType": _RESOURCE_TYPE[entry["type"]],
        "id": f"{entry['type'][:4]}-{uuid.uuid4().hex[:10]}",
        "meta": {"source": f"mao-patient-registry:{source}"},
    }
    note = [{"text": f"Recorded via {source}: {entry['text']}"}] if entry.get("text") else []
    if not confirmed:
        note.append({"text": "Extracted automatically from an imported record; not yet confirmed by a clinician."})
    today = date.today().isoformat()
    verification = ("confirmed", "Confirmed") if confirmed else ("unconfirmed", "Unconfirmed")

    if entry["type"] == "condition":
        return {**base,
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active", "display": "Active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status", "code": verification[0], "display": verification[1]}]},
                "code": concept, "subject": subject, "recordedDate": today,
                **({"onsetDateTime": entry["onset"]} if entry.get("onset") else {}), "note": note}
    if entry["type"] == "medication":
        return {**base, "status": "active", "intent": "order", "medicationCodeableConcept": concept, "subject": subject,
                **({"authoredOn": entry["onset"]} if entry.get("onset") else {}), "note": note}
    if entry["type"] == "allergy":
        return {**base,
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", "code": "active", "display": "Active"}]},
                "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification", "code": verification[0], "display": verification[1]}]},
                "type": "allergy", "code": concept, "patient": subject, "recordedDate": entry.get("onset") or today, "note": note}

    observation = {**base, "status": "final",
                   "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory", "display": "Laboratory"}]}],
                   "code": concept, "subject": subject, "effectiveDateTime": f"{entry.get('onset') or today}T00:00:00Z"}
    try:
        observation["valueQuantity"] = {"value": float(entry["value"]), "unit": entry.get("unit") or "",
                                        "system": UCUM_SYSTEM, "code": entry.get("unit") or ""}
    except (KeyError, TypeError, ValueError):
        if entry.get("value") not in (None, ""):
            observation["valueString"] = str(entry["value"])
    return observation


# =====================================================================
# History & previous records
# =====================================================================

def validate_entries(entries: Optional[List[Dict[str, Any]]], lenient_dates: bool = False) -> List[Tuple[Dict[str, Any], bool]]:
    """Normalizes a whole batch up front, so a bad entry rejects the batch before anything is written."""
    if len(entries or []) > MAX_ENTRIES:
        raise ValueError(f"at most {MAX_ENTRIES} entries per request")
    return [_normalize_entry(raw, lenient_dates) for raw in entries or []]


def add_history_entries(
    patient_id: str,
    entries: List[Dict[str, Any]],
    source: str = "manual",
    lenient_dates: bool = False,
    confirmed: bool = True,
) -> Dict[str, Any]:
    """confirmed=False writes verificationStatus "unconfirmed" (entries nobody reviewed, e.g. a record imported from chat)."""
    _ensure_loaded()
    source = re.sub(r"[^a-z0-9-]", "", (source or "manual").lower())[:40] or "manual"
    normalized = validate_entries(entries, lenient_dates)  # all-or-nothing: validate before the first write
    cs_patient, fhir_patient, name = _resolve_targets(patient_id)
    fhir_id = fhir_patient["id"]
    seen = _existing_keys(fhir_id)
    added, skipped, unrecognized = [], [], []

    for entry, recognized in normalized:
        key = _entry_key(entry)
        if key in seen:
            skipped.append(entry)
            continue
        seen.add(key)
        resource = _to_fhir(entry, fhir_id, name, source, confirmed)
        _track_fhir(resource)
        entry["resource_id"] = resource["id"]
        added.append(entry)
        if not recognized:
            unrecognized.append(entry)

    _save()
    return {
        "patient_id": cs_patient.id if cs_patient else fhir_id,
        "added": added,
        "skipped_duplicates": skipped,
        "unrecognized": unrecognized,
        "verification": "confirmed" if confirmed else "unconfirmed",
        **({"onset_dropped": dropped} if (dropped := [e for e in added + skipped if e.get("onset_dropped")]) else {}),
    }


def _guard_reason(sub_lower: str, match_start: int) -> Optional[str]:
    for reason, pattern in _GUARDS:
        found = re.search(pattern, sub_lower)
        if found and found.start() < match_start:
            return reason
    return None


def _concept_start(sub_lower: str, concept: Dict[str, Any]) -> int:
    """Where the concept is named in the sub-clause (the lexicon entry that produced it is found by code)."""
    for pattern, template in NARRATIVE_LEXICON + SUPPLEMENTAL_LEXICON:
        if template["code"] == concept["code"]:
            found = re.search(pattern, sub_lower)
            if found:
                return found.start()
    return len(sub_lower)


def extract_entries_from_text(text: str) -> Dict[str, Any]:
    """
    Deterministic: Intake agent narrative extractor + the supplemental and lab lexicons. Never an LLM.
    Concepts that are negated ("denies warfarin"), family history ("father had diabetes") or
    discontinued ("stopped clopidogrel") are returned under "excluded" with the reason, not as entries.
    """
    intake = IntakeAgent()
    found: List[Tuple[Dict[str, Any], Optional[str]]] = []
    for sentence in re.split(_SENTENCE_SPLIT, text or ""):
        inherited: Optional[str] = None
        for sub in re.split(_SUBCLAUSE_SPLIT, sentence or ""):
            lowered = sub.lower()
            own = next((reason for reason, pattern in _GUARDS if re.search(pattern, lowered)), None)
            if not own and re.search(_AFFIRMATIVE, lowered):
                inherited = None  # "no aspirin, takes warfarin": the second clause stands on its own

            concepts = [(c, _concept_start(lowered, c)) for c in intake.extract_from_narrative(sub)]
            concepts += [(dict(template, evidence=sub.strip()), _concept_start(lowered, template))
                         for pattern, template in SUPPLEMENTAL_LEXICON if re.search(pattern, lowered)]
            lab = _lab_match(sub)
            if lab and "value" in lab:  # a lab name without a result is not a finding
                concepts.append(({"type": "observation", "system": LOINC_SYSTEM, "code": lab["code"], "display": lab["display"],
                                  "text": lab["text"], "value": lab["value"], "unit": lab["unit"], "evidence": sub.strip()},
                                 re.search(_lab_pattern(lab["code"]), lowered).start()))
            reasons = [_guard_reason(lowered, start) if own else inherited for _, start in concepts]
            found.extend((concept, reason) for (concept, _), reason in zip(concepts, reasons))
            if own:  # carries over to a list continuation only when it governed this clause ("diabetes not controlled" does not)
                inherited = own if reasons and all(reasons) else None

    entries, excluded, seen = [], [], set()
    for concept, reason in found:
        key = (concept["type"], concept["code"], concept.get("value"), bool(reason))
        if key in seen:
            continue
        seen.add(key)
        entry = {k: concept[k] for k in ("type", "code", "system", "display", "onset", "value", "unit", "evidence") if concept.get(k) not in (None, "")}
        entry["text"] = concept.get("text") or concept["display"]
        if reason:
            excluded.append(dict(entry, reason=reason))
        else:
            entries.append(entry)
    return {"entries": entries, "excluded": excluded}


def _lab_pattern(code: str) -> str:
    return next(pattern for pattern, lab in LAB_LEXICON if lab["code"] == code)


def import_previous_record(
    patient_id: str,
    title: str,
    text: str,
    record_date: Optional[str] = None,
    source_facility: Optional[str] = None,
    entries: Optional[List[Dict[str, Any]]] = None,
    reviewed: Optional[bool] = None,
) -> Dict[str, Any]:
    """reviewed: did a person tick these entries? Defaults to "yes if entries were supplied"; the chat import
    supplies model-assisted entries nobody has looked at yet and passes reviewed=False."""
    _ensure_loaded()
    if not (text or "").strip():
        raise ValueError("text is required")
    if record_date:
        record_date = _valid_date(record_date, "record_date")
    cs_patient, _, _ = _resolve_targets(patient_id)
    if not cs_patient:
        raise KeyError(f"'{patient_id}' has no CareStack chart to attach a document to")
    carestack = carestack_services()

    # The caller's confirmed entries win; extraction is the fallback, never an addition to them
    supplied = entries is not None
    reviewed = supplied if reviewed is None else reviewed
    extraction = None if supplied else extract_entries_from_text(text)
    chosen = entries if supplied else extraction["entries"]
    validate_entries(chosen)  # before the document is filed: a rejected import must leave nothing behind
    document = carestack.save_patient_document(
        cs_patient.id,
        document_type=PREVIOUS_RECORD_DOCUMENT_TYPE,
        title=(title or "").strip() or "Previous medical record",
        file_content=text,
        metadata={"record_date": record_date, "source_facility": source_facility, "imported_at": _now(),
                  "entries_submitted": len(chosen)},
    )
    _state["documents"].append(document)
    # Entries nobody reviewed (no preview step, e.g. imported from chat) are charted as unconfirmed
    result = add_history_entries(cs_patient.id, chosen, source="previous-record", confirmed=reviewed)
    return {"patient_id": result["patient_id"], "document_id": document["document_id"],
            "added": result["added"], "skipped_duplicates": result["skipped_duplicates"], "unrecognized": result["unrecognized"],
            "verification": result["verification"],
            "excluded": [] if supplied else extraction["excluded"]}


# =====================================================================
# Removal (tests and demo reset)
# =====================================================================

def remove_patient(patient_id: str) -> bool:
    """Removes everything this registry added for a patient; seeded data is never touched."""
    _ensure_loaded()
    carestack = carestack_services()
    cs_patient = carestack._find_carestack_patient(patient_id)
    cs_id = cs_patient.id if cs_patient else patient_id
    keys = {cs_id.lower(), patient_id.lower()} | ({cs_patient.mrn.lower()} if cs_patient else set())
    fhir_ids = {c for c, aliases in _state["fhir_aliases"].items() if keys & set(aliases)}
    linked = clearance_service()._resolve_patient_info(cs_id).get("fhir_patient")
    if linked:
        fhir_ids.add(linked["id"].lower())

    def _subject(resource: Dict[str, Any]) -> str:
        ref = (resource.get("subject") or resource.get("patient") or {}).get("reference", "")
        return ref.split("/")[-1].lower()

    doomed = {r["id"] for r in _state["fhir"]
              if (r["resourceType"] == "Patient" and r["id"].lower() in fhir_ids) or _subject(r) in fhir_ids}
    for bucket in fhir_client._local_cache.values():
        bucket[:] = [r for r in bucket if r.get("id") not in doomed]
    _state["fhir"] = [r for r in _state["fhir"] if r["id"] not in doomed]

    created_here = any(p["id"] == cs_id for p in _state["patients"])
    for fhir_id in fhir_ids:
        persisted = _state["fhir_aliases"].pop(fhir_id, [])
        if any(r["id"].lower() == fhir_id for r in fhir_client._local_cache["Patient"]):
            PATIENT_ALIASES[fhir_id] = [a for a in PATIENT_ALIASES.get(fhir_id, []) if a not in persisted]
        else:
            PATIENT_ALIASES.pop(fhir_id, None)

    doc_ids = {d["document_id"] for d in _state["documents"] if d["patient_id"] == cs_id}
    _state["documents"] = [d for d in _state["documents"] if d["document_id"] not in doc_ids]
    if cs_patient:
        cs_patient.attached_documents[:] = [d for d in cs_patient.attached_documents if d.get("document_id") not in doc_ids]
    for key in list(carestack.CARESTACK_PATIENT_DOCUMENTS):
        kept = [d for d in carestack.CARESTACK_PATIENT_DOCUMENTS[key] if d.get("document_id") not in doc_ids]
        if len(kept) != len(carestack.CARESTACK_PATIENT_DOCUMENTS[key]):
            if kept:
                carestack.CARESTACK_PATIENT_DOCUMENTS[key] = kept
            else:
                carestack.CARESTACK_PATIENT_DOCUMENTS.pop(key)

    if created_here:
        carestack.MOCK_PATIENTS[:] = [p for p in carestack.MOCK_PATIENTS if p.id != cs_id]
        _state["patients"] = [p for p in _state["patients"] if p["id"] != cs_id]
        for alias in [a for a, target in _state["cs_aliases"].items() if target == cs_id]:
            _state["cs_aliases"].pop(alias)
            carestack.CARESTACK_PATIENT_ALIASES.pop(alias, None)
        for key in (cs_id, cs_id.lower()):
            carestack.PATIENT_MEDICAL_ALERTS.pop(key, None)
    _save()
    return created_here or bool(doomed) or bool(doc_ids)


# =====================================================================
# Chart editing (manual mode): every history item and patient detail is editable
# =====================================================================

_TYPE_OF_RESOURCE = {v: k for k, v in _RESOURCE_TYPE.items()}
_DEMOGRAPHIC_FIELDS = ("first_name", "last_name", "birth_date", "gender", "phone", "email", "next_appointment", "primary_dentist")


def _apply_edits() -> None:
    """Re-applies persisted overrides/deletions/demographic edits on top of seeded + runtime data."""
    carestack = carestack_services()
    deleted = set(_state["fhir_deleted"])
    for bucket in fhir_client._local_cache.values():
        bucket[:] = [r for r in bucket if r.get("id") not in deleted]
    for resource_id, resource in _state["fhir_overrides"].items():
        bucket = fhir_client._local_cache.setdefault(resource["resourceType"], [])
        for other in fhir_client._local_cache.values():  # an edit may have re-filed it under another type
            if other is not bucket:
                other[:] = [r for r in other if r.get("id") != resource_id]
        index = next((i for i, r in enumerate(bucket) if r.get("id") == resource_id), None)
        if index is None:
            bucket.append(resource)
        else:
            bucket[index] = resource
    for cs_id, patch in _state["patient_overrides"].items():
        patient = next((p for p in carestack.MOCK_PATIENTS if p.id == cs_id), None)
        if patient:
            _apply_patient_patch(patient, patch)


def _apply_patient_patch(patient, patch: Dict[str, Any]) -> None:
    for field in _DEMOGRAPHIC_FIELDS:
        if field in patch:
            setattr(patient, field, patch[field])
    if "planned_procedures" in patch:
        patient.active_treatment_plan = _build_procedures(patch["planned_procedures"])
    fhir_patient = clearance_service()._resolve_patient_info(patient.id).get("fhir_patient")
    if fhir_patient:
        fhir_patient["name"] = [{"use": "official", "family": patient.last_name, "given": [patient.first_name]}]
        fhir_patient["birthDate"] = patient.birth_date
        fhir_patient["gender"] = patient.gender


def _find_resource(resource_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    for resource_type in _TYPE_OF_RESOURCE:
        bucket = fhir_client._local_cache.get(resource_type, [])
        for resource in bucket:
            if resource.get("id") == resource_id:
                return resource, bucket
    return None, None


def _subject_id(resource: Dict[str, Any]) -> str:
    ref = (resource.get("subject") or resource.get("patient") or {}).get("reference", "")
    return ref.split("/")[-1].lower()


def _chart_entry(resource: Dict[str, Any]) -> Dict[str, Any]:
    entry_type = _TYPE_OF_RESOURCE[resource["resourceType"]]
    concept = resource.get("medicationCodeableConcept" if entry_type == "medication" else "code") or {}
    codings = concept.get("coding") or []
    preferred = next((c for c in codings if c.get("system") in (ICD10_SYSTEM, RXNORM_SYSTEM, LOINC_SYSTEM)), codings[0] if codings else {})
    onset = resource.get("onsetDateTime") or resource.get("authoredOn") or resource.get("effectiveDateTime") or resource.get("recordedDate") or ""
    quantity = resource.get("valueQuantity") or {}
    verification = ((resource.get("verificationStatus") or {}).get("coding") or [{}])[0].get("code")
    return {
        "resource_id": resource["id"],
        "type": entry_type,
        "text": concept.get("text") or preferred.get("display") or preferred.get("code") or "",
        "code": preferred.get("code") or "",
        "system": preferred.get("system") or "",
        "onset": onset[:10],
        "value": quantity.get("value", resource.get("valueString")),
        "unit": quantity.get("unit") or "",
        "unconfirmed": verification == "unconfirmed",
        "added_at_runtime": any(r["id"] == resource["id"] for r in _state["fhir"]),
    }


def get_chart(patient_id: str) -> Dict[str, Any]:
    """Editable view of a chart: demographics, treatment plan, documents and every history item with its id."""
    _ensure_loaded()
    cs_patient, fhir_patient, name = _resolve_targets(patient_id)
    fhir_id = fhir_patient["id"].lower()
    entries = [
        _chart_entry(resource)
        for resource_type in _TYPE_OF_RESOURCE
        for resource in fhir_client._local_cache.get(resource_type, [])
        if _subject_id(resource) == fhir_id
    ]
    return {
        "patient_id": cs_patient.id if cs_patient else fhir_patient["id"],
        "mrn": cs_patient.mrn if cs_patient else "",
        "name": name,
        "first_name": cs_patient.first_name if cs_patient else "",
        "last_name": cs_patient.last_name if cs_patient else "",
        "birth_date": (cs_patient.birth_date if cs_patient else fhir_patient.get("birthDate")) or "",
        "gender": (cs_patient.gender if cs_patient else fhir_patient.get("gender")) or "unknown",
        "phone": (cs_patient.phone if cs_patient else "") or "",
        "email": (cs_patient.email if cs_patient else "") or "",
        "last_visit": (cs_patient.last_visit if cs_patient else "") or "",
        "next_appointment": (cs_patient.next_appointment if cs_patient else "") or "",
        "primary_dentist": (cs_patient.primary_dentist if cs_patient else "") or "",
        "editable_details": cs_patient is not None,
        "planned_procedures": [
            {"code": t.code, "description": t.description, "tooth_number": t.tooth_number or ""}
            for t in (cs_patient.active_treatment_plan if cs_patient else [])
        ],
        "documents": [
            {k: d.get(k) for k in ("document_id", "document_type", "title", "upload_timestamp")}
            for d in (cs_patient.attached_documents if cs_patient else [])
        ],
        "entries": entries,
    }


def update_patient(patient_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_loaded()
    cs_patient = carestack_services()._find_carestack_patient(patient_id)
    if not cs_patient:
        raise KeyError(f"No CareStack chart matches '{patient_id}'")
    patch: Dict[str, Any] = {}
    for field in _DEMOGRAPHIC_FIELDS:
        if changes.get(field) is None:
            continue
        value = str(changes[field]).strip()
        if field in ("first_name", "last_name"):
            value = _valid_name(value, field)
        elif field == "birth_date":
            value = _valid_date(value, field)
        elif field == "gender":
            value = value.lower() if value.lower() in ("male", "female", "other", "unknown") else "unknown"
        patch[field] = value[:120]
    if changes.get("planned_procedures") is not None:
        _build_procedures(changes["planned_procedures"])  # validates CDT codes before anything is written
        patch["planned_procedures"] = changes["planned_procedures"]
    if not patch:
        raise ValueError("no editable fields supplied")

    _apply_patient_patch(cs_patient, patch)
    _state["patient_overrides"][cs_patient.id] = {**_state["patient_overrides"].get(cs_patient.id, {}), **patch}
    record = next((r for r in _state["patients"] if r["id"] == cs_patient.id), None)
    if record is not None:  # created here: keep the stored record itself current too
        record.update(cs_patient.model_dump(mode="json"))
    _save()
    return get_chart(cs_patient.id)


def update_history_entry(patient_id: str, resource_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """Re-normalizes the edited item through the same lexicon as a new one, keeping its id."""
    _ensure_loaded()
    _, fhir_patient, name = _resolve_targets(patient_id)
    resource, bucket = _find_resource(resource_id)
    if resource is None or _subject_id(resource) != fhir_patient["id"].lower():
        raise KeyError(f"History item '{resource_id}' is not on this patient's chart")

    current = _chart_entry(resource)
    merged = {k: current.get(k) for k in ("type", "text", "onset", "value", "unit")}
    merged.update({k: v for k, v in changes.items() if k in merged and v is not None})
    if changes.get("code"):
        merged.update(code=changes["code"], system=changes.get("system"))
    entry, recognized = _normalize_entry(merged)

    replacement = _to_fhir(entry, fhir_patient["id"], name, "manual-edit", confirmed=True)
    replacement["id"] = resource_id
    bucket.remove(resource)
    fhir_client._local_cache.setdefault(replacement["resourceType"], []).append(replacement)

    runtime_index = next((i for i, r in enumerate(_state["fhir"]) if r["id"] == resource_id), None)
    if runtime_index is not None:
        _state["fhir"][runtime_index] = replacement
    else:
        _state["fhir_overrides"][resource_id] = replacement
    _save()
    return {**_chart_entry(replacement), "recognized": recognized}


def delete_history_entry(patient_id: str, resource_id: str) -> Dict[str, Any]:
    _ensure_loaded()
    _, fhir_patient, _ = _resolve_targets(patient_id)
    resource, bucket = _find_resource(resource_id)
    if resource is None or _subject_id(resource) != fhir_patient["id"].lower():
        raise KeyError(f"History item '{resource_id}' is not on this patient's chart")
    bucket.remove(resource)
    runtime = [r for r in _state["fhir"] if r["id"] == resource_id]
    if runtime:
        _state["fhir"] = [r for r in _state["fhir"] if r["id"] != resource_id]
    else:
        _state["fhir_overrides"].pop(resource_id, None)
        if resource_id not in _state["fhir_deleted"]:
            _state["fhir_deleted"].append(resource_id)
    _save()
    return {"deleted": resource_id}
