from __future__ import annotations

import hashlib
import json
import logging
import math
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from agent.rag.config import DEFAULT_EMBEDDING_DIM, knowledge_dir

logger = logging.getLogger(__name__)


@dataclass
class ChunkRecord:
    chunk_id: str
    text: str
    source_file: str
    char_start: int
    char_end: int
    file_hash: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source_file": self.source_file,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "file_hash": self.file_hash,
            "metadata": dict(self.metadata),
        }


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class KBStore:
    def __init__(self, knowledge_id: str):
        self.knowledge_id = knowledge_id
        self.directory: Path = knowledge_dir(knowledge_id)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.raw_dir: Path = self.directory / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.chunks_path: Path = self.directory / "chunks.json"
        self.manifest_path: Path = self.directory / "manifest.json"
        self.faiss_path: Path = self.directory / "index.faiss"
        self.meta_path: Path = self.directory / "meta.json"
        self.bm25_path: Path = self.directory / "bm25.json"

    # ---------------- manifest ----------------
    def load_manifest(self) -> list[dict[str, Any]]:
        if not self.manifest_path.exists():
            return []
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def save_manifest(self, manifest: list[dict[str, Any]]) -> None:
        self.manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------------- chunks ----------------
    def load_chunks(self) -> list[dict[str, Any]]:
        if not self.chunks_path.exists():
            return []
        try:
            payload = json.loads(self.chunks_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def save_chunks(self, chunks: list[dict[str, Any]]) -> None:
        self.chunks_path.write_text(
            json.dumps(chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------------- meta ----------------
    def load_meta(self) -> dict[str, Any]:
        if not self.meta_path.exists():
            return {}
        try:
            return json.loads(self.meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_meta(self, meta: dict[str, Any]) -> None:
        self.meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---------------- BM25 ----------------
    def load_bm25(self) -> dict[str, Any] | None:
        if not self.bm25_path.exists():
            return None
        try:
            payload = json.loads(self.bm25_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def save_bm25(self, payload: dict[str, Any]) -> None:
        self.bm25_path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    def clear_bm25(self) -> None:
        if self.bm25_path.exists():
            self.bm25_path.unlink()

    # ---------------- raw files ----------------
    def store_raw(self, filename: str, data: bytes) -> Path:
        safe_name = Path(filename).name
        target = self.raw_dir / safe_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    # ---------------- index rebuild ----------------
    def write_index(self, vectors: Sequence[Sequence[float]], dim: int | None = None) -> str:
        dim = dim or (len(vectors[0]) if vectors else DEFAULT_EMBEDDING_DIM)
        try:
            import faiss  # type: ignore
            import numpy as np  # type: ignore
        except Exception as exc:
            logger.info("faiss/numpy 缺失，使用 JSON 向量回退: %s", exc)
            payload = {"dim": dim, "vectors": [list(map(float, vec)) for vec in vectors]}
            self.faiss_path.with_suffix(".json").write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            if self.faiss_path.exists():
                self.faiss_path.unlink()
            return "json"
        if not vectors:
            if self.faiss_path.exists():
                self.faiss_path.unlink()
            return "faiss"
        matrix = np.asarray(vectors, dtype="float32")
        index = faiss.IndexFlatIP(dim)
        index.add(matrix)
        faiss.write_index(index, str(self.faiss_path))
        json_path = self.faiss_path.with_suffix(".json")
        if json_path.exists():
            json_path.unlink()
        return "faiss"

    def search(self, vector: Sequence[float], top_k: int = 4) -> list[tuple[int, float]]:
        if self.faiss_path.exists():
            try:
                import faiss  # type: ignore
                import numpy as np  # type: ignore
            except Exception:
                pass
            else:
                index = faiss.read_index(str(self.faiss_path))
                query = np.asarray([vector], dtype="float32")
                scores, indices = index.search(query, top_k)
                return [
                    (int(idx), float(score))
                    for idx, score in zip(indices[0], scores[0])
                    if int(idx) >= 0
                ]
        json_path = self.faiss_path.with_suffix(".json")
        if json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding="utf-8"))
                vectors = payload.get("vectors") or []
            except Exception:
                vectors = []
            scored: list[tuple[int, float]] = []
            for idx, vec in enumerate(vectors):
                scored.append((idx, _dot(vector, vec)))
            scored.sort(key=lambda item: item[1], reverse=True)
            return scored[:top_k]
        return []

    # ---------------- lifecycle ----------------
    def destroy(self) -> None:
        if self.directory.exists():
            shutil.rmtree(self.directory, ignore_errors=True)

    def now_iso(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def kb_store(knowledge_id: str) -> KBStore:
    return KBStore(knowledge_id)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    total = 0.0
    for x, y in zip(a, b):
        total += float(x) * float(y)
    norm_a = math.sqrt(sum(float(x) * float(x) for x in a)) or 1.0
    norm_b = math.sqrt(sum(float(y) * float(y) for y in b)) or 1.0
    return total / (norm_a * norm_b)
