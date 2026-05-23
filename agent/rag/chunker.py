"""Chunking with paragraph + sentence-boundary awareness.

Strategy:
- Split on blank lines into paragraphs (each carries absolute char_start/end).
- Markdown ATX headings (# / ## / ...) act as hard boundaries: they always
  start a fresh chunk so a heading's body never bleeds into the prior section.
- Paragraphs shorter than chunk_size are merged until merge_target is reached;
  paragraphs longer than chunk_size are slid in windows that prefer to end on
  a Chinese / ASCII sentence terminator instead of breaking mid-sentence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from agent.rag.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MERGE_TARGET,
    SENTENCE_BOUNDARY_LOOKBACK,
)


_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_WHITESPACE = re.compile(r"[ \t　]+")
_MD_HEADING = re.compile(r"^#{1,6}\s+\S")
_SENTENCE_ENDERS = "。！？!?；;.\n"


@dataclass(frozen=True)
class Chunk:
    text: str
    char_start: int
    char_end: int


def _normalize_paragraph(text: str) -> str:
    lines = [_WHITESPACE.sub(" ", line.strip()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _iter_paragraphs(text: str) -> Iterable[tuple[str, int, int, bool]]:
    """Yield (paragraph_text, char_start, char_end, is_heading).

    `is_heading` is True for markdown ATX headings so the caller can treat them
    as hard boundaries.
    """
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
        if not normalized:
            continue
        first_line = normalized.split("\n", 1)[0]
        is_heading = bool(_MD_HEADING.match(first_line))
        yield normalized, start, end, is_heading


def _find_sentence_boundary(text: str, target: int, lookback: int) -> int:
    """Return an index <= target that ends right after a sentence terminator,
    looking back at most `lookback` characters. Falls back to `target` if no
    boundary is found in the lookback window."""
    if target >= len(text):
        return len(text)
    lower = max(0, target - lookback)
    for idx in range(target, lower, -1):
        if text[idx - 1] in _SENTENCE_ENDERS:
            return idx
    return target


def _sliding_window(
    text: str,
    base_offset: int,
    chunk_size: int,
    overlap: int,
) -> Iterable[Chunk]:
    if chunk_size <= 0:
        chunk_size = DEFAULT_CHUNK_SIZE
    length = len(text)
    start = 0
    while start < length:
        target_end = min(length, start + chunk_size)
        end = (
            target_end
            if target_end >= length
            else _find_sentence_boundary(text, target_end, SENTENCE_BOUNDARY_LOOKBACK)
        )
        if end <= start:  # safety: never make zero-width windows
            end = target_end
        piece = text[start:end].strip()
        if piece:
            yield Chunk(
                text=piece,
                char_start=base_offset + start,
                char_end=base_offset + end,
            )
        if end >= length:
            break
        # Advance by (chunk_size - overlap), but make sure we still make progress
        # when sentence-boundary trimming kept the window very short.
        stride = max(1, chunk_size - max(0, overlap))
        next_start = max(start + 1, end - max(0, overlap))
        if next_start - start < stride // 2:
            next_start = start + stride
        start = next_start


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

    for paragraph, start, end, is_heading in paragraphs:
        # Markdown heading is always its own boundary: flush whatever was
        # buffered and let the heading + following paragraphs start fresh.
        if is_heading:
            flush_buffer()
            buffer_start = start
            buffer_text.append(paragraph)
            buffer_end = end
            buffer_len = len(paragraph)
            continue

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
