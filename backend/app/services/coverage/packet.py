"""
What leaves the building. Two documents, both built only from the verified analysis:

  * a PRE-TREATMENT ESTIMATE REQUEST for a "potential pathway": the confirmed clinical facts, the payer's own
    wording they satisfy, and the documentation the payer asks for. It is a request for a decision, not a claim;
    a named person must sign it off. No procedure code is chosen for the medical side: that is a certified coder's job.
  * a plain-language NOTE for the patient when there is no pathway, quoting why.
"""

from datetime import date
from typing import Any, Dict

from ..agents.base import carestack_services

_last_analysis: Dict[str, Dict[str, Any]] = {}  # latest analysis per patient, kept server-side so a packet cannot be built from edited client data


def remember(result: Dict[str, Any]) -> None:
    _last_analysis[result["patient_id"]] = result


def _cite(criterion: Dict[str, Any]) -> str:
    source = criterion["source"]
    where = f"{source['insurer']}, {source['title']}" + (f", section \"{source['heading']}\"" if source["heading"] else "")
    return f"> \"{criterion['quote']}\"\n> ({where}{'; ' + source['review'] if source['review'] else ''}) {source['url']}".rstrip()


def build(patient_id: str, reviewed_by: str) -> Dict[str, Any]:
    result = _last_analysis.get(patient_id)
    if not result:
        raise KeyError("Run the coverage check for this patient first.")
    outcome = result["determination"]["outcome"]
    if outcome not in ("potential_pathway", "no_pathway"):
        raise ValueError("A document is only produced for a potential pathway or a clear 'no pathway'. This case needs human review first.")
    reviewed_by = (reviewed_by or "").strip()
    if outcome == "potential_pathway" and len(reviewed_by) < 3:
        raise ValueError("A pre-treatment estimate request must be signed off by a named person.")

    facts, insurance, criteria = result["facts"], result["insurance"], result["criteria"]
    supports = [c for c in criteria if c["kind"] == "supports" and c["met"] == "yes"]
    paperwork = [c for c in criteria if c["kind"] in ("documentation", "prior_authorization")]
    excludes = [c for c in criteria if c["kind"] == "excludes" and c["applies_to_case"]]
    lines = []

    if outcome == "potential_pathway":
        title = f"Pre-treatment estimate request - {result['patient_name']} - {facts['procedure']['label']}"
        lines += [f"# Request for pre-treatment estimate / benefit determination", "",
                  f"**Date:** {date.today().isoformat()}  ", f"**To:** {insurance['medical']['insurer']} - medical benefits  ",
                  f"**Member:** {result['patient_name']} · member ID {insurance['medical']['member_id'] or 'on file'} · plan {insurance['medical']['plan_name'] or 'on file'}  ",
                  f"**Dental benefit status:** {insurance['dental']['status']}", "",
                  "We ask whether the service below is eligible under the member's **medical** plan. This is a request for a "
                  "determination before treatment, not a claim.", "", "## Proposed service", "",
                  f"- {facts['procedure']['label']} (CDT {facts['procedure']['cdt_code']})"]
        if facts["diagnosis"]:
            lines.append(f"- Diagnosis: {facts['diagnosis']}")
        if facts["imaging"]:
            lines.append(f"- Imaging: {facts['imaging']}")
        if facts["symptoms"]:
            lines.append(f"- Symptoms: {'; '.join(facts['symptoms'])}")
        lines += ["", "## Why we believe this falls under your published policy", ""]
        for c in supports:
            lines += [f"**{c['requirement']}**", "", f"Clinical finding: {c['fact']}", "", _cite(c), ""]
        if paperwork:
            lines += ["## Documentation and authorization your policy asks for", ""]
            for c in paperwork:
                lines += [f"- {c['requirement']}", "", _cite(c), ""]
        if not result["determination"].get("plan_verified"):
            lines += ["## Note", "", "The member's plan document was not available to us. Please confirm against the member-specific benefit plan.", ""]
        lines += ["## Clinical note", "", facts["clinical_note"] or "(none supplied)", "",
                  f"Reviewed and approved for sending by **{reviewed_by}**. Medical procedure coding to be confirmed by a certified coder."]
        kind = "Pre-Treatment Estimate Request"
    else:
        title = f"Coverage explanation - {result['patient_name']} - {facts['procedure']['label']}"
        lines += ["# Why this is not billed to your medical insurance", "",
                  f"**Date:** {date.today().isoformat()}  ", f"**Patient:** {result['patient_name']}", "",
                  f"We checked whether **{facts['procedure']['label']}** could be covered by your medical plan "
                  f"({insurance['medical']['insurer'] or 'insurer not recorded'}), because your dental benefit is {insurance['dental']['status']}.", "",
                  result["determination"]["reason"], ""]
        if excludes:
            lines += ["## What the insurer's published policy says", ""] + [part for c in excludes for part in (_cite(c), "")]
        lines += ["This is our reading of published policy, not a decision by your insurer. You can ask them for a pre-treatment "
                  "estimate if you would like their answer in writing. We are happy to discuss payment options."]
        kind = "Coverage Explanation"

    content = "\n".join(lines)
    carestack = carestack_services()
    record = carestack.save_patient_document(
        patient_id=patient_id, document_type=kind, title=title, file_content=content,
        metadata={"generated_by": "Dental Coverage Recovery Agent", "outcome": outcome, "reviewed_by": reviewed_by or None,
                  "sources": sorted({c["source"]["url"] for c in criteria if c["source"]["url"]})},
    )
    return {"document_id": record.get("document_id"), "document_type": kind, "title": title, "content_markdown": content}
