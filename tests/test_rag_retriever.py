from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _write_chunks(store, chunks):
    store.save_chunks([
        {
            "chunk_id": item["chunk_id"],
            "text": item["text"],
            "source_file": item.get("source_file", "rules.md"),
            "char_start": item.get("char_start", 0),
            "char_end": item.get("char_end", len(item["text"])),
            "file_hash": "hash",
            "metadata": {},
        }
        for item in chunks
    ])


def test_hash_fallback_dense_noise_cannot_create_standalone_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag"))
    monkeypatch.setenv("AFH_ALLOW_HASH_RAG_FALLBACK", "1")

    from agent.rag import retriever
    from agent.rag.bm25 import build_bm25
    from agent.rag.store import kb_store

    store = kb_store("kb_hash_noise")
    _write_chunks(store, [
        {"chunk_id": "noise", "text": "钻石戒指保养和日常清洁说明。"},
        {"chunk_id": "target", "text": "平台活动互斥规则：已参加品牌日的商品不可重复报名。"},
    ])
    chunks = store.load_chunks()
    store.save_bm25(build_bm25(chunks).to_dict())

    monkeypatch.setattr(retriever, "is_hash_fallback", lambda: True)
    monkeypatch.setattr(retriever, "embed_query", lambda _query: ([1.0], "hash-fallback"))
    monkeypatch.setattr(retriever, "_dense_candidates", lambda *_args, **_kwargs: [(0, 0.99)])

    hits = retriever.retrieve("品牌日商品能不能重复报名", ["kb_hash_noise"], top_k=3)

    assert hits
    assert hits[0]["chunk_id"] == "target"
    assert all(item["chunk_id"] != "noise" for item in hits)


def test_hash_fallback_returns_empty_when_only_dense_has_noise(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag"))
    monkeypatch.setenv("AFH_ALLOW_HASH_RAG_FALLBACK", "1")

    from agent.rag import retriever
    from agent.rag.bm25 import build_bm25
    from agent.rag.store import kb_store

    store = kb_store("kb_dense_only")
    _write_chunks(store, [
        {"chunk_id": "noise", "text": "珍珠项链佩戴说明。"},
    ])
    chunks = store.load_chunks()
    store.save_bm25(build_bm25(chunks).to_dict())

    monkeypatch.setattr(retriever, "is_hash_fallback", lambda: True)
    monkeypatch.setattr(retriever, "embed_query", lambda _query: ([1.0], "hash-fallback"))
    monkeypatch.setattr(retriever, "_dense_candidates", lambda *_args, **_kwargs: [(0, 0.99)])

    assert retriever.retrieve("品牌日重复报名", ["kb_dense_only"], top_k=3) == []


def test_stale_bm25_is_rebuilt_before_search(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag"))
    monkeypatch.setenv("AFH_ALLOW_HASH_RAG_FALLBACK", "1")

    from agent.rag import retriever
    from agent.rag.bm25 import build_bm25
    from agent.rag.store import kb_store

    store = kb_store("kb_stale")
    stale_chunks = [{"chunk_id": "old", "text": "旧内容 品牌日", "source_file": "old.md", "char_start": 0, "char_end": 6, "file_hash": "x", "metadata": {}}]
    store.save_bm25(build_bm25(stale_chunks).to_dict())
    _write_chunks(store, [
        {"chunk_id": "new", "text": "新规则：活动价不得高于近30天最低价。"},
    ])

    monkeypatch.setattr(retriever, "is_hash_fallback", lambda: True)
    monkeypatch.setattr(retriever, "embed_query", lambda _query: ([1.0], "hash-fallback"))
    monkeypatch.setattr(retriever, "_dense_candidates", lambda *_args, **_kwargs: [])

    hits = retriever.retrieve("活动价 高于 近30天最低价", ["kb_stale"], top_k=3)

    assert hits
    assert hits[0]["chunk_id"] == "new"
    rebuilt = store.load_bm25()
    assert rebuilt
    assert rebuilt["chunk_ids"] == ["new"]


def test_semantic_retrieval_rejects_hash_index(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag"))
    monkeypatch.delenv("AFH_ALLOW_HASH_RAG_FALLBACK", raising=False)

    from agent.rag import retriever
    from agent.rag.embedder import SemanticEmbeddingUnavailable
    from agent.rag.store import kb_store

    store = kb_store("kb_hash_index")
    _write_chunks(store, [
        {"chunk_id": "old", "text": "活动互斥规则：品牌日商品不可重复报名。"},
    ])
    store.save_meta({"embedding_backend": "hash-fallback"})

    monkeypatch.setattr(retriever, "is_hash_fallback", lambda: False)
    monkeypatch.setattr(
        retriever,
        "embed_query",
        lambda _query: ([1.0] * 512, "sentence-transformers:BAAI/bge-small-zh-v1.5"),
    )

    with pytest.raises(SemanticEmbeddingUnavailable):
        retriever.retrieve("品牌日能否重复报名", ["kb_hash_index"], top_k=3)
