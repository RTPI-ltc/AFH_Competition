from __future__ import annotations

from pathlib import Path

import pytest

from agent.rag import indexer, retriever


@pytest.fixture
def kb_id(rag_tmp_root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "test_rag.db"))
    return "kb_test_indexer"


def test_index_text_and_search(kb_id: str) -> None:
    long_text = (
        "天猫618大促规则\n\n"
        "1. 商品需符合销量、好评率、库存的基础门槛。\n"
        "2. 活动价不得高于历史最低价。\n"
        "3. 同品类报名 SKU 数量需控制。\n\n"
        "京东双11规则\n\n"
        "1. 关注库存与发货时效。\n"
        "2. 报名互斥商品需剔除。"
    )
    result = indexer.index_text(kb_id, "rules.md", long_text)
    assert result.files_indexed == 1
    assert result.chunks_total >= 1
    assert result.embedding_backend  # 至少返回了某种 backend 字符串

    hits = retriever.retrieve_safe("618 商品销量门槛", [kb_id])
    assert isinstance(hits, list)


def test_index_skips_unchanged_file(kb_id: str) -> None:
    text = "条款内容：商品需满足销量门槛。\n\n额外说明。"
    first = indexer.index_text(kb_id, "rules.md", text)
    assert first.files_indexed == 1
    again = indexer.index_text(kb_id, "rules.md", text)
    assert again.files_indexed == 0
    assert again.files_skipped == 1


def test_index_replace_updates_chunks(kb_id: str) -> None:
    indexer.index_text(kb_id, "rules.md", "版本A 内容。")
    new_text = "版本B 内容更新更详细。"
    result = indexer.index_uploaded_bytes(
        kb_id,
        [("rules.md", new_text.encode("utf-8"))],
        replace_same_name=True,
    )
    assert result.files_indexed == 1
    assert result.chunks_total >= 1


def test_retrieve_safe_no_kb_returns_empty(kb_id: str) -> None:
    assert retriever.retrieve_safe("任意问题", []) == []
    assert retriever.retrieve_safe("", [kb_id]) == []
