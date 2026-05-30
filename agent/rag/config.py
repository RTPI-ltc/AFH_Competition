from __future__ import annotations

import os
from pathlib import Path


DEFAULT_CHUNK_SIZE = 350
DEFAULT_CHUNK_OVERLAP = 60
DEFAULT_CHUNK_STRIDE = DEFAULT_CHUNK_SIZE - DEFAULT_CHUNK_OVERLAP
DEFAULT_MERGE_TARGET = int(DEFAULT_CHUNK_SIZE * 0.8)
# When sliding inside a long paragraph, prefer to end the window at a sentence
# boundary even if that means producing a slightly shorter chunk.
SENTENCE_BOUNDARY_LOOKBACK = 80

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_EMBEDDING_DIM = 512
# Query instruction for bge-zh retrieval (recommended by BGE authors).
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："

SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".log",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
    ".pdf",
    ".docx",
)

TEXT_EXTENSIONS: frozenset[str] = frozenset({
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".log",
    ".csv",
    ".tsv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
})


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_db_dir() -> Path:
    configured = os.getenv("AFH_DB_PATH")
    if configured:
        return Path(configured).resolve().parent
    return _project_root() / "data"


def get_rag_root() -> Path:
    override = os.getenv("AFH_RAG_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return _resolve_db_dir() / "rag_index"


def knowledge_dir(knowledge_id: str) -> Path:
    safe = knowledge_id.replace("/", "_").replace("\\", "_").strip()
    if not safe:
        raise ValueError("knowledge_id 不能为空")
    root = get_rag_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / safe


def embedding_disabled() -> bool:
    return os.getenv("AFH_DISABLE_RAG_EMBEDDING") == "1"


def hash_fallback_allowed() -> bool:
    return os.getenv("AFH_ALLOW_HASH_RAG_FALLBACK", "0") == "1"


def gpu_mode() -> str:
    raw = os.getenv("AFH_GPU_MODE", "auto").strip().lower()
    if raw not in {"auto", "off", "required"}:
        return "auto"
    return raw


def gpu_required() -> bool:
    return gpu_mode() == "required"


def local_embedding_download_allowed() -> bool:
    return os.getenv("AFH_RAG_ALLOW_MODEL_DOWNLOAD", "0") == "1"


def remote_embedding_url() -> str:
    if gpu_mode() == "off":
        return ""
    return os.getenv("AFH_RAG_EMBEDDING_URL", "").strip().rstrip("/")


def remote_embedding_timeout() -> float:
    raw = os.getenv("AFH_RAG_EMBEDDING_TIMEOUT", "8").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 8.0


def gpu_circuit_breaker_seconds() -> float:
    raw = os.getenv("AFH_GPU_CIRCUIT_BREAKER_SECONDS", "60").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 60.0


RAG_DISABLED = os.getenv("AFH_DISABLE_RAG") == "1"


def preload_requested() -> bool:
    return os.getenv("AFH_RAG_PRELOAD") == "1"
