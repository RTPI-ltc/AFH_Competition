from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_raganything_cpu_ingestion_indexes_text_without_optional_package(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag"))
    monkeypatch.setenv("AFH_ALLOW_HASH_RAG_FALLBACK", "1")

    from agent.ingestion import raganything_pipeline
    from agent.rag.store import kb_store

    monkeypatch.setattr(raganything_pipeline, "raganything_available", lambda: False)
    text = (
        "AIRS 黑客松提交要求\n\n"
        "团队需要提交项目说明文档、可运行 Demo、演示视频和附件清单。\n\n"
        "评审会关注业务价值、技术完整性、可信机制和演示清晰度。"
    )

    result = raganything_pipeline.ingest_uploaded_bytes(
        "kb_cpu_ingestion",
        [("赛事说明.txt", text.encode("utf-8"))],
    )

    assert result.architecture == "rag-anything-compatible"
    assert result.backend == "local_cpu_fallback"
    assert result.raganything_available is False
    assert result.files_indexed == 1
    assert result.chunks_total >= 1
    assert result.content_types == ("text",)
    assert result.metadata["gpu_required"] is False

    chunks = kb_store("kb_cpu_ingestion").load_chunks()
    assert chunks
    assert chunks[0]["source_file"] == "赛事说明.txt"
    assert "Demo" in " ".join(item["text"] for item in chunks)


def test_raganything_retrieval_adapter_returns_empty_for_empty_input(monkeypatch):
    from agent.retrieval.raganything_adapter import retrieve_hits

    assert retrieve_hits("", ["kb_missing"]) == []
    assert retrieve_hits("赛事提交材料", []) == []


def test_raganything_retrieval_adapter_normalizes_local_hits(monkeypatch):
    from agent.retrieval import raganything_adapter

    monkeypatch.setattr(
        raganything_adapter,
        "retrieve_safe",
        lambda *_args, **_kwargs: [
            {
                "chunk_id": "c1",
                "kb_id": "kb_demo",
                "text": "参赛团队需要提交项目说明文档、可运行 Demo 和演示视频。",
                "source_file": "赛事说明.txt",
                "char_start": 0,
                "char_end": 28,
                "dense_score": 0.82,
                "bm25_score": 4.1,
                "rrf_score": 0.03,
                "metadata": {"source_file": "赛事说明.txt"},
            }
        ],
    )

    hits = raganything_adapter.retrieve_hits("提交材料", ["kb_demo"])

    assert len(hits) == 1
    hit = hits[0]
    assert hit.hit_kind == "hybrid"
    assert hit.modality == "text"
    assert hit.confidence == "high"
    assert hit.chunk.knowledge_id == "kb_demo"
    assert hit.chunk.content_type == "text"
    assert hit.metadata["architecture"] == "rag-anything-compatible"
