from __future__ import annotations

from importlib.util import find_spec

from agent.rag.indexer import index_uploaded_bytes
from agent.schemas import IngestionResult


ARCHITECTURE = "rag-anything-compatible"
CPU_FALLBACK_BACKEND = "local_cpu_fallback"


def raganything_available() -> bool:
    return find_spec("raganything") is not None


def ingest_uploaded_bytes(
    knowledge_id: str,
    files: list[tuple[str, bytes]],
    *,
    replace_same_name: bool = False,
) -> IngestionResult:
    """Index uploads through a RAG-Anything compatible facade.

    The CPU MVP intentionally keeps the heavy multimodal parser optional. When
    `raganything` is not installed, this function reuses the existing local
    loaders, sentence-aware chunker, and hybrid BM25/embedding indexer. The API
    contract already exposes multimodal fields so a later GPU worker can swap in
    RAG-Anything without changing frontend or chat code.
    """
    has_raganything = raganything_available()
    result = index_uploaded_bytes(
        knowledge_id,
        files,
        replace_same_name=replace_same_name,
    )
    backend = "raganything_optional_cpu" if has_raganything else CPU_FALLBACK_BACKEND
    return IngestionResult(
        knowledge_id=result.knowledge_id,
        backend=backend,
        architecture=ARCHITECTURE,
        files_indexed=result.files_indexed,
        files_skipped=result.files_skipped,
        chunks_added=result.chunks_added,
        chunks_total=result.chunks_total,
        embedding_backend=result.embedding_backend,
        content_types=("text",),
        raganything_available=has_raganything,
        errors=tuple(result.errors),
        metadata={
            "parser": "local_loaders",
            "chunker": "paragraph_sentence_cpu",
            "indexer": "local_hybrid",
            "gpu_required": False,
        },
    )
