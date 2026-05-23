from __future__ import annotations

import hashlib
import logging
import math
import threading
from typing import Sequence

from agent.rag.config import (
    DEFAULT_EMBEDDING_DIM,
    DEFAULT_EMBEDDING_MODEL,
    embedding_disabled,
    preload_requested,
)

logger = logging.getLogger(__name__)


_HASH_BACKEND = "hash-fallback"
_LOCK = threading.Lock()
_MODEL: object | None = None
_BACKEND: str = ""
_TRIED_LOAD = False


def _hash_embedding(text: str, dim: int = DEFAULT_EMBEDDING_DIM) -> list[float]:
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


def _l2_normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(v) * float(v) for v in vector))
    if norm <= 0:
        return [0.0 for _ in vector]
    return [float(v) / norm for v in vector]


def _try_load_model() -> tuple[object | None, str]:
    if embedding_disabled():
        logger.info("RAG embedding disabled by AFH_DISABLE_RAG_EMBEDDING=1")
        return None, _HASH_BACKEND
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        logger.warning("sentence-transformers 未安装，回退到 hash embedding: %s", exc)
        return None, _HASH_BACKEND
    try:
        model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
    except Exception as exc:
        logger.warning("加载嵌入模型失败，回退到 hash embedding: %s", exc)
        return None, _HASH_BACKEND
    return model, f"sentence-transformers:{DEFAULT_EMBEDDING_MODEL}"


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
    if embedding_disabled():
        return _HASH_BACKEND
    return "lazy"


def embed_texts(texts: Sequence[str]) -> tuple[list[list[float]], str]:
    if not texts:
        return [], current_backend() or _HASH_BACKEND
    model, backend = get_embedder()
    if model is None:
        vectors = [_hash_embedding(t) for t in texts]
        return vectors, backend
    try:
        raw = model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
    except Exception as exc:
        logger.warning("模型推理失败，回退到 hash embedding: %s", exc)
        vectors = [_hash_embedding(t) for t in texts]
        return vectors, _HASH_BACKEND
    vectors = []
    for vec in raw:
        as_list = [float(x) for x in vec]
        vectors.append(_l2_normalize(as_list))
    return vectors, backend


def embed_query(text: str) -> tuple[list[float], str]:
    vectors, backend = embed_texts([text])
    return vectors[0], backend


def preload_if_requested() -> None:
    if preload_requested():
        threading.Thread(target=get_embedder, name="rag-embedder-preload", daemon=True).start()
