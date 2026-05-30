from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _reset_embedder_state() -> None:
    from agent.rag import embedder

    embedder.reset_runtime_state()


def test_gpu_off_indexes_and_retrieves_with_local_bm25(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag"))
    monkeypatch.setenv("AFH_GPU_MODE", "off")
    monkeypatch.delenv("AFH_RAG_EMBEDDING_URL", raising=False)
    monkeypatch.delenv("AFH_ALLOW_HASH_RAG_FALLBACK", raising=False)
    _reset_embedder_state()

    from agent.rag.indexer import index_text
    from agent.rag.retriever import retrieve_with_diagnostics

    result = index_text(
        "kb_bm25_local",
        "rules.txt",
        "AIRS 黑客松提交材料包括项目说明文档、可运行 Demo、演示视频和附件清单。",
    )
    assert result.embedding_backend == "bm25-only"

    hits, diagnostics = retrieve_with_diagnostics("黑客松需要提交哪些材料", ["kb_bm25_local"], top_k=3)

    assert hits
    assert hits[0]["retrieval_mode"] == "bm25-only"
    assert diagnostics["retrieval_mode"] == "bm25-only"
    assert diagnostics["gpu_mode"] == "off"

    _reset_embedder_state()


def test_gpu_auto_falls_back_to_bm25_when_remote_is_unreachable(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag"))
    monkeypatch.setenv("AFH_GPU_MODE", "off")
    monkeypatch.delenv("AFH_ALLOW_HASH_RAG_FALLBACK", raising=False)
    _reset_embedder_state()

    from agent.rag import embedder
    from agent.rag.indexer import index_text
    from agent.rag.retriever import retrieve_with_diagnostics

    index_text(
        "kb_remote_down",
        "course.txt",
        "课程复习提纲应该覆盖核心概念、关键案例和常见误区。",
    )

    monkeypatch.setenv("AFH_GPU_MODE", "auto")
    monkeypatch.setenv("AFH_RAG_EMBEDDING_URL", "http://gpu-worker.local/embed")
    monkeypatch.setenv("AFH_GPU_CIRCUIT_BREAKER_SECONDS", "30")
    _reset_embedder_state()

    def fail_urlopen(*_args, **_kwargs):
        raise OSError("worker down")

    monkeypatch.setattr(embedder.url_request, "urlopen", fail_urlopen)

    hits, diagnostics = retrieve_with_diagnostics("复习提纲覆盖什么", ["kb_remote_down"], top_k=3)

    assert hits
    assert diagnostics["retrieval_mode"] == "bm25-only"
    assert diagnostics["semantic_error"]
    assert "worker down" in diagnostics["semantic_error"]
    assert embedder.embedding_runtime_status()["remote_circuit_open"] is True

    _reset_embedder_state()


def test_gpu_required_fails_when_embedding_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag"))
    monkeypatch.setenv("AFH_GPU_MODE", "required")
    monkeypatch.delenv("AFH_RAG_EMBEDDING_URL", raising=False)
    monkeypatch.delenv("AFH_ALLOW_HASH_RAG_FALLBACK", raising=False)
    _reset_embedder_state()

    from agent.rag.embedder import SemanticEmbeddingUnavailable
    from agent.rag.indexer import index_text

    with pytest.raises(SemanticEmbeddingUnavailable):
        index_text("kb_required", "rules.txt", "必须走 GPU 的语义索引。")

    _reset_embedder_state()
