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
    preload_requested,
)

logger = logging.getLogger(__name__)


HASH_BACKEND = "hash-fallback"
_LOCK = threading.Lock()
_MODEL: object | None = None
_BACKEND: str = ""
_TRIED_LOAD = False


def _hash_embedding(text: str, dim: int = DEFAULT_EMBEDDING_DIM) -> list[float]:
    """Cheap deterministic vector used only as an absolute fallback.
    These vectors do NOT carry meaningful semantic similarity — they help BM25
    coexist with the rest of the pipeline without crashing, but the retriever
    should treat hash-fallback dense scores as untrustworthy."""
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
        return None, HASH_BACKEND
    try:
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        logger.warning(
            "sentence-transformers 未安装，向量检索将退到 hash 兜底（无真语义）。"
            " 请 `pip install sentence-transformers`。原始错误: %s",
            exc,
        )
        return None, HASH_BACKEND
    try:
        model = SentenceTransformer(DEFAULT_EMBEDDING_MODEL)
    except Exception as exc:
        logger.warning(
            "嵌入模型 %s 加载失败，回退 hash 兜底。检查网络/磁盘/缓存。原始错误: %s",
            DEFAULT_EMBEDDING_MODEL,
            exc,
        )
        return None, HASH_BACKEND
    backend = f"sentence-transformers:{DEFAULT_EMBEDDING_MODEL}"
    logger.info("嵌入模型已加载: %s", backend)
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
    if embedding_disabled():
        return HASH_BACKEND
    return "lazy"


def is_hash_fallback() -> bool:
    """Cheap check the retriever uses to decide whether dense scores are
    semantically meaningful or just a noisy bigram signal."""
    backend = current_backend()
    if backend == "lazy":
        # Not yet loaded; assume semantic until we try.
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
        return [_hash_embedding(t) for t in texts], backend
    try:
        raw = model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
    except Exception as exc:
        logger.warning("模型推理失败，回退 hash 兜底: %s", exc)
        return [_hash_embedding(t) for t in texts], HASH_BACKEND
    return [[float(x) for x in vec] for vec in raw], backend


def embed_query(text: str) -> tuple[list[float], str]:
    """Embed a single query. For BGE-zh models, prepend the retrieval
    instruction so query and passage live on the same manifold."""
    model, backend = get_embedder()
    if model is None:
        return _hash_embedding(text), backend
    prompt = text
    if _is_bge_model(backend) and text and not text.startswith(BGE_QUERY_PREFIX):
        prompt = BGE_QUERY_PREFIX + text
    try:
        raw = model.encode([prompt], normalize_embeddings=True, show_progress_bar=False)
    except Exception as exc:
        logger.warning("query 推理失败，回退 hash 兜底: %s", exc)
        return _hash_embedding(text), HASH_BACKEND
    return [float(x) for x in raw[0]], backend


def preload_if_requested() -> None:
    if preload_requested():
        threading.Thread(target=get_embedder, name="rag-embedder-preload", daemon=True).start()
