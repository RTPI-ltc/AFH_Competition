from __future__ import annotations

from agent.rag.chunker import chunk_text


def test_chunk_text_empty_returns_empty() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_chunk_text_short_paragraph_returns_single_chunk() -> None:
    text = "这是一个简短的中文段落，足够短不需要切片。"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].char_start == 0


def test_chunk_text_long_paragraph_uses_sliding_window() -> None:
    text = "段" * 1200
    chunks = chunk_text(text, chunk_size=500, overlap=80)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert len(chunk.text) <= 500
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end <= len(text)


def test_chunk_text_merges_small_paragraphs() -> None:
    parts = ["第一段。", "第二段。", "第三段。", "第四段。"]
    text = "\n\n".join(parts)
    chunks = chunk_text(text, chunk_size=500, overlap=80, merge_target=20)
    assert len(chunks) >= 1
    assert all(chunk.text for chunk in chunks)


def test_chunk_text_preserves_offsets_monotonic() -> None:
    text = "段A。\n\n" + ("B" * 800) + "\n\n段C。"
    chunks = chunk_text(text)
    offsets = [chunk.char_start for chunk in chunks]
    assert offsets == sorted(offsets)
