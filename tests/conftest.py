from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def _disable_rag_heavy_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AFH_DISABLE_RAG_EMBEDDING", "1")
    monkeypatch.setenv("AFH_DISABLE_LLM", os.getenv("AFH_DISABLE_LLM", "1"))


@pytest.fixture
def rag_tmp_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "rag_index"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AFH_RAG_ROOT", str(root))
    return root
