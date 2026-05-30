from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
from urllib import request as url_request
from urllib.error import URLError
from typing import Sequence

from agent.rag.config import (
    BGE_QUERY_PREFIX,
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL,
    embedding_disabled,
    gpu_circuit_breaker_seconds,
    gpu_mode,
    gpu_required,
    hash_fallback_allowed,
    local_embedding_download_allowed,
    preload_requested,
    remote_embedding_timeout,
    remote_embedding_url,
)

logger = logging.getLogger(__name__)


HASH_BACKEND = "hash-fallback"
REMOTE_BACKEND_PREFIX = "remote-embedding:"
_LOCK = threading.Lock()
_MODEL: object | None = None
_BACKEND: str = ""
_TRIED_LOAD = False
_CONFIG_KEY: tuple[str, str, bool, bool, bool] | None = None
_UNAVAILABLE_MESSAGE: str | None = None
_REMOTE_BLOCKED_UNTIL = 0.0
_REMOTE_LAST_ERROR = ""


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


def _local_embedding_cache_available() -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except Exception:
        return False
    required_files = ("config.json", "tokenizer_config.json")
    return all(isinstance(try_to_load_from_cache(DEFAULT_EMBEDDING_MODEL, filename), str) for filename in required_files)


def _embedder_config_key() -> tuple[str, str, bool, bool, bool]:
    return (
        gpu_mode(),
        remote_embedding_url(),
        embedding_disabled(),
        hash_fallback_allowed(),
        local_embedding_download_allowed(),
    )


def _try_load_model() -> tuple[object | None, str]:
    mode = gpu_mode()
    remote_url = remote_embedding_url()
    if remote_url:
        logger.info("Using remote semantic embedding service: %s", remote_url)
        return None, f"{REMOTE_BACKEND_PREFIX}{remote_url}"
    if mode == "off":
        raise SemanticEmbeddingUnavailable("GPU mode is off; semantic embedding is disabled and local BM25 retrieval will be used.")
    if mode == "required":
        raise SemanticEmbeddingUnavailable("GPU mode is required, but AFH_RAG_EMBEDDING_URL is not configured.")
    if embedding_disabled():
        logger.info("RAG embedding disabled by AFH_DISABLE_RAG_EMBEDDING=1")
        if hash_fallback_allowed():
            return None, HASH_BACKEND
        raise SemanticEmbeddingUnavailable(
            "Semantic RAG embedding is disabled. Unset AFH_DISABLE_RAG_EMBEDDING "
            "or set AFH_ALLOW_HASH_RAG_FALLBACK=1 for local fallback-only debugging."
        )
    allow_download = local_embedding_download_allowed()
    if not allow_download and not _local_embedding_cache_available():
        if hash_fallback_allowed():
            logger.warning(
                "Semantic embedding model %s is not cached locally. Falling back to hash vectors "
                "because AFH_ALLOW_HASH_RAG_FALLBACK=1.",
                DEFAULT_EMBEDDING_MODEL,
            )
            return None, HASH_BACKEND
        raise SemanticEmbeddingUnavailable(
            f"Semantic embedding model {DEFAULT_EMBEDDING_MODEL} is not cached locally, "
            "and request-time model download is disabled. Start the GPU embedding worker "
            "and set AFH_RAG_EMBEDDING_URL, pre-cache the model, or set "
            "AFH_RAG_ALLOW_MODEL_DOWNLOAD=1 for an explicit one-time download."
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
        model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL, local_files_only=not allow_download)
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
    global _MODEL, _BACKEND, _TRIED_LOAD, _CONFIG_KEY, _UNAVAILABLE_MESSAGE
    config_key = _embedder_config_key()
    if _TRIED_LOAD and _CONFIG_KEY == config_key:
        if _UNAVAILABLE_MESSAGE:
            raise SemanticEmbeddingUnavailable(_UNAVAILABLE_MESSAGE)
        return _MODEL, _BACKEND
    with _LOCK:
        if _TRIED_LOAD and _CONFIG_KEY == config_key:
            if _UNAVAILABLE_MESSAGE:
                raise SemanticEmbeddingUnavailable(_UNAVAILABLE_MESSAGE)
            return _MODEL, _BACKEND
        try:
            _MODEL, _BACKEND = _try_load_model()
        except SemanticEmbeddingUnavailable as exc:
            _MODEL = None
            _BACKEND = "unavailable"
            _CONFIG_KEY = config_key
            _UNAVAILABLE_MESSAGE = str(exc)
            _TRIED_LOAD = True
            raise
        _CONFIG_KEY = config_key
        _UNAVAILABLE_MESSAGE = None
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


def _is_remote_backend(backend: str) -> bool:
    return backend.startswith(REMOTE_BACKEND_PREFIX)


def _remote_circuit_open() -> bool:
    return time.monotonic() < _REMOTE_BLOCKED_UNTIL


def _record_remote_failure(message: str) -> None:
    global _REMOTE_BLOCKED_UNTIL, _REMOTE_LAST_ERROR
    _REMOTE_LAST_ERROR = message
    if not gpu_required():
        _REMOTE_BLOCKED_UNTIL = time.monotonic() + gpu_circuit_breaker_seconds()


def reset_runtime_state() -> None:
    global _MODEL, _BACKEND, _TRIED_LOAD, _CONFIG_KEY, _UNAVAILABLE_MESSAGE, _REMOTE_BLOCKED_UNTIL, _REMOTE_LAST_ERROR
    with _LOCK:
        _MODEL = None
        _BACKEND = ""
        _TRIED_LOAD = False
        _CONFIG_KEY = None
        _UNAVAILABLE_MESSAGE = None
        _REMOTE_BLOCKED_UNTIL = 0.0
        _REMOTE_LAST_ERROR = ""


def embedding_runtime_status() -> dict[str, object]:
    mode = gpu_mode()
    remote_url = remote_embedding_url()
    circuit_remaining = max(0.0, _REMOTE_BLOCKED_UNTIL - time.monotonic())
    return {
        "gpu_mode": mode,
        "remote_embedding_configured": bool(remote_url),
        "remote_embedding_url": remote_url,
        "remote_circuit_open": circuit_remaining > 0,
        "remote_circuit_remaining_seconds": round(circuit_remaining, 1),
        "remote_last_error": _REMOTE_LAST_ERROR,
        "embedding_backend": current_backend(),
        "hash_fallback_allowed": hash_fallback_allowed(),
        "local_model_download_allowed": local_embedding_download_allowed(),
    }


def _is_bge_model(backend: str) -> bool:
    return "bge" in backend.lower() and "zh" in backend.lower()


def _embed_remote(texts: Sequence[str], *, is_query: bool) -> tuple[list[list[float]], str]:
    endpoint = remote_embedding_url()
    if not endpoint:
        raise SemanticEmbeddingUnavailable("Remote embedding endpoint is not configured.")
    if _remote_circuit_open():
        raise SemanticEmbeddingUnavailable(
            f"GPU embedding worker is temporarily unavailable; using local BM25 fallback. Last error: {_REMOTE_LAST_ERROR}"
        )
    if not texts:
        return [], f"{REMOTE_BACKEND_PREFIX}{endpoint}"
    payload = json.dumps({"texts": list(texts), "is_query": is_query}, ensure_ascii=False).encode("utf-8")
    req = url_request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with url_request.urlopen(req, timeout=remote_embedding_timeout()) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError) as exc:
        message = f"Remote semantic embedding request failed: {exc}"
        _record_remote_failure(message)
        raise SemanticEmbeddingUnavailable(message) from exc
    vectors = data.get("vectors")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        message = "Remote semantic embedding response has invalid vector count."
        _record_remote_failure(message)
        raise SemanticEmbeddingUnavailable(message)
    normalized: list[list[float]] = []
    for vector in vectors:
        if not isinstance(vector, list) or not vector:
            message = "Remote semantic embedding response has an invalid vector."
            _record_remote_failure(message)
            raise SemanticEmbeddingUnavailable(message)
        normalized.append([float(value) for value in vector])
    backend = str(data.get("backend") or f"{REMOTE_BACKEND_PREFIX}{endpoint}")
    return normalized, backend


def embed_texts(texts: Sequence[str]) -> tuple[list[list[float]], str]:
    """Embed passages (chunks). Returns (vectors, backend_label)."""
    if not texts:
        return [], current_backend() or HASH_BACKEND
    model, backend = get_embedder()
    if _is_remote_backend(backend):
        return _embed_remote(texts, is_query=False)
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
    if _is_remote_backend(backend):
        vectors, remote_backend = _embed_remote([text], is_query=True)
        return vectors[0], remote_backend
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
