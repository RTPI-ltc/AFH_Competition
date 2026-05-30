from __future__ import annotations

from typing import Any

from agent.rag.retriever import retrieve_safe
from agent.schemas import DocumentChunk, RetrievalHit


def _score(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _chunk_from_record(record: dict[str, Any]) -> DocumentChunk:
    chunk_id = str(record.get("chunk_id") or record.get("id") or "")
    return DocumentChunk(
        id=chunk_id,
        knowledge_id=str(record.get("kb_id") or record.get("knowledge_id") or ""),
        text=str(record.get("text") or ""),
        source_file=str(record.get("source_file") or ""),
        content_type=str(record.get("content_type") or "text"),  # type: ignore[arg-type]
        page=record.get("page") if isinstance(record.get("page"), int) else None,
        section=str(record.get("section") or "") or None,
        char_start=record.get("char_start") if isinstance(record.get("char_start"), int) else None,
        char_end=record.get("char_end") if isinstance(record.get("char_end"), int) else None,
        asset_path=str(record.get("asset_path") or "") or None,
        related_chunk_ids=tuple(str(item) for item in record.get("related_chunk_ids") or []),
        metadata=dict(record.get("metadata") or {}),
    )


def _hit_from_record(record: dict[str, Any]) -> RetrievalHit:
    dense_score = _score(record.get("dense_score"))
    sparse_score = _score(record.get("bm25_score"))
    fused_score = _score(record.get("rrf_score")) or _score(record.get("score")) or 0.0
    confidence = "high" if dense_score is not None and sparse_score is not None else "medium"
    return RetrievalHit(
        chunk=_chunk_from_record(record),
        dense_score=dense_score,
        sparse_score=sparse_score,
        fused_score=fused_score,
        hit_kind="hybrid",
        modality="text",
        confidence=confidence,  # type: ignore[arg-type]
        metadata={
            "backend": "local_cpu_fallback",
            "architecture": "rag-anything-compatible",
        },
    )


def retrieve_hits(query: str, knowledge_ids: list[str], top_k: int = 8) -> list[RetrievalHit]:
    if not query.strip() or not knowledge_ids:
        return []
    records = retrieve_safe(query, knowledge_ids, top_k=top_k)
    return [_hit_from_record(record) for record in records]


def retrieve_hit_dicts(query: str, knowledge_ids: list[str], top_k: int = 8) -> list[dict[str, Any]]:
    return [hit.to_dict() for hit in retrieve_hits(query, knowledge_ids, top_k=top_k)]
