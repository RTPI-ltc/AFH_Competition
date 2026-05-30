from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def project_and_conv(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "knowledge_agent.db"))
    from agent import database

    database.init_db()
    project_id = database.ensure_project(str(uuid.uuid4()), name="知识库 Agent 测试项目")
    conv_id = database.ensure_conversation(project_id, str(uuid.uuid4()), title="测试会话")
    return database, project_id, conv_id


def test_missing_llm_key_returns_recoverable_review_state(project_and_conv, monkeypatch):
    from agent import chat

    database, project_id, conv_id = project_and_conv
    monkeypatch.setattr(chat, "llm_available", lambda: False)
    monkeypatch.setattr(chat, "retrieve_with_diagnostics", lambda *_args, **_kwargs: ([], {
        "retrieval_mode": "no-hit",
        "retrieval_backend": "bm25-only",
        "gpu_mode": "auto",
        "semantic_error": None,
        "retrieval_notices": [],
    }))

    result = chat.handle_chat(
        project_id,
        conv_id,
        "请总结赛事提交材料。",
        knowledge_ids=["official_airs_hackathon"],
    )

    assert "API Key" in result["reply"]
    assert result["agent_id"] == "hackathon-assistant"
    assert result["agent_name"]
    assert result["runtime_backend"] in {"agentscope", "agentscope-compatible-fallback"}
    assert result["confidence"] == "low"
    assert any("API Key" in note for note in result["evidence_notes"])
    assert result["follow_up_questions"]
    assert result["rag_chunks"] == []
    assert result["knowledge_ids"] == ["official_airs_hackathon"]

    messages = database.list_conversation_messages(conv_id)
    assert [item["role"] for item in messages] == ["user", "assistant"]
    metadata = messages[-1]["metadata"]
    assert metadata["agent_id"] == result["agent_id"]
    assert metadata["agent_name"] == result["agent_name"]
    assert metadata["runtime_backend"] == result["runtime_backend"]
    assert metadata["confidence"] == "low"
    assert metadata["evidence_notes"] == result["evidence_notes"]
    assert metadata["follow_up_questions"] == result["follow_up_questions"]
    assert metadata["rag_chunks"] == []
    assert metadata["knowledge_ids"] == ["official_airs_hackathon"]


def test_model_json_is_normalized_without_listing_side_effects(project_and_conv, monkeypatch):
    from agent import chat, database

    _db, project_id, conv_id = project_and_conv
    monkeypatch.setattr(chat, "llm_available", lambda: True)
    monkeypatch.setattr(chat, "retrieve_with_diagnostics", lambda *_args, **_kwargs: ([], {
        "retrieval_mode": "no-hit",
        "retrieval_backend": "bm25-only",
        "gpu_mode": "auto",
        "semantic_error": None,
        "retrieval_notices": [],
    }))
    monkeypatch.setattr(
        chat,
        "call_llm",
        lambda *_args: """
        {
          "reply": "需要补充 Demo 运行说明和数据来源。",
          "confidence": "high",
          "evidence_notes": ["材料核对任务应优先检查可运行性和引用来源"],
          "follow_up_questions": ["是否已有演示视频？"]
        }
        """,
    )

    result = chat.handle_chat(project_id, conv_id, "帮我核对赛事提交材料。")

    assert result["reply"].startswith("需要补充")
    assert result["agent_id"] == "hackathon-assistant"
    assert result["agent_name"]
    assert result["runtime_backend"] in {"agentscope", "agentscope-compatible-fallback"}
    assert result["confidence"] == "low"
    assert result["evidence_notes"] == ["材料核对任务应优先检查可运行性和引用来源"]
    assert result["follow_up_questions"] == ["是否已有演示视频？"]
    assert result["rag_chunks"] == []
    assert database.list_listing_items(project_id) == []
