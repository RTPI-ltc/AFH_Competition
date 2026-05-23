"""Minimal BM25 implementation for the RAG hybrid retriever.

Stores a compact JSON serializable state. No external dependencies.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Sequence

from agent.rag.tokenizer import backend_name, tokenize, tokenize_query


K1 = 1.5
B = 0.75


@dataclass
class BM25State:
    chunk_ids: list[str] = field(default_factory=list)
    doc_lengths: list[int] = field(default_factory=list)
    avg_doc_len: float = 0.0
    df: dict[str, int] = field(default_factory=dict)
    postings: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    total_docs: int = 0
    k1: float = K1
    b: float = B
    tokenizer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_ids": list(self.chunk_ids),
            "doc_lengths": list(self.doc_lengths),
            "avg_doc_len": self.avg_doc_len,
            "df": dict(self.df),
            "postings": {term: list(pl) for term, pl in self.postings.items()},
            "total_docs": self.total_docs,
            "k1": self.k1,
            "b": self.b,
            "tokenizer": self.tokenizer,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "BM25State":
        postings_raw = payload.get("postings") or {}
        postings: dict[str, list[tuple[int, int]]] = {}
        for term, items in postings_raw.items():
            cleaned: list[tuple[int, int]] = []
            for item in items:
                if not item:
                    continue
                if isinstance(item, dict):
                    doc_idx = int(item.get("doc", -1))
                    tf = int(item.get("tf", 0))
                else:
                    doc_idx = int(item[0])
                    tf = int(item[1])
                if doc_idx >= 0 and tf > 0:
                    cleaned.append((doc_idx, tf))
            postings[term] = cleaned
        return cls(
            chunk_ids=list(payload.get("chunk_ids") or []),
            doc_lengths=[int(x) for x in payload.get("doc_lengths") or []],
            avg_doc_len=float(payload.get("avg_doc_len") or 0.0),
            df={k: int(v) for k, v in (payload.get("df") or {}).items()},
            postings=postings,
            total_docs=int(payload.get("total_docs") or 0),
            k1=float(payload.get("k1") or K1),
            b=float(payload.get("b") or B),
            tokenizer=str(payload.get("tokenizer") or ""),
        )


def build_bm25(chunks: Sequence[dict[str, Any]], *, k1: float = K1, b: float = B) -> BM25State:
    """Build a BM25 inverted index over the chunk texts."""
    state = BM25State(k1=k1, b=b, tokenizer=backend_name())
    if not chunks:
        return state

    df_counter: Counter[str] = Counter()
    doc_lengths: list[int] = []
    chunk_ids: list[str] = []

    # First pass: tokenize, capture lengths and document frequencies
    tokenized: list[list[str]] = []
    for chunk in chunks:
        text = str(chunk.get("text") or "")
        tokens = tokenize(text)
        tokenized.append(tokens)
        doc_lengths.append(len(tokens))
        chunk_ids.append(str(chunk.get("chunk_id") or ""))
        for term in set(tokens):
            df_counter[term] += 1

    total = len(tokenized)
    avg_len = (sum(doc_lengths) / total) if total else 0.0

    postings: dict[str, list[tuple[int, int]]] = {}
    for doc_idx, tokens in enumerate(tokenized):
        if not tokens:
            continue
        tf_counter = Counter(tokens)
        for term, tf in tf_counter.items():
            postings.setdefault(term, []).append((doc_idx, tf))

    state.chunk_ids = chunk_ids
    state.doc_lengths = doc_lengths
    state.avg_doc_len = avg_len
    state.df = dict(df_counter)
    state.postings = postings
    state.total_docs = total
    return state


def _idf(state: BM25State, term: str) -> float:
    df = state.df.get(term, 0)
    if df <= 0:
        return 0.0
    numerator = state.total_docs - df + 0.5
    denominator = df + 0.5
    return math.log(1.0 + (numerator / denominator))


def search_bm25(state: BM25State, query: str, top_k: int = 8) -> list[tuple[int, float]]:
    """Return [(doc_index, score), ...] sorted by descending score, length <= top_k."""
    if not query or state.total_docs == 0:
        return []
    terms = tokenize_query(query)
    if not terms:
        return []

    scores: dict[int, float] = {}
    k1 = state.k1
    b = state.b
    avg_len = state.avg_doc_len or 1.0

    for term in terms:
        postings = state.postings.get(term)
        if not postings:
            continue
        idf = _idf(state, term)
        if idf <= 0:
            continue
        for doc_idx, tf in postings:
            doc_len = state.doc_lengths[doc_idx] if doc_idx < len(state.doc_lengths) else 0
            norm = 1.0 - b + b * (doc_len / avg_len)
            score = idf * (tf * (k1 + 1.0)) / (tf + k1 * norm)
            if score <= 0:
                continue
            scores[doc_idx] = scores.get(doc_idx, 0.0) + score

    if not scores:
        return []
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return ranked[:top_k]
