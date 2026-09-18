"""
Retrieval over the cached policy chunks. Three signals, fused by reciprocal rank:

  1. exact codes  - the case's CDT / ICD-10 / CPT codes against the codes each chunk actually lists
                    (payer policies publish their own code tables, so this is the most precise signal)
  2. semantic     - API embeddings in a local ChromaDB collection
  3. lexical      - BM25 over the chunk text; also the whole retriever when no embedding key is set

The retriever only ever returns text that exists in a cached document. It decides nothing.
"""

import hashlib
import math
import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional

import httpx

from . import embeddings, policy_store

COLLECTION = "payer-policies"
_STOP = set("the a an of and or to in for is are be with by on as at that this it from not which may when if any all can "
            "will their its such these those has have had was were been than then into also more other".split())


def _tokens(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9-]{2,}", text.lower()) if w not in _STOP]


def _collection():
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(path=os.path.join(policy_store.cache_dir(), "chroma"),
                                       settings=Settings(anonymized_telemetry=False))
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def _fingerprint(chunk: Dict[str, Any]) -> str:
    return hashlib.sha1(f"{embeddings.model_name()}|{chunk['text']}".encode()).hexdigest()


INDEX_BATCH = 80  # stays under a 100-items-per-minute free tier with room for the query embeddings
_progress: Dict[str, Any] = {"state": "idle", "indexed": 0, "total": 0, "mode": "lexical", "note": ""}


def index_status(region: str = "US") -> Dict[str, Any]:
    """Progress of a build running in this process, otherwise what is actually in the index on disk."""
    if _progress["state"] in ("indexing", "paused"):
        return dict(_progress, embedding_model=embeddings.model_name() or None)
    total = len(policy_store.all_chunks(region))
    if not embeddings.provider():
        return {"state": "done", "indexed": 0, "total": total, "mode": "lexical", "embedding_model": None,
                "note": "No embedding key set: keyword and code search only."}
    try:
        indexed = min(_collection().count(), total)
    except Exception:
        indexed = 0
    state = "done" if total and indexed >= total else "incomplete"
    return {"state": state, "indexed": indexed, "total": total, "mode": "semantic" if indexed else "lexical",
            "embedding_model": embeddings.model_name(), "note": "" if state == "done" else "Press Refresh sources to finish indexing."}


async def build_index(region: str = "US", client: Optional[httpx.AsyncClient] = None, max_wait: float = 3600.0) -> Dict[str, Any]:
    """
    Embeds chunks that are new or changed since the last build, in metered batches, saving after each one: a rate
    limit or a restart costs nothing, the next call carries on. Search works the whole time (codes + lexical, plus
    whatever is already embedded).
    """
    import asyncio

    if not embeddings.provider():
        _progress.update(state="done", mode="lexical", note="No embedding key set: lexical and code search only.")
        return index_status()
    chunks = policy_store.all_chunks(region)
    collection = _collection()
    existing = collection.get(include=["metadatas"])
    known = {i: (m or {}).get("fingerprint") for i, m in zip(existing["ids"], existing["metadatas"])}
    stale = [i for i in known if i not in {c["id"] for c in chunks}]
    if stale:
        collection.delete(ids=stale)
    # Criteria and exclusions first, code tables last: the first minute of indexing is the most useful one
    todo = sorted((c for c in chunks if known.get(c["id"]) != _fingerprint(c)), key=lambda c: c.get("kind") == "codes")
    _progress.update(state="indexing" if todo else "done", total=len(chunks), indexed=len(chunks) - len(todo), mode="semantic", note="")
    waited = 0.0
    while todo:
        batch = todo[:INDEX_BATCH]
        try:
            vectors = await embeddings.embed([f"{c['heading']}\n{c['text']}" for c in batch], client=client)
        except embeddings.RateLimited as limit:
            if waited + limit.retry_after > max_wait:
                _progress.update(state="paused", note="Embedding quota reached; indexing resumes on the next refresh.")
                return index_status()
            _progress["note"] = f"Embedding quota reached, continuing in {limit.retry_after:.0f}s."
            waited += limit.retry_after
            await asyncio.sleep(limit.retry_after)
            continue
        except Exception as exc:
            _progress.update(state="paused", note=f"Embedding failed ({exc}); lexical search still works.")
            return index_status()
        collection.upsert(
            ids=[c["id"] for c in batch], embeddings=vectors, documents=[c["text"] for c in batch],
            metadatas=[{"insurer": c["insurer"], "region": c["region"], "source_id": c["source_id"],
                        "fingerprint": _fingerprint(c)} for c in batch],
        )
        todo = todo[INDEX_BATCH:]
        _progress.update(indexed=_progress["total"] - len(todo), note="")
    _progress.update(state="done")
    return index_status()


def _bm25(query: str, chunks: List[Dict[str, Any]], k: int) -> List[str]:
    query_terms = _tokens(query)
    if not query_terms or not chunks:
        return []
    docs = [_tokens(f"{c['heading']} {c['text']}") for c in chunks]
    avg = sum(len(d) for d in docs) / len(docs)
    df = Counter(term for d in docs for term in set(d))
    scores = []
    for chunk, doc in zip(chunks, docs):
        tf = Counter(doc)
        score = sum(
            math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(doc) / avg))
            for t in query_terms if tf[t]
        )
        if score > 0:
            scores.append((score, chunk["id"]))
    return [i for _, i in sorted(scores, reverse=True)[:k]]


async def search(
    query: str,
    region: str = "US",
    insurers: Optional[List[str]] = None,
    codes: Optional[List[str]] = None,
    k: int = 10,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    chunks = policy_store.all_chunks(region, insurers)
    by_id = {c["id"]: c for c in chunks}
    rankings: Dict[str, List[str]] = {}

    wanted = {c.upper() for c in codes or []}
    if wanted:
        def listed(chunk):
            return wanted & {x.upper() for group in chunk["codes"].values() for x in group}
        rankings["code"] = [c["id"] for c in sorted(chunks, key=lambda c: -len(listed(c))) if listed(c)][: k * 2]

    mode = "lexical"
    if embeddings.provider():
        try:
            vector = (await embeddings.embed([query], is_query=True, client=client))[0]
            where = {"region": region} if not insurers else {"$and": [{"region": region}, {"insurer": {"$in": insurers}}]}
            found = _collection().query(query_embeddings=[vector], n_results=k * 2, where=where)
            rankings["semantic"] = [i for i in found["ids"][0] if i in by_id]
            mode = "semantic" if rankings["semantic"] else "lexical"
        except Exception:  # index missing or API down: lexical still answers
            mode = "lexical"
    rankings["lexical"] = _bm25(query, chunks, k * 2)

    fused: Dict[str, float] = {}
    why: Dict[str, List[str]] = {}
    for signal, ids in rankings.items():
        weight = 1.6 if signal == "code" else 1.0
        for rank, chunk_id in enumerate(ids):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + weight / (30 + rank)
            why.setdefault(chunk_id, []).append(signal)
    ordered = sorted(fused, key=fused.get, reverse=True)[:k]
    return {"mode": mode, "passages": [{**by_id[i], "matched_by": why[i]} for i in ordered]}
