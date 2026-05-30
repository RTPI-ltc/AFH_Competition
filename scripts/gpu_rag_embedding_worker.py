from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import torch
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "BAAI/bge-small-zh-v1.5"
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


class EmbedRequest(BaseModel):
    texts: list[str] = Field(default_factory=list, max_length=64)
    is_query: bool = False


class EmbedResponse(BaseModel):
    vectors: list[list[float]]
    backend: str
    device: str
    dim: int


app = FastAPI(title="AFH GPU RAG Embedding Worker")


def _model_name() -> str:
    return os.getenv("AFH_GPU_EMBEDDING_MODEL", DEFAULT_MODEL)


def _device() -> str:
    configured = os.getenv("AFH_GPU_EMBEDDING_DEVICE", "").strip()
    if configured:
        return configured
    return "cuda" if torch.cuda.is_available() else "cpu"


def _is_bge_zh(model_name: str) -> bool:
    lowered = model_name.lower()
    return "bge" in lowered and "zh" in lowered


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    return SentenceTransformer(_model_name(), device=_device())


def _prepare_texts(texts: list[str], *, is_query: bool) -> list[str]:
    model_name = _model_name()
    if not is_query or not _is_bge_zh(model_name):
        return texts
    return [
        text if text.startswith(BGE_QUERY_PREFIX) else BGE_QUERY_PREFIX + text
        for text in texts
    ]


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": _model_name(),
        "device": _device(),
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_count": torch.cuda.device_count(),
        "cuda_devices": [
            torch.cuda.get_device_name(idx)
            for idx in range(torch.cuda.device_count())
        ],
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(body: EmbedRequest) -> EmbedResponse:
    texts = [str(text or "").strip() for text in body.texts]
    if not texts:
        return EmbedResponse(vectors=[], backend=f"gpu-worker:{_model_name()}", device=_device(), dim=0)
    model = _load_model()
    prepared = _prepare_texts(texts, is_query=body.is_query)
    raw = model.encode(prepared, normalize_embeddings=True, show_progress_bar=False)
    vectors = [[float(value) for value in vector] for vector in raw]
    dim = len(vectors[0]) if vectors else 0
    return EmbedResponse(
        vectors=vectors,
        backend=f"gpu-worker:{_model_name()}",
        device=_device(),
        dim=dim,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "gpu_rag_embedding_worker:app",
        host=os.getenv("AFH_GPU_WORKER_HOST", "127.0.0.1"),
        port=int(os.getenv("AFH_GPU_WORKER_PORT", "8010")),
        reload=False,
    )
