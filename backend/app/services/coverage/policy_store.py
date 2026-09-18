"""
Policy store: fetches the published payer policy documents listed in data/coverage_sources.json,
caches them locally and turns them into quotable chunks.

Nothing about coverage is authored in this codebase. The registry holds URLs only; every statement
the Coverage Recovery Agent makes is a quote from one of these cached documents. The cache lives in
data/policy_cache/ and is git-ignored: payer policies are copyrighted, so they are kept on the
practice's machine, never redistributed, and only short attributed quotes with a link are shown.
"""

import hashlib
import html as html_lib
import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

import httpx

from ..document_ingest import DocumentError, document_to_text

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
REGISTRY_FILE = os.path.join(DATA_DIR, "coverage_sources.json")
CACHE_ENV = "MDIN_POLICY_CACHE"
USER_AGENT = "Mozilla/5.0 (compatible; MDIN-coverage-recovery/0.1; dental practice policy lookup)"
MAX_CHUNK_CHARS = 1600
FETCH_TIMEOUT = 40.0

_CDT = re.compile(r"\bD\d{4}\b")
_CPT = re.compile(r"\b\d{5}\b")
_ICD = re.compile(r"\b[A-TV-Z]\d{2}(?:\.\d{1,4}[A-Z]?)?\b")
_CODE_GROUP = re.compile(r"[^.:\n]{0,120}\bcodes?\b[^.:\n]{0,80}\b(?:not covered|covered|criteria|related|other)\b[^.:\n]{0,80}:", re.I)
_REVIEW = re.compile(r"(Last Review(?:ed)?|Effective Date|Last Published|Revision Date|Last Updated|Page Last Modified)[^\d]{0,30}(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|[A-Z][a-z]+ \d{1,2}, \d{4})")


def cache_dir() -> str:
    path = os.environ.get(CACHE_ENV) or os.path.join(DATA_DIR, "policy_cache")
    os.makedirs(path, exist_ok=True)
    return path


def load_registry() -> Dict[str, Any]:
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------
# HTML -> text that keeps headings, so chunks know which section they came from
# ---------------------------------------------------------------------

class _Extractor(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "form", "svg"}
    BLOCK = {"p", "div", "li", "tr", "br", "table", "ul", "ol", "section", "td", "th"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip = 0
        self._heading = False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif re.fullmatch(r"h[1-5]", tag):
            self._heading = True
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")  # keep the level: h2 is the policy's top-level section
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
        elif re.fullmatch(r"h[1-5]", tag):
            self._heading = False
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    parser = _Extractor()
    parser.feed(raw)
    text = html_lib.unescape("".join(parser.parts)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


# ---------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------

_NOT_POLICY = re.compile(r"\b(background|references?|bibliograph|literature|glossary|appendix|revision|history|table of contents|"
                         r"clinical evidence|description of (procedure|service)|u\.s\. food|regulatory status|sources)\b", re.I)
_CODE_SECTION = re.compile(r"\b(CPT|HCPCS|ICD-?10|CDT|Coding|Applicable Codes)\b", re.I)


def _kind(section: str, heading: str) -> str:
    """policy | codes | background. Only policy and codes are ever retrieved or quoted: a literature-review
    paragraph from a Background section is not a coverage statement and must not be presented as one."""
    if _CODE_SECTION.search(section) or _CODE_SECTION.search(heading):
        return "codes"
    if _NOT_POLICY.search(section) or _NOT_POLICY.search(heading):
        return "background"
    return "policy"


def _sections(text: str) -> List[Dict[str, str]]:
    sections, section, heading, lines = [], "", "", []

    def flush() -> None:
        if "".join(lines).strip():
            sections.append({"section": section, "heading": heading, "text": "\n".join(lines).strip()})

    for line in text.splitlines():
        stripped = line.strip()
        marked = re.match(r"(#{1,5}) (.*)", stripped)
        # PDF text has no markup: a short line without a full stop, in Title Case or CAPS, reads as a heading
        plain = (not marked and 0 < len(stripped) <= 70 and not stripped.endswith((".", ",", ";", ":"))
                 and len(stripped.split()) <= 9 and (stripped.isupper() or stripped.istitle()) and not re.search(r"\d{4,}", stripped))
        if marked or plain:
            flush()
            lines = []
            heading = (marked.group(2) if marked else stripped).strip()
            if (marked and len(marked.group(1)) <= 2) or (plain and stripped.isupper()) or (plain and _NOT_POLICY.search(heading)):
                section = heading
        else:
            lines.append(line)
    flush()
    return sections


def _split(text: str) -> List[str]:
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    pieces, current = [], ""
    for sentence in re.split(r"(?<=[.;:])\s+|\n+", text):
        if current and len(current) + len(sentence) + 1 > MAX_CHUNK_CHARS:
            pieces.append(current.strip())
            current = ""
        current = f"{current} {sentence}".strip()
        while len(current) > MAX_CHUNK_CHARS:  # one enormous "sentence" (a code table)
            pieces.append(current[:MAX_CHUNK_CHARS])
            current = current[MAX_CHUNK_CHARS:]
    if current.strip():
        pieces.append(current.strip())
    return pieces


def _codes(text: str, is_code_table: bool) -> Dict[str, List[str]]:
    codes = {"cdt": sorted(set(_CDT.findall(text))), "icd10": sorted({c for c in _ICD.findall(text) if "." in c})}
    # Bare 5-digit numbers are only trusted as CPT inside the document's own code tables (not zip codes, not dates)
    codes["cpt"] = sorted(set(_CPT.findall(text))) if is_code_table else []
    return codes


def chunk_document(source: Dict[str, Any], text: str) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    group = ""
    for section in _sections(text):
        heading = section["heading"]
        kind = _kind(section["section"], heading)
        in_code_section = kind == "codes"
        for piece in _split(section["text"]):
            label = _CODE_GROUP.search(piece)
            if label:
                group = re.sub(r"\s+", " ", label.group(0)).strip(" :")
            is_table = in_code_section or bool(label)
            chunks.append({
                "id": f"{source['id']}#{len(chunks)}",
                "source_id": source["id"],
                "insurer": source["insurer"],
                "region": source["region"],
                "section": section["section"],
                "heading": heading,
                "kind": kind,
                "code_group": group if is_table else "",
                "text": piece,
                "codes": _codes(piece, is_table),
            })
        if not in_code_section:
            group = ""
    return chunks


# ---------------------------------------------------------------------
# Fetch + cache
# ---------------------------------------------------------------------

def _paths(source_id: str) -> Dict[str, str]:
    base = os.path.join(cache_dir(), re.sub(r"[^a-z0-9._-]", "_", source_id.lower()))
    return {"raw": base + ".raw", "parsed": base + ".json"}


def _review_date(text: str) -> Optional[str]:
    match = _REVIEW.search(text[:6000]) or _REVIEW.search(text)
    return f"{match.group(1)}: {match.group(2)}" if match else None


async def fetch_source(source: Dict[str, Any], client: httpx.AsyncClient) -> Dict[str, Any]:
    """Downloads one document, caches raw + parsed form. A failure is recorded and returned, never hidden."""
    paths = _paths(source["id"])
    record: Dict[str, Any] = {**{k: source[k] for k in ("id", "region", "insurer", "title", "url", "kind")},
                              "fetched_at": datetime.now(timezone.utc).isoformat(), "ok": False}
    try:
        response = await client.get(source["url"], headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=FETCH_TIMEOUT)
        record["http_status"] = response.status_code
        if response.status_code != 200:
            raise DocumentError(f"HTTP {response.status_code}")
        raw = response.content
        is_pdf = raw[:5] == b"%PDF-" or source["kind"] == "pdf"
        if is_pdf:
            text = (await document_to_text(raw, f"{source['id']}.pdf", "application/pdf"))["text"]
        else:
            text = html_to_text(raw.decode(response.encoding or "utf-8", errors="replace"))
        if len(text) < 400:
            raise DocumentError("document has almost no readable text")
        with open(paths["raw"], "wb") as f:
            f.write(raw)
        record.update(ok=True, sha256=hashlib.sha256(raw).hexdigest(), chars=len(text), review=_review_date(text),
                      text=text, chunks=chunk_document(source, text))
    except (httpx.HTTPError, DocumentError, UnicodeError) as exc:
        record["error"] = str(exc) or exc.__class__.__name__
        previous = load_cached(source["id"])
        if previous and previous.get("ok"):  # keep serving the last good copy, but say the refresh failed
            previous["refresh_error"] = f"{record['error']} at {record['fetched_at']}"
            record = previous
    with open(paths["parsed"], "w", encoding="utf-8") as f:
        json.dump(record, f)
    return record


def load_cached(source_id: str) -> Optional[Dict[str, Any]]:
    path = _paths(source_id)["parsed"]
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


async def refresh(region: Optional[str] = None, client: Optional[httpx.AsyncClient] = None) -> List[Dict[str, Any]]:
    import asyncio

    sources = [s for s in load_registry()["sources"] if not region or s["region"] == region]
    owns = client is None
    client = client or httpx.AsyncClient()
    try:
        return list(await asyncio.gather(*(fetch_source(s, client) for s in sources)))
    finally:
        if owns:
            await client.aclose()


def status(region: Optional[str] = None) -> List[Dict[str, Any]]:
    """One row per registered source: is it cached, how old is it, did the last fetch fail."""
    rows = []
    for source in load_registry()["sources"]:
        if region and source["region"] != region:
            continue
        cached = load_cached(source["id"]) or {}
        age_days = None
        if cached.get("fetched_at") and cached.get("ok"):
            age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(cached["fetched_at"])).days
        rows.append({**{k: source[k] for k in ("id", "region", "insurer", "title", "url")},
                     "cached": bool(cached.get("ok")), "fetched_at": cached.get("fetched_at") if cached.get("ok") else None,
                     "age_days": age_days, "review": cached.get("review"), "chunks": len(cached.get("chunks") or []),
                     "error": cached.get("error") or cached.get("refresh_error")})
    return rows


def all_chunks(region: str = "US", insurers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for source in load_registry()["sources"]:
        if source["region"] != region or (insurers and source["insurer"] not in insurers):
            continue
        cached = load_cached(source["id"])
        if cached and cached.get("ok"):
            for chunk in cached["chunks"]:
                if chunk.get("kind") == "background":
                    continue
                chunks.append({**chunk, "title": source["title"], "url": source["url"], "review": cached.get("review"),
                               "fetched_at": cached.get("fetched_at")})
    return chunks
