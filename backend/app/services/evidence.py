"""
Literature evidence for risk findings, from Europe PMC (https://europepmc.org/RestfulWebService):
free, no API key, peer-reviewed abstracts. Quotes are verbatim sentences from the abstract with a
link to the source, never generated text. Network failures degrade to "no evidence", never an error.
"""

import asyncio
import html
import re
from typing import Any, Dict, List, Optional

import httpx

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
TIMEOUT_SECONDS = 8.0
MAX_QUOTE_CHARS = 320

# rule_id -> (search query, words that make a sentence worth quoting)
RULE_QUERIES: Dict[str, Dict[str, Any]] = {
    "CARDIAC_STENT_DAPT": {
        "query": '("dental extraction" OR "tooth extraction" OR "oral surgery") AND ("dual antiplatelet" OR clopidogrel OR "coronary stent")',
        "keywords": ("antiplatelet", "clopidogrel", "aspirin", "stent", "bleeding", "discontinu", "interrupt", "thrombo", "hemosta", "haemosta"),
    },
    "BISPHOSPHONATE_MRONJ": {
        "query": '("medication-related osteonecrosis of the jaw" OR MRONJ) AND (extraction OR "dentoalveolar surgery") AND (bisphosphonate OR denosumab)',
        "keywords": ("osteonecrosis", "mronj", "bisphosphonate", "extraction", "risk", "drug holiday", "prevent", "denosumab"),
    },
    "ANTICOAGULANT_HEMORRHAGE": {
        "query": '("dental extraction" OR "tooth extraction" OR "oral surgery") AND (warfarin OR "direct oral anticoagulant" OR anticoagulant) AND bleeding',
        "keywords": ("warfarin", "anticoagul", "inr", "bleeding", "hemosta", "haemosta", "interrupt", "continu", "tranexamic"),
    },
    "SYSTEMIC_MODIFIERS": {
        "query": '("dental extraction" OR "oral surgery" OR "dental treatment") AND (hypertension OR "diabetes mellitus") AND (epinephrine OR healing OR complication)',
        "keywords": ("hypertens", "blood pressure", "epinephrine", "diabet", "hba1c", "healing", "infection", "vasoconstrictor"),
    },
    "ENDOCARDITIS_PROPHYLAXIS": {
        "query": '"infective endocarditis" AND "antibiotic prophylaxis" AND (dental OR dentistry) AND (guideline OR recommendation)',
        "keywords": ("prophylaxis", "endocarditis", "prosthetic", "valve", "amoxicillin", "recommend", "guideline", "high-risk", "high risk"),
    },
    "DRUG_ALLERGY": {
        "query": '("penicillin allergy" OR "latex allergy") AND (dental OR dentistry) AND (alternative OR clindamycin OR management OR prophylaxis)',
        "keywords": ("allerg", "penicillin", "clindamycin", "azithromycin", "latex", "alternative", "anaphyla", "cephalosporin"),
    },
}

_cache: Dict[str, List[Dict[str, Any]]] = {}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def pick_quote(abstract: str, keywords: tuple) -> str:
    """The abstract sentence that says the most about this risk, verbatim. Conclusions win ties."""
    # Structured abstracts carry section headings (<h4>Conclusions</h4>, "RESULTS:"): not part of the sentence
    body = re.sub(r"<h\d[^>]*>.*?</h\d>", " ", abstract or "", flags=re.S | re.I)
    sentences = [re.sub(r"^[A-Z][A-Za-z /&-]{2,30}:\s+", "", s.strip()) for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(\[])", _clean(body))]
    sentences = [s for s in sentences if 40 <= len(s) <= MAX_QUOTE_CHARS]
    if not sentences:
        return ""
    total = len(sentences)

    def score(item) -> float:
        index, sentence = item
        lowered = sentence.lower()
        hits = sum(1 for k in keywords if k in lowered)
        concluding = 0.5 if re.search(r"\b(conclu|recommend|should|suggest|safe|risk)", lowered) else 0.0
        return hits + concluding + 0.3 * (index / total)  # later sentences tend to carry the finding

    best_index, best = max(enumerate(sentences), key=score)
    return best if score((best_index, best)) >= 2 else ""


async def search(rule_id: str, client: httpx.AsyncClient, limit: int = 3) -> List[Dict[str, Any]]:
    spec = RULE_QUERIES.get(rule_id)
    if not spec:
        return []
    if rule_id in _cache:
        return _cache[rule_id][:limit]
    try:
        response = await client.get(EUROPE_PMC_URL, params={
            "query": f'({spec["query"]}) AND HAS_ABSTRACT:Y AND (PUB_TYPE:"review" OR PUB_TYPE:"systematic review" OR PUB_TYPE:"guideline" OR PUB_TYPE:"meta-analysis")',
            "format": "json", "resultType": "core", "pageSize": 12,  # default order is relevance
        }, timeout=TIMEOUT_SECONDS)
        results = response.json().get("resultList", {}).get("result", []) if response.status_code == 200 else []
    except (httpx.HTTPError, ValueError):
        return []

    evidence = []
    for item in results:
        quote = pick_quote(item.get("abstractText", ""), spec["keywords"])
        if not quote:
            continue
        source, ident = item.get("source") or "MED", item.get("id") or item.get("pmid")
        evidence.append({
            "title": _clean(item.get("title", "")).rstrip("."),
            "journal": ((item.get("journalInfo") or {}).get("journal") or {}).get("title") or item.get("bookOrReportDetails", {}).get("publisher", ""),
            "year": item.get("pubYear") or "",
            "authors": _clean(item.get("authorString", ""))[:120],
            "quote": quote,
            "url": f"https://europepmc.org/article/{source}/{ident}",
            "source": "Europe PMC",
        })
    if evidence:
        _cache[rule_id] = evidence
    return evidence[:limit]


async def for_rules(rule_ids: List[str], client: Optional[httpx.AsyncClient] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Evidence for several findings at once, fetched concurrently."""
    owns_client = client is None
    client = client or httpx.AsyncClient(headers={"User-Agent": "MDIN-risk-check/0.1 (hackathon demo)"})
    try:
        found = await asyncio.gather(*(search(rule_id, client) for rule_id in rule_ids))
    finally:
        if owns_client:
            await client.aclose()
    return dict(zip(rule_ids, found))
