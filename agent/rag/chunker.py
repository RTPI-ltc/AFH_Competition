from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from agent.rag.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MERGE_TARGET,
)


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_WHITESPACE = re.compile(r"[ \t　]+")


@dataclass(frozen=True)
class Chunk:
    text: str
    char_start: int
    char_end: int


def _normalize_paragraph(text: str) -> str:
    lines = [_WHITESPACE.sub(" ", line.strip()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _iter_paragraphs(text: str) -> Iterable[tuple[str, int, int]]:
    if not text:
        return
    cursor = 0
    for raw in _PARAGRAPH_SPLIT.split(text):
        if not raw:
            cursor += 2
            continue
        start = text.find(raw, cursor)
        if start < 0:
            start = cursor
        end = start + len(raw)
        cursor = end
        normalized = _normalize_paragraph(raw)
        if normalized:
            yield normalized, start, end


def _sliding_window(
    text: str,
    base_offset: int,
    chunk_size: int,
    overlap: int,
) -> Iterable[Chunk]:
    if chunk_size <= 0:
        chunk_size = DEFAULT_CHUNK_SIZE
    stride = max(1, chunk_size - max(0, overlap))
    length = len(text)
    start = 0
    while start < length:
        end = min(length, start + chunk_size)
        piece = text[start:end].strip()
        if piece:
            yield Chunk(
                text=piece,
                char_start=base_offset + start,
                char_end=base_offset + end,
            )
        if end >= length:
            break
        start += stride


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    merge_target: int = DEFAULT_MERGE_TARGET,
) -> list[Chunk]:
    if not text or not text.strip():
        return []

    paragraphs = list(_iter_paragraphs(text))
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    buffer_text: list[str] = []
    buffer_start: int | None = None
    buffer_end: int = 0
    buffer_len: int = 0

    def flush_buffer() -> None:
        nonlocal buffer_text, buffer_start, buffer_end, buffer_len
        if buffer_text and buffer_start is not None:
            merged = "\n".join(buffer_text).strip()
            if merged:
                chunks.append(Chunk(text=merged, char_start=buffer_start, char_end=buffer_end))
        buffer_text = []
        buffer_start = None
        buffer_end = 0
        buffer_len = 0

    for paragraph, start, end in paragraphs:
        if len(paragraph) > chunk_size:
            flush_buffer()
            chunks.extend(_sliding_window(paragraph, start, chunk_size, overlap))
            continue

        if buffer_start is None:
            buffer_start = start

        prospective = buffer_len + len(paragraph) + (1 if buffer_text else 0)
        if buffer_text and prospective > chunk_size:
            flush_buffer()
            buffer_start = start

        buffer_text.append(paragraph)
        buffer_end = end
        buffer_len = sum(len(item) for item in buffer_text) + max(0, len(buffer_text) - 1)

        if buffer_len >= merge_target:
            flush_buffer()

    flush_buffer()
    return chunks
