from __future__ import annotations

import logging
from typing import Iterable

from agent.rag.bm25 import BM25State, build_bm25, search_bm25
from agent.rag.config import RAG_DISABLED
from agent.rag.embedder import current_backend, embed_query, is_hash_fallback
from agent.rag.store import KBStore, kb_store

logger = logging.getLogger(__name__)


# Per-method candidate pools: take more than top_k so RRF has room to re-rank.
PER_KB_DENSE_K = 8
PER_KB_BM25_K = 8
GLOBAL_TOP_K = 8
RRF_K = 60
# Floor below which the fused RRF score is considered junk. RRF max for two
# methods at rank 1 = 2/61 ≈ 0.0328. A single hit at rank 8 ≈ 1/68 ≈ 0.0147.
# We require either two methods agreeing or one method with a non-trivial rank.
RRF_FLOOR = 0.012
# Two chunks from the same source whose char ranges overlap by >= this ratio
# are merged into one (keep the one with the higher fused score).
DEDUP_OVERLAP_RATIO = 0.5


def _normalize_kb_ids(knowledge_ids: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for raw in knowledge_ids or []:
        if not raw:
            continue
        kb_id = str(raw).strip()
        if not kb_id or kb_id in seen:
            continue
        seen.add(kb_id)
        cleaned.append(kb_id)
    return cleaned


def _ensure_bm25(store: KBStore, chunks: list[dict]) -> BM25State | None:
    """Load BM25 state from disk, lazily building it for legacy KBs that lack it."""
    payload = store.load_bm25()
    if payload is not None:
        try:
            return BM25State.from_dict(payload)
        except Exception as exc:
            logger.warning("BM25 state load failed for %s, will rebuild: %s", store.knowledge_id, exc)
    if not chunks:
        return None
    try:
        state = build_bm25(chunks)
        store.save_bm25(state.to_dict())
        return state
    except Exception as exc:
        logger.warning("BM25 lazy build failed for %s: %s", store.knowledge_id, exc)
        return None


def _dense_candidates(store: KBStore, query_vector: list[float], top_k: int) -> list[tuple[int, float]]:
    if not query_vector:
        return []
    try:
        return store.search(query_vector, top_k=top_k)
    except Exception as exc:
        logger.warning("dense search failed for %s: %s", store.knowledge_id, exc)
        return []


def _bm25_candidates(state: BM25State | None, query: str, top_k: int) -> list[tuple[int, float]]:
    if state is None:
        return []
    try:
        return search_bm25(state, query, top_k=top_k)
    except Exception as exc:
        logger.warning("bm25 search failed: %s", exc)
        return []


def _fuse_per_kb(
    kb_id: str,
    chunks: list[dict],
    dense: list[tuple[int, float]],
    bm25: list[tuple[int, float]],
) -> list[dict]:
    """RRF-fuse dense and BM25 rankings for a single KB."""
    fused: dict[int, dict] = {}

    for rank, (idx, score) in enumerate(dense):
        if idx < 0 or idx >= len(chunks):
            continue
        bucket = fused.setdefault(idx, {"rrf": 0.0, "dense_score": None, "bm25_score": None})
        bucket["rrf"] += 1.0 / (RRF_K + rank + 1)
        bucket["dense_score"] = float(score)

    for rank, (idx, score) in enumerate(bm25):
        if idx < 0 or idx >= len(chunks):
            continue
        bucket = fused.setdefault(idx, {"rrf": 0.0, "dense_score": None, "bm25_score": None})
        bucket["rrf"] += 1.0 / (RRF_K + rank + 1)
        bucket["bm25_score"] = float(score)

    records: list[dict] = []
    for idx, bucket in fused.items():
        chunk = dict(chunks[idx])
        chunk["kb_id"] = kb_id
        chunk["dense_score"] = bucket["dense_score"]
        chunk["bm25_score"] = bucket["bm25_score"]
        chunk["rrf_score"] = bucket["rrf"]
        # Public "score" stays the RRF fused score for downstream sorting/display.
        chunk["score"] = bucket["rrf"]
        records.append(chunk)
    return records


def _dedupe(records: list[dict]) -> list[dict]:
    """Collapse overlapping chunks from the same source file."""
    if not records:
        return records
    records.sort(key=lambda item: float(item.get("rrf_score") or 0.0), reverse=True)
    kept: list[dict] = []
    for record in records:
        source = record.get("source_file") or ""
        kb_id = record.get("kb_id") or ""
        start = int(record.get("char_start") or 0)
        end = int(record.get("char_end") or 0)
        span = max(1, end - start)
        merged = False
        for existing in kept:
            if existing.get("kb_id") != kb_id or existing.get("source_file") != source:
                continue
            e_start = int(existing.get("char_start") or 0)
            e_end = int(existing.get("char_end") or 0)
            e_span = max(1, e_end - e_start)
            overlap = max(0, min(end, e_end) - max(start, e_start))
            ratio = overlap / min(span, e_span)
            if ratio >= DEDUP_OVERLAP_RATIO:
                # Keep the higher-ranked one (already first in kept) and accumulate signals.
                if record.get("dense_score") is not None and existing.get("dense_score") is None:
                    existing["dense_score"] = record["dense_score"]
                if record.get("bm25_score") is not None and existing.get("bm25_score") is None:
                    existing["bm25_score"] = record["bm25_score"]
                merged = True
                break
        if not merged:
            kept.append(record)
    return kept


def retrieve(query: str, knowledge_ids: list[str], top_k: int = GLOBAL_TOP_K) -> list[dict]:
    if RAG_DISABLED:
        return []
    if not query or not query.strip():
        return []
    ids = _normalize_kb_ids(knowledge_ids)
    if not ids:
        return []

    # Always run BOTH channels and let RRF fuse them. Hash-backend dense
    # scores are noisy, but they still encode character bigrams; combined
    # with BM25 via rank-based fusion they raise recall without dominating
    # the ranking. The previous policy of skipping dense whenever the model
    # was on hash fallback caused zero-recall on semantic queries.
    hash_mode = is_hash_fallback()
    query_vector, _backend = embed_query(query)

    all_records: list[dict] = []
    for kb_id in ids:
        store = kb_store(kb_id)
        chunks = store.load_chunks()
        if not chunks:
            continue
        dense = _dense_candidates(store, query_vector, PER_KB_DENSE_K) if query_vector else []
        bm25_state = _ensure_bm25(store, chunks)
        bm25 = _bm25_candidates(bm25_state, query, PER_KB_BM25_K)
        if not dense and not bm25:
            continue
        all_records.extend(_fuse_per_kb(kb_id, chunks, dense, bm25))

    if not all_records:
        logger.info(
            "RAG retrieval returned no hits (backend=%s, kbs=%s, query_len=%d).",
            current_backend(), ids, len(query),
        )
        return []

    deduped = _dedupe(all_records)
    # The floor is calibrated for the 2-method RRF setup. When hash mode is
    # active, dense ranks are noisy but still rank-based contributing, so the
    # same floor still applies meaningfully. We relax it slightly to avoid
    # filtering BM25-only hits where dense returned junk.
    floor = RRF_FLOOR if not hash_mode else 0.0
    deduped = [r for r in deduped if float(r.get("rrf_score") or 0.0) >= floor]
    deduped.sort(key=lambda item: float(item.get("rrf_score") or 0.0), reverse=True)
    return deduped[:top_k]


def retrieve_safe(query: str, knowledge_ids: list[str], top_k: int = GLOBAL_TOP_K) -> list[dict]:
    try:
        return retrieve(query, knowledge_ids, top_k=top_k)
    except Exception as exc:
        logger.warning("RAG 检索失败，降级到无上下文: %s", exc)
        return []
