from __future__ import annotations

import logging
import re
import threading
from typing import Callable, Iterable

logger = logging.getLogger(__name__)


_CJK_RANGES = (
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2B73F),
    (0xF900, 0xFAFF),
)

_ASCII_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.\-]*")
_PUNCT = re.compile(
    r"[\s　 、-〿＀-￯!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~]+"
)

_JIEBA_LOCK = threading.Lock()
_JIEBA: Callable[[str], Iterable[str]] | None = None
_JIEBA_TRIED = False


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def _get_jieba() -> Callable[[str], Iterable[str]] | None:
    global _JIEBA, _JIEBA_TRIED
    if _JIEBA_TRIED:
        return _JIEBA
    with _JIEBA_LOCK:
        if _JIEBA_TRIED:
            return _JIEBA
        try:
            import jieba  # type: ignore

            jieba.setLogLevel(logging.WARNING)
            _JIEBA = jieba.lcut
        except Exception as exc:
            logger.info("jieba 不可用，使用正则降级分词: %s", exc)
            _JIEBA = None
        _JIEBA_TRIED = True
    return _JIEBA


def _fallback_tokenize(text: str) -> list[str]:
    if not text:
        return []
    tokens: list[str] = []
    cursor = 0
    length = len(text)
    while cursor < length:
        ch = text[cursor]
        # ASCII alphanumeric words / SKU codes / numbers
        match = _ASCII_TOKEN.match(text, cursor)
        if match:
            tokens.append(match.group(0).lower())
            cursor = match.end()
            continue
        # CJK: emit single char + bigram with next CJK char if present
        if _is_cjk(ch):
            tokens.append(ch)
            nxt = text[cursor + 1] if cursor + 1 < length else ""
            if nxt and _is_cjk(nxt):
                tokens.append(ch + nxt)
            cursor += 1
            continue
        # Skip punctuation / whitespace
        cursor += 1
    return tokens


def _clean_jieba_tokens(raw: Iterable[str]) -> list[str]:
    tokens: list[str] = []
    for piece in raw:
        if not piece:
            continue
        piece = piece.strip()
        if not piece:
            continue
        if _PUNCT.fullmatch(piece):
            continue
        if piece.isascii():
            piece = piece.lower()
        tokens.append(piece)
    return tokens


def tokenize(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    cutter = _get_jieba()
    if cutter is not None:
        try:
            return _clean_jieba_tokens(cutter(text))
        except Exception as exc:
            logger.warning("jieba 分词失败，降级到正则: %s", exc)
    return _fallback_tokenize(text)


def tokenize_query(text: str) -> list[str]:
    # Same tokenizer, but de-duplicate while preserving order so BM25 doesn't double-count
    seen: set[str] = set()
    out: list[str] = []
    for token in tokenize(text):
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def backend_name() -> str:
    return "jieba" if _get_jieba() is not None else "regex-bigram"
