from __future__ import annotations

from agent.rag.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    RAG_DISABLED,
    SUPPORTED_EXTENSIONS,
    embedding_disabled,
    get_rag_root,
    knowledge_dir,
)
from agent.rag.indexer import build_or_update_index, index_uploaded_bytes
from agent.rag.prompt_format import append_context_to_system
from agent.rag.retriever import retrieve_safe
from agent.rag.store import KBStore, kb_store

__all__ = [
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHUNK_SIZE",
    "KBStore",
    "RAG_DISABLED",
    "SUPPORTED_EXTENSIONS",
    "append_context_to_system",
    "build_or_update_index",
    "embedding_disabled",
    "get_rag_root",
    "index_uploaded_bytes",
    "kb_store",
    "knowledge_dir",
    "retrieve_safe",
]
