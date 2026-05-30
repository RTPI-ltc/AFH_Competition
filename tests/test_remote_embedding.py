from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _reset_embedder_state(embedder) -> None:
    embedder.reset_runtime_state()


def test_remote_embedding_service_is_used_for_passages_and_queries(monkeypatch):
    from agent.rag import embedder

    _reset_embedder_state(embedder)
    monkeypatch.setenv("AFH_GPU_MODE", "auto")
    monkeypatch.setenv("AFH_RAG_EMBEDDING_URL", "http://gpu-worker.local/embed")
    captured: list[dict] = []

    def fake_urlopen(req, timeout):
        payload = json.loads(req.data.decode("utf-8"))
        captured.append({"payload": payload, "timeout": timeout})
        return _FakeResponse({
            "vectors": [[0.1, 0.2, 0.3] for _ in payload["texts"]],
            "backend": "gpu-worker:BAAI/bge-small-zh-v1.5",
            "device": "cuda",
            "dim": 3,
        })

    monkeypatch.setattr(embedder.url_request, "urlopen", fake_urlopen)

    passage_vectors, passage_backend = embedder.embed_texts(["赛事规则", "提交材料"])
    query_vector, query_backend = embedder.embed_query("提交截止时间")

    assert passage_backend == "gpu-worker:BAAI/bge-small-zh-v1.5"
    assert query_backend == "gpu-worker:BAAI/bge-small-zh-v1.5"
    assert passage_vectors == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert query_vector == [0.1, 0.2, 0.3]
    assert captured[0]["payload"] == {"texts": ["赛事规则", "提交材料"], "is_query": False}
    assert captured[1]["payload"] == {"texts": ["提交截止时间"], "is_query": True}

    _reset_embedder_state(embedder)


def test_remote_embedding_invalid_response_opens_circuit(monkeypatch):
    from agent.rag import embedder
    from agent.rag.embedder import SemanticEmbeddingUnavailable

    _reset_embedder_state(embedder)
    monkeypatch.setenv("AFH_GPU_MODE", "auto")
    monkeypatch.setenv("AFH_RAG_EMBEDDING_URL", "http://gpu-worker.local/embed")
    monkeypatch.setenv("AFH_GPU_CIRCUIT_BREAKER_SECONDS", "30")
    monkeypatch.setattr(embedder.url_request, "urlopen", lambda *_args, **_kwargs: _FakeResponse({"vectors": []}))

    with pytest.raises(SemanticEmbeddingUnavailable):
        embedder.embed_texts(["赛事规则"])

    status = embedder.embedding_runtime_status()
    assert status["remote_circuit_open"] is True
    assert "invalid vector count" in str(status["remote_last_error"])

    _reset_embedder_state(embedder)


def test_local_embedding_download_is_opt_in(monkeypatch):
    from agent.rag import embedder
    from agent.rag.embedder import SemanticEmbeddingUnavailable

    _reset_embedder_state(embedder)
    monkeypatch.delenv("AFH_RAG_EMBEDDING_URL", raising=False)
    monkeypatch.delenv("AFH_RAG_ALLOW_MODEL_DOWNLOAD", raising=False)
    monkeypatch.delenv("AFH_ALLOW_HASH_RAG_FALLBACK", raising=False)
    monkeypatch.setenv("AFH_GPU_MODE", "auto")
    monkeypatch.setattr(embedder, "_local_embedding_cache_available", lambda: False)

    with pytest.raises(SemanticEmbeddingUnavailable) as exc_info:
        embedder.embed_query("提交材料")

    assert "not cached locally" in str(exc_info.value)
    assert "AFH_RAG_EMBEDDING_URL" in str(exc_info.value)

    _reset_embedder_state(embedder)


def test_unavailable_local_embedding_is_cached_until_config_changes(monkeypatch):
    from agent.rag import embedder
    from agent.rag.embedder import SemanticEmbeddingUnavailable

    _reset_embedder_state(embedder)
    monkeypatch.delenv("AFH_RAG_EMBEDDING_URL", raising=False)
    monkeypatch.delenv("AFH_RAG_ALLOW_MODEL_DOWNLOAD", raising=False)
    monkeypatch.delenv("AFH_ALLOW_HASH_RAG_FALLBACK", raising=False)
    monkeypatch.setenv("AFH_GPU_MODE", "auto")
    calls = {"cache": 0}

    def missing_cache() -> bool:
        calls["cache"] += 1
        return False

    monkeypatch.setattr(embedder, "_local_embedding_cache_available", missing_cache)

    with pytest.raises(SemanticEmbeddingUnavailable):
        embedder.embed_query("提交材料")
    with pytest.raises(SemanticEmbeddingUnavailable):
        embedder.embed_query("提交材料")

    assert calls["cache"] == 1

    monkeypatch.setenv("AFH_RAG_EMBEDDING_URL", "http://gpu-worker.local/embed")
    monkeypatch.setattr(
        embedder.url_request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse({
            "vectors": [[0.1, 0.2, 0.3]],
            "backend": "gpu-worker:BAAI/bge-small-zh-v1.5",
        }),
    )

    vector, backend = embedder.embed_query("提交材料")
    assert vector == [0.1, 0.2, 0.3]
    assert backend == "gpu-worker:BAAI/bge-small-zh-v1.5"

    _reset_embedder_state(embedder)
