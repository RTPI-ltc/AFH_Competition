from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ContentType = Literal["text", "image", "table", "equation", "generic", "mixed"]
KnowledgeType = Literal["official", "personal"]
RetrievalKind = Literal["dense", "sparse", "graph", "hybrid", "multimodal", "external"]
Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class KnowledgeSource:
    id: str
    name: str
    type: KnowledgeType
    description: str = ""
    file_count: int = 0
    chunk_count: int = 0
    rag_backend: str = "local_cpu_fallback"
    index_backend: str = "local_hybrid"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "file_count": self.file_count,
            "chunk_count": self.chunk_count,
            "rag_backend": self.rag_backend,
            "index_backend": self.index_backend,
        }


@dataclass(frozen=True)
class KnowledgeAsset:
    id: str
    knowledge_id: str
    content_type: ContentType
    source_file: str
    asset_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_id": self.knowledge_id,
            "content_type": self.content_type,
            "source_file": self.source_file,
            "asset_path": self.asset_path,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    knowledge_id: str
    text: str
    source_file: str
    content_type: ContentType = "text"
    page: int | None = None
    section: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    asset_path: str | None = None
    related_chunk_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "knowledge_id": self.knowledge_id,
            "text": self.text,
            "source_file": self.source_file,
            "content_type": self.content_type,
            "page": self.page,
            "section": self.section,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "asset_path": self.asset_path,
            "related_chunk_ids": list(self.related_chunk_ids),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RetrievalHit:
    chunk: DocumentChunk
    fused_score: float
    hit_kind: RetrievalKind = "hybrid"
    modality: ContentType = "text"
    dense_score: float | None = None
    sparse_score: float | None = None
    rerank_score: float | None = None
    confidence: Confidence = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk": self.chunk.to_dict(),
            "dense_score": self.dense_score,
            "sparse_score": self.sparse_score,
            "rerank_score": self.rerank_score,
            "fused_score": self.fused_score,
            "hit_kind": self.hit_kind,
            "modality": self.modality,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IngestionResult:
    knowledge_id: str
    backend: str
    architecture: str
    files_indexed: int
    files_skipped: int
    chunks_added: int
    chunks_total: int
    embedding_backend: str
    content_types: tuple[ContentType, ...] = ("text",)
    raganything_available: bool = False
    assets: tuple[KnowledgeAsset, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "backend": self.backend,
            "architecture": self.architecture,
            "files_indexed": self.files_indexed,
            "files_skipped": self.files_skipped,
            "chunks_added": self.chunks_added,
            "chunks_total": self.chunks_total,
            "embedding_backend": self.embedding_backend,
            "content_types": list(self.content_types),
            "raganything_available": self.raganything_available,
            "assets": [asset.to_dict() for asset in self.assets],
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }
