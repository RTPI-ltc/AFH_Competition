from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from agent.rag.bm25 import build_bm25
from agent.rag.chunker import Chunk, chunk_text
from agent.rag.embedder import embed_texts
from agent.rag.loaders import iter_files, load_bytes, load_file, supported_extension
from agent.rag.store import KBStore, hash_bytes, kb_store

logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    knowledge_id: str
    files_indexed: int
    files_skipped: int
    chunks_added: int
    chunks_total: int
    embedding_backend: str
    errors: list[str]

    def to_dict(self) -> dict:
        return {
            "knowledge_id": self.knowledge_id,
            "files_indexed": self.files_indexed,
            "files_skipped": self.files_skipped,
            "chunks_added": self.chunks_added,
            "chunks_total": self.chunks_total,
            "embedding_backend": self.embedding_backend,
            "errors": list(self.errors),
        }


def _file_kind(filename: str) -> str:
    suffix = Path(filename).suffix.lower().lstrip(".")
    return suffix or "text"


def _chunks_to_records(
    store: KBStore,
    filename: str,
    file_hash: str,
    text_chunks: Iterable[Chunk],
) -> list[dict]:
    records: list[dict] = []
    for chunk in text_chunks:
        records.append({
            "chunk_id": uuid.uuid4().hex,
            "text": chunk.text,
            "source_file": filename,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "file_hash": file_hash,
            "metadata": {"kb_id": store.knowledge_id, "source_file": filename},
        })
    return records


def _rebuild_index(store: KBStore, chunks: list[dict]) -> tuple[str, int]:
    texts = [item["text"] for item in chunks]
    if not texts:
        store.write_index([], dim=None)
        store.clear_bm25()
        return "empty", 0
    vectors, backend = embed_texts(texts)
    if not vectors:
        # Even when dense fails, build BM25 so sparse retrieval still works.
        bm25_state = build_bm25(chunks)
        store.save_bm25(bm25_state.to_dict())
        return backend or "empty", 0
    dim = len(vectors[0])
    store.write_index(vectors, dim=dim)
    bm25_state = build_bm25(chunks)
    store.save_bm25(bm25_state.to_dict())
    return backend, dim


def index_uploaded_bytes(
    knowledge_id: str,
    files: list[tuple[str, bytes]],
    *,
    replace_same_name: bool = False,
) -> IndexResult:
    store = kb_store(knowledge_id)
    chunks = store.load_chunks()
    manifest = store.load_manifest()
    manifest_by_name = {item["filename"]: item for item in manifest}

    files_indexed = 0
    files_skipped = 0
    new_chunks_added = 0
    errors: list[str] = []
    changed = False

    for filename, data in files:
        ext = Path(filename).suffix.lower()
        if not supported_extension(ext):
            errors.append(f"{filename}: 不支持的文件类型 {ext}")
            files_skipped += 1
            continue
        digest = hash_bytes(data)
        existing = manifest_by_name.get(filename)
        if existing and existing.get("file_hash") == digest and not replace_same_name:
            files_skipped += 1
            continue
        try:
            text = load_bytes(filename, data)
        except Exception as exc:
            errors.append(f"{filename}: {exc}")
            files_skipped += 1
            continue
        if not text.strip():
            errors.append(f"{filename}: 文件为空或无法提取文本")
            files_skipped += 1
            continue
        store.store_raw(filename, data)
        if existing:
            chunks = [item for item in chunks if item.get("source_file") != filename]
        text_chunks = chunk_text(text)
        if not text_chunks:
            errors.append(f"{filename}: 切片为空")
            files_skipped += 1
            continue
        new_records = _chunks_to_records(store, filename, digest, text_chunks)
        chunks.extend(new_records)
        new_chunks_added += len(new_records)
        files_indexed += 1
        changed = True
        manifest_by_name[filename] = {
            "filename": filename,
            "file_hash": digest,
            "chunk_count": len(new_records),
            "uploaded_at": store.now_iso(),
            "byte_size": len(data),
            "file_kind": _file_kind(filename),
        }

    backend = "unchanged"
    if changed:
        store.save_chunks(chunks)
        store.save_manifest(list(manifest_by_name.values()))
        backend, _dim = _rebuild_index(store, chunks)
        bm25_payload = store.load_bm25() or {}
        store.save_meta({
            "knowledge_id": knowledge_id,
            "chunk_count": len(chunks),
            "file_count": len(manifest_by_name),
            "embedding_backend": backend,
            "bm25_tokenizer": bm25_payload.get("tokenizer", ""),
            "retrieval_mode": "hybrid",
            "updated_at": store.now_iso(),
        })

    return IndexResult(
        knowledge_id=knowledge_id,
        files_indexed=files_indexed,
        files_skipped=files_skipped,
        chunks_added=new_chunks_added,
        chunks_total=len(chunks),
        embedding_backend=backend if backend != "unchanged" else (store.load_meta().get("embedding_backend") or "unchanged"),
        errors=errors,
    )


def build_or_update_index(
    knowledge_id: str,
    paths: list[Path],
    *,
    replace_same_name: bool = False,
) -> IndexResult:
    files: list[tuple[str, bytes]] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            for file_path in iter_files(path):
                try:
                    files.append((file_path.name, file_path.read_bytes()))
                except Exception as exc:
                    logger.warning("读取失败 %s: %s", file_path, exc)
            continue
        if path.is_file():
            if not supported_extension(path.suffix):
                logger.info("跳过不支持文件: %s", path)
                continue
            try:
                files.append((path.name, path.read_bytes()))
            except Exception as exc:
                logger.warning("读取失败 %s: %s", path, exc)
            continue
    return index_uploaded_bytes(knowledge_id, files, replace_same_name=replace_same_name)


def index_text(
    knowledge_id: str,
    filename: str,
    text: str,
) -> IndexResult:
    data = text.encode("utf-8")
    return index_uploaded_bytes(knowledge_id, [(filename, data)])


# expose helpers
__all__ = [
    "IndexResult",
    "build_or_update_index",
    "index_text",
    "index_uploaded_bytes",
    "load_file",
]
