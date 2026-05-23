from __future__ import annotations

import logging
from typing import Iterable

from agent.rag.config import RAG_DISABLED
from agent.rag.embedder import embed_query
from agent.rag.store import kb_store

logger = logging.getLogger(__name__)


SCORE_FLOOR = 0.2
PER_KB_TOP_K = 4
GLOBAL_TOP_K = 8


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


def retrieve(query: str, knowledge_ids: list[str], top_k: int = GLOBAL_TOP_K) -> list[dict]:
    if RAG_DISABLED:
        return []
    if not query or not query.strip():
        return []
    ids = _normalize_kb_ids(knowledge_ids)
    if not ids:
        return []
    vector, _backend = embed_query(query)
    if not vector:
        return []

    aggregated: list[dict] = []
    for kb_id in ids:
        store = kb_store(kb_id)
        chunks = store.load_chunks()
        if not chunks:
            continue
        matches = store.search(vector, top_k=PER_KB_TOP_K)
        for index, score in matches:
            if index < 0 or index >= len(chunks):
                continue
            if score < SCORE_FLOOR:
                continue
            record = dict(chunks[index])
            record["score"] = float(score)
            record["kb_id"] = kb_id
            aggregated.append(record)

    aggregated.sort(key=lambda item: item.get("score") or 0.0, reverse=True)
    return aggregated[:top_k]


def retrieve_safe(query: str, knowledge_ids: list[str], top_k: int = GLOBAL_TOP_K) -> list[dict]:
    try:
        return retrieve(query, knowledge_ids, top_k=top_k)
    except Exception as exc:
        logger.warning("RAG 检索失败，降级到无上下文: %s", exc)
        return []
