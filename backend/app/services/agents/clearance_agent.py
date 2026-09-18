"""
MAO Medical Clearance Agent (Step 15).

Autonomy trigger: `clearance_status == "REQUIRED_PENDING"`.

1. Locates the attending cardiologist / PCP from the patient's medical record.
2. Drafts the clinical justification citing the planned procedure and systemic findings.
3. Dispatches a Digital Clearance Passport (HL7 FHIR Task + CommunicationRequest) to the
   physician's EHR InBasket -> TRANSMITTED_TO_EHR.
4. Escalation loop: no response after 48 hours -> nudge SMS to the patient + front-desk flag.
5. Ingests the physician's free-text endorsement, extracts structured restrictions and
   moves the CareStack appointment to CLEARED_FOR_CARE.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ...models.agent_state import MAOState, make_agent_log, utc_now_iso
from ...models.clearance import AttendingPhysician, ClearanceDecision
from .base import clearance_service, primary_cdt

ESCALATION_THRESHOLD_HOURS = 48

_NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4}
_DRUGS = {
    "aspirin": "ASPIRIN", "asa": "ASPIRIN",
    "plavix": "CLOPIDOGREL", "clopidogrel": "CLOPIDOGREL",
    "warfarin": "WARFARIN", "coumadin": "WARFARIN",
    "eliquis": "APIXABAN", "apixaban": "APIXABAN",
    "xarelto": "RIVAROXABAN", "rivaroxaban": "RIVAROXABAN",
    "dapt": "DAPT", "dual antiplatelet": "DAPT", "antiplatelet": "ANTIPLATELET_THERAPY",
    "alendronate": "ALENDRONATE", "fosamax": "ALENDRONATE",
}
_DRUG_PATTERN = "|".join(sorted((re.escape(k) for k in _DRUGS), key=len, reverse=True))
_MAINTAIN = r"(?:maintain|continue|keep (?:taking|on)|stay on|do not (?:stop|hold|interrupt)|don't (?:stop|hold))"
_HOLD = r"(?:hold|stop|discontinue|pause|withhold|suspend)"
# Rejection is evaluated before approval, and a negated approval ("not approved", "do not approve",
# "can't clear", "not OK to proceed") is a rejection. A false REJECTED is the safe direction; a false APPROVED is not.
# The lookahead keeps "do not stop aspirin, cleared to proceed" an approval.
_NEGATED_APPROVAL = (
    r"(?:\b(?:not|never|no longer|cannot|unable to)\b|n't\b)"
    r"(?:(?!\b(?:stop|hold|interrupt|discontinue|pause|withhold|suspend)\b)[^.;,\n]){0,30}?"
    r"\b(?:approv\w*|clear\w*|ok(?:ay)? to proceed|proceed|go ahead)\b"
)
_REJECT = (
    r"\b(not cleared|do not proceed|cannot clear|clearance denied|denied|defer (?:the )?(?:procedure|surgery|extraction)|postpone\w*"
    r"|reject\w*|declin\w+|refus\w+|disapprov\w*|(?<!not )(?<!no longer )contraindicated|unsafe to proceed)\b|" + _NEGATED_APPROVAL
)


class MedicalClearanceAgent:
    name = "Medical Clearance Agent"
    icon = "stethoscope"

    # -- 1. physician lookup ---------------------------------------------------

    def locate_physician(self, state: MAOState) -> AttendingPhysician:
        """Prefers the practitioner named on the patient's FHIR record; falls back to specialty routing."""
        service = clearance_service()
        info = service._resolve_patient_info(state["patient_id"])
        default = service._locate_attending_physician(info.get("conditions", []), info.get("medications", []))

        for gp in (info.get("fhir_patient") or {}).get("generalPractitioner", []):
            if not gp.get("display"):
                continue
            extensions = {e.get("url", "").rsplit("-", 1)[-1]: e.get("valueString") for e in gp.get("extension", [])}
            same = gp["display"] == default.name
            return AttendingPhysician(
                npi=(gp.get("identifier") or {}).get("value") or default.npi,
                name=gp["display"],
                specialty=extensions.get("specialty") or default.specialty,
                facility_name=extensions.get("facility") or default.facility_name,
                fhir_endpoint=default.fhir_endpoint if same else "",
                direct_email=default.direct_email if same else "",
            )
        return default

    # -- 2. justification ------------------------------------------------------

    def draft_justification(self, state: MAOState, cdt_code: str, physician: AttendingPhysician) -> str:
        evaluation = next(
            (e for e in reversed(state.get("risk_evaluations") or []) if e.get("hazard_level") == "CRITICAL"),
            (state.get("risk_evaluations") or [{}])[-1],
        )
        records = state.get("medical_records") or {}
        lines = [
            f"{physician.name} - pre-operative medical clearance is requested for {state.get('patient_name') or state['patient_id']} "
            f"(DOB {state.get('dob') or 'unknown'}), scheduled for dental procedure CDT {cdt_code}.",
            "Systemic findings: " + ("; ".join(evaluation.get("contraindications", [])) or "none recorded") + ".",
            "Active conditions: " + (", ".join(records.get("conditions", [])) or "none") + ".",
            "Active medications: " + (", ".join(records.get("medications", [])) or "none") + ".",
            "Please advise on: (1) continuation or interruption of antithrombotic therapy, "
            "(2) vasoconstrictor / epinephrine limits, (3) any additional peri-operative precautions.",
        ]
        return "\n".join(lines)

    # -- 4. escalation ---------------------------------------------------------

    def check_escalation(self, state: MAOState, hours_since_dispatch: Optional[float] = None) -> Dict[str, Any]:
        """Returns a state update if the clearance request has gone unanswered past the threshold, else {}."""
        protocol = dict(state.get("clearance_protocol") or {})
        if state.get("clearance_status") != "TRANSMITTED_TO_EHR" or protocol.get("escalated_at"):
            return {}
        if hours_since_dispatch is None:
            try:
                dispatched = datetime.fromisoformat(protocol.get("dispatched_at", ""))
            except ValueError:
                return {}
            hours_since_dispatch = (datetime.now(timezone.utc) - dispatched) / timedelta(hours=1)
        if hours_since_dispatch <= ESCALATION_THRESHOLD_HOURS:
            return {}

        physician = (state.get("assigned_medical_md") or {}).get("name") or "your physician"
        sms = (
            f"Hi {(state.get('patient_name') or 'there').split(',')[-1].split()[0]}, your dental team is still waiting on "
            f"medical clearance from {physician} for your upcoming procedure. A quick call to their office "
            f"will help us keep your appointment. Reply STOP to opt out."
        )
        protocol.update({
            "escalated_at": utc_now_iso(),
            "escalation": {
                "hours_without_response": round(hours_since_dispatch, 1),
                "patient_nudge_sms": {"channel": "sms", "status": "simulated_sent", "body": sms},
                "front_desk_flag": "Clearance overdue >48h - confirm or reschedule appointment",
            },
        })
        appointment = dict(state.get("appointment") or {}, status="REQUIRES_ACTION", front_desk_flag=True)
        return {
            "clearance_protocol": protocol,
            "appointment": appointment,
            "agent_logs": [make_agent_log(
                self.name,
                "Escalation: no physician response after 48h",
                f"{hours_since_dispatch:.0f}h since dispatch. Sent nudge SMS to patient and flagged the front-desk schedule.",
                "bell-ring",
            )],
        }

    # -- 5. endorsement ingestion ------------------------------------------------

    def parse_physician_endorsement(self, text: str) -> Dict[str, Any]:
        """
        Extracts a structured clearance protocol from a physician's free-text reply, e.g.
        "Cleared for extractions, keep epinephrine minimal, limit to 2 carpules 1:100k epi, maintain Aspirin"
        -> restrictions ["LIMIT_EPINEPHRINE_2_CARPULES", "MAINTAIN_ASPIRIN"].
        """
        lowered = " ".join((text or "").lower().split())
        restrictions: List[str] = []

        def add(code: str) -> None:
            if code not in restrictions:
                restrictions.append(code)

        if re.search(r"\b(no|avoid|without)\s+(epi\b|epinephrine|vasoconstrictor)", lowered):
            add("AVOID_EPINEPHRINE")
        elif re.search(r"\bepi(nephrine)?\b|vasoconstrictor", lowered):
            carpules = re.search(r"(\d+|one|two|three|four)\s*(?:carpules?|cartridges?)", lowered)
            if carpules:
                raw = carpules.group(1)
                add(f"LIMIT_EPINEPHRINE_{_NUMBER_WORDS.get(raw, raw)}_CARPULES")
            elif re.search(r"minimal|minimi[sz]e|limit|restrict|reduce", lowered):
                add("MINIMIZE_EPINEPHRINE")

        held: List[str] = []
        for match in re.finditer(rf"{_MAINTAIN}\s+(?:the\s+|patient on\s+)?({_DRUG_PATTERN})", lowered):
            add(f"MAINTAIN_{_DRUGS[match.group(1)]}")
        for match in re.finditer(rf"(?<!not ){_HOLD}\s+(?:the\s+)?({_DRUG_PATTERN})(?:\s+(?:for\s+)?(\d+)\s*(hours?|hrs?|days?))?", lowered):
            if re.search(rf"(?:do not|don't)\s+{_HOLD}\s+(?:the\s+)?{re.escape(match.group(1))}", lowered):
                continue
            drug = _DRUGS[match.group(1)]
            held.append(drug)
            hours = int(match.group(2)) * (24 if match.group(3).startswith("day") else 1) if match.group(2) else None
            add(f"HOLD_{drug}" + (f"_{hours}H" if hours else ""))

        if re.search(r"prophyla|premedicat", lowered) and not re.search(r"no (antibiotic )?prophyla", lowered):
            add("ANTIBIOTIC_PROPHYLAXIS_REQUIRED")
        if re.search(r"hemosta|suture|tranexamic", lowered):
            add("LOCAL_HEMOSTATIC_MEASURES")
        if re.search(r"monitor (bp|blood pressure|vitals)", lowered):
            add("MONITOR_BLOOD_PRESSURE")

        inr = re.search(
            r"inr\b(?:\s*(?:target|goal|range|should be|must be|kept|of|at|is|:|below|under|less than|<=?))*"
            r"\s*(\d(?:\.\d)?(?:\s*-\s*\d(?:\.\d)?)?)",
            lowered,
        )
        inr_target = inr.group(1).replace(" ", "") if inr else ""
        if inr and re.search(r"below|under|<|less than", inr.group(0)):
            inr_target = f"<{inr_target}"

        rejected = bool(re.search(_REJECT, lowered))
        approved = not rejected and bool(re.search(r"\b(cleared|clear to|approved?|ok to proceed|may proceed|proceed with)\b", lowered))
        decision = "REJECTED" if rejected else ("APPROVED_WITH_CONDITIONS" if restrictions else "APPROVED") if approved else "UNDETERMINED"

        return {
            "decision": decision,
            "restrictions": restrictions,
            "hold_medications": bool(held),
            "held_medications": held,
            "inr_target": inr_target,
            "raw_text": text,
        }

    def ingest_physician_response(self, state: MAOState, text: str, signed_by: Optional[str] = None) -> Dict[str, Any]:
        """Applies a physician reply to the shared state and writes the outcome back to CareStack."""
        parsed = self.parse_physician_endorsement(text)
        signed_by = signed_by or (state.get("assigned_medical_md") or {}).get("name") or "Attending Physician"
        protocol = dict(state.get("clearance_protocol") or {})
        protocol.update({
            "restrictions": parsed["restrictions"],
            "hold_medications": parsed["hold_medications"],
            "held_medications": parsed["held_medications"],
            "inr_target": parsed["inr_target"],
            "signed_by": signed_by,
            "decision": parsed["decision"],
            "physician_response": text,
            "responded_at": utc_now_iso(),
        })

        if parsed["decision"] in ("REJECTED", "UNDETERMINED"):
            # Never auto-clear on an ambiguous or negative reply: leave it with a human
            protocol["requires_staff_review"] = True
            return {
                "clearance_protocol": protocol,
                "appointment": dict(state.get("appointment") or {}, status="REQUIRES_ACTION", front_desk_flag=True),
                "agent_logs": [make_agent_log(
                    self.name,
                    "Physician response needs staff review",
                    f'Could not confirm clearance from reply "{text}" (parsed as {parsed["decision"]}). '
                    "Appointment stays on hold and is flagged for the front desk.",
                    "alert-octagon",
                )],
            }

        writeback = False
        if protocol.get("request_id"):
            try:
                clearance_service().record_physician_decision(ClearanceDecision(
                    request_id=protocol["request_id"],
                    decision=parsed["decision"],
                    physician_notes=text,
                    coagulation_parameters={
                        "target_inr_range": parsed["inr_target"] or "N/A",
                        "hold_medication": parsed["hold_medications"],
                        "hold_hours": 0,
                        "restrictions": parsed["restrictions"],
                    },
                    signed_by=signed_by,
                ))
                writeback = True
            except Exception:
                writeback = False
        protocol["carestack_writeback"] = writeback

        return {
            "clearance_status": "APPROVED_WITH_CONDITIONS" if parsed["restrictions"] else "CLEARED",
            "clearance_protocol": protocol,
            "appointment": dict(state.get("appointment") or {}, status="CLEARED_FOR_CARE", front_desk_flag=False),
            "agent_logs": [make_agent_log(
                self.name,
                "Ingested physician endorsement",
                f"{signed_by}: {parsed['decision']}. Restrictions: {', '.join(parsed['restrictions']) or 'none'}. "
                "CareStack appointment updated to CLEARED_FOR_CARE.",
                "check-circle",
            )],
        }

    # -- node ---------------------------------------------------------------------

    async def __call__(self, state: MAOState) -> Dict[str, Any]:
        cdt_code = primary_cdt(state, "D7140")
        physician = self.locate_physician(state)
        justification = self.draft_justification(state, cdt_code, physician)
        logs = [make_agent_log(
            self.name,
            "Located attending physician",
            f"{physician.name}, {physician.specialty} - {physician.facility_name} (NPI {physician.npi}).",
            "user-search",
        )]

        passport = clearance_service().create_clearance_passport(
            patient_id=state["patient_id"],
            cdt_code=cdt_code,
            ehr_data={"physician": physician.model_dump()},
        )
        # Replace the engine's generic rationale with this agent's procedure-specific draft
        passport.clinical_justification = justification
        if isinstance(passport.fhir_task, dict):
            passport.fhir_task["description"] = justification
        task_id = passport.fhir_task.get("id") if isinstance(passport.fhir_task, dict) else None

        logs.append(make_agent_log(
            self.name,
            "Dispatched FHIR Task to physician EHR InBasket",
            f"Task {task_id or passport.request_id} for CDT {cdt_code} transmitted to {physician.name} "
            f"({physician.facility_name}). Awaiting endorsement; escalation after {ESCALATION_THRESHOLD_HOURS}h.",
            "send",
        ))

        update: Dict[str, Any] = {
            "clearance_status": "TRANSMITTED_TO_EHR",
            "assigned_medical_md": {
                "name": physician.name,
                "npi": physician.npi,
                "facility": physician.facility_name,
                "specialty": physician.specialty,
                "direct_endpoint": physician.fhir_endpoint,
            },
            "clearance_protocol": dict(
                state.get("clearance_protocol") or {},
                request_id=str(passport.request_id),
                fhir_task_id=task_id,
                dispatched_at=utc_now_iso(),
                clinical_justification=justification,
            ),
            "agent_logs": logs,
        }

        # Simulation hooks let one run demonstrate the asynchronous half of the loop
        simulation = state.get("simulation") or {}
        for step in (
            lambda s: self.check_escalation(s, simulation["hours_since_dispatch"]) if simulation.get("hours_since_dispatch") else {},
            lambda s: self.ingest_physician_response(s, simulation["physician_response"]) if simulation.get("physician_response") else {},
        ):
            follow_up = step({**state, **{k: v for k, v in update.items() if k != "agent_logs"}})
            logs.extend(follow_up.pop("agent_logs", []))
            update.update(follow_up)
        return update
