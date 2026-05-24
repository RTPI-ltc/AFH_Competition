from __future__ import annotations

import hashlib
import logging
import math
import threading
from typing import Sequence

from agent.rag.config import (
    BGE_QUERY_PREFIX,
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL,
    embedding_disabled,
    hash_fallback_allowed,
    preload_requested,
)

logger = logging.getLogger(__name__)


HASH_BACKEND = "hash-fallback"
_LOCK = threading.Lock()
_MODEL: object | None = None
_BACKEND: str = ""
_TRIED_LOAD = False


class SemanticEmbeddingUnavailable(RuntimeError):
    """Raised when semantic RAG embeddings are required but unavailable."""


def _hash_embedding(text: str, dim: int = DEFAULT_EMBEDDING_DIM) -> list[float]:
    """Cheap deterministic vector used only for explicit local fallback."""
    vector = [0.0] * dim
    tokens = text.split() if " " in text else [text[i:i + 2] for i in range(0, len(text), 2)]
    if not tokens:
        tokens = [text or ""]
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=16).digest()
        for i in range(dim):
            byte = digest[i % len(digest)]
            vector[i] += (byte / 255.0) - 0.5
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def _try_load_model() -> tuple[object | None, str]:
    if embedding_disabled():
        logger.info("RAG embedding disabled by AFH_DISABLE_RAG_EMBEDDING=1")
        if hash_fallback_allowed():
            return None, HASH_BACKEND
        raise SemanticEmbeddingUnavailable(
            "Semantic RAG embedding is disabled. Unset AFH_DISABLE_RAG_EMBEDDING "
            "or set AFH_ALLOW_HASH_RAG_FALLBACK=1 for local fallback-only debugging."
        )
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        message = (
            "sentence-transformers is required for semantic RAG retrieval. "
            "Install deployment dependencies with `pip install -r requirements.txt`."
        )
        if hash_fallback_allowed():
            logger.warning("%s Falling back to hash vectors because AFH_ALLOW_HASH_RAG_FALLBACK=1. Error: %s", message, exc)
            return None, HASH_BACKEND
        raise SemanticEmbeddingUnavailable(message) from exc
    try:
        model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
    except Exception as exc:
        message = (
            f"Semantic embedding model {DEFAULT_EMBEDDING_MODEL} failed to load. "
            "Check network/model cache during deployment."
        )
        if hash_fallback_allowed():
            logger.warning("%s Falling back to hash vectors because AFH_ALLOW_HASH_RAG_FALLBACK=1. Error: %s", message, exc)
            return None, HASH_BACKEND
        raise SemanticEmbeddingUnavailable(message) from exc
    backend = f"sentence-transformers:{DEFAULT_EMBEDDING_MODEL}"
    logger.info("Embedding model loaded: %s", backend)
    return model, backend


def get_embedder() -> tuple[object | None, str]:
    global _MODEL, _BACKEND, _TRIED_LOAD
    if _TRIED_LOAD:
        return _MODEL, _BACKEND
    with _LOCK:
        if _TRIED_LOAD:
            return _MODEL, _BACKEND
        _MODEL, _BACKEND = _try_load_model()
        _TRIED_LOAD = True
    return _MODEL, _BACKEND


def current_backend() -> str:
    if _TRIED_LOAD:
        return _BACKEND
    if embedding_disabled() and hash_fallback_allowed():
        return HASH_BACKEND
    return "lazy"


def is_hash_fallback() -> bool:
    backend = current_backend()
    if backend == "lazy":
        get_embedder()
        backend = current_backend()
    return backend == HASH_BACKEND


def _is_bge_model(backend: str) -> bool:
    return "bge" in backend.lower() and "zh" in backend.lower()


def embed_texts(texts: Sequence[str]) -> tuple[list[list[float]], str]:
    """Embed passages (chunks). Returns (vectors, backend_label)."""
    if not texts:
        return [], current_backend() or HASH_BACKEND
    model, backend = get_embedder()
    if model is None:
        if hash_fallback_allowed():
            return [_hash_embedding(t) for t in texts], backend
        raise SemanticEmbeddingUnavailable("Semantic passage embedding is required; hash fallback is disabled.")
    try:
        raw = model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
    except Exception as exc:
        if hash_fallback_allowed():
            logger.warning("Embedding inference failed; falling back to hash vectors: %s", exc)
            return [_hash_embedding(t) for t in texts], HASH_BACKEND
        raise SemanticEmbeddingUnavailable("Semantic embedding inference failed.") from exc
    return [[float(x) for x in vec] for vec in raw], backend


def embed_query(text: str) -> tuple[list[float], str]:
    """Embed a single query with BGE's query instruction when applicable."""
    model, backend = get_embedder()
    if model is None:
        if hash_fallback_allowed():
            return _hash_embedding(text), backend
        raise SemanticEmbeddingUnavailable("Semantic query embedding is required; hash fallback is disabled.")
    prompt = text
    if _is_bge_model(backend) and text and not text.startswith(BGE_QUERY_PREFIX):
        prompt = BGE_QUERY_PREFIX + text
    try:
        raw = model.encode([prompt], normalize_embeddings=True, show_progress_bar=False)
    except Exception as exc:
        if hash_fallback_allowed():
            logger.warning("Query embedding inference failed; falling back to hash vectors: %s", exc)
            return _hash_embedding(text), HASH_BACKEND
        raise SemanticEmbeddingUnavailable("Semantic query embedding inference failed.") from exc
    return [float(x) for x in raw[0]], backend


def preload_if_requested() -> None:
    if preload_requested():
        threading.Thread(target=get_embedder, name="rag-embedder-preload", daemon=True).start()
