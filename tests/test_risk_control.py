from __future__ import annotations

import sys
import uuid
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "rag_citation.db"))
    from agent import database

    database.init_db()
    project_id = database.ensure_project(str(uuid.uuid4()), name="引用测试项目")
    conversation_id = database.ensure_conversation(project_id, str(uuid.uuid4()), title="引用测试对话")
    return database, project_id, conversation_id


def test_rag_chunks_are_added_to_prompt_and_metadata(tmp_path, monkeypatch):
    database, project_id, conversation_id = _setup_db(tmp_path, monkeypatch)

    from agent import chat

    chunk = {
        "kb_id": "official_airs_hackathon",
        "source_file": "AIRS 黑客松赛事知识样例.txt",
        "text": "参赛团队需要提交项目说明文档、可运行 Demo、演示视频和附件清单。",
        "score": 0.03,
        "dense_score": 0.81,
        "bm25_score": 4.2,
        "rrf_score": 0.03,
    }
    captured: dict[str, str] = {}

    def fake_llm(system_prompt: str, user_prompt: str) -> str:
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return """
        {
          "reply": "需要提交项目说明文档、可运行 Demo、演示视频和附件清单。",
          "confidence": "high",
          "evidence_notes": ["依据 AIRS 黑客松赛事知识样例"],
          "follow_up_questions": []
        }
        """

    monkeypatch.setattr(chat, "llm_available", lambda: True)
    monkeypatch.setattr(chat, "retrieve_with_diagnostics", lambda *_args, **_kwargs: ([chunk], {
        "retrieval_mode": "hybrid",
        "retrieval_backend": "sentence-transformers:BAAI/bge-small-zh-v1.5",
        "gpu_mode": "auto",
        "semantic_error": None,
        "retrieval_notices": [],
    }))
    monkeypatch.setattr(chat, "call_llm", fake_llm)

    result = chat.handle_chat(
        project_id,
        conversation_id,
        "赛事需要提交哪些材料？",
        knowledge_ids=["official_airs_hackathon"],
    )

    payload = json.loads(captured["user"])
    assert "selected_agent" in captured["system"]
    assert payload["retrieved_chunk_count"] == 1
    assert payload["retrieved_chunks"][0]["source_file"] == "AIRS 黑客松赛事知识样例.txt"
    assert payload["retrieved_chunks"][0]["text"].startswith("参赛团队需要提交")
    assert result["agent_id"] == "hackathon-assistant"
    assert result["agent_name"]
    assert result["runtime_backend"] in {"agentscope", "agentscope-compatible-fallback"}
    assert result["confidence"] == "high"
    assert result["evidence_notes"] == ["依据 AIRS 黑客松赛事知识样例"]
    assert result["follow_up_questions"] == []
    assert result["rag_chunks"][0]["source_file"] == "AIRS 黑客松赛事知识样例.txt"
    assert result["knowledge_ids"] == ["official_airs_hackathon"]

    messages = database.list_conversation_messages(conversation_id)
    metadata = messages[-1]["metadata"]
    assert metadata["agent_id"] == result["agent_id"]
    assert metadata["agent_name"] == result["agent_name"]
    assert metadata["runtime_backend"] == result["runtime_backend"]
    assert metadata["confidence"] == "high"
    assert metadata["evidence_notes"] == ["依据 AIRS 黑客松赛事知识样例"]
    assert metadata["follow_up_questions"] == []
    assert metadata["rag_chunks"][0]["snippet"].startswith("参赛团队需要提交")


def test_non_json_model_reply_is_preserved_with_low_confidence_risk(tmp_path, monkeypatch):
    _database, project_id, conversation_id = _setup_db(tmp_path, monkeypatch)

    from agent import chat

    monkeypatch.setattr(chat, "llm_available", lambda: True)
    monkeypatch.setattr(chat, "retrieve_with_diagnostics", lambda *_args, **_kwargs: ([], {
        "retrieval_mode": "no-hit",
        "retrieval_backend": "bm25-only",
        "gpu_mode": "auto",
        "semantic_error": None,
        "retrieval_notices": [],
    }))
    monkeypatch.setattr(chat, "call_llm", lambda *_args: "这是一个纯文本回答。")

    result = chat.handle_chat(project_id, conversation_id, "课程考试范围是什么？")

    assert result["reply"] == "这是一个纯文本回答。"
    assert result["agent_id"] == "hackathon-assistant"
    assert result["agent_name"]
    assert result["runtime_backend"] in {"agentscope", "agentscope-compatible-fallback"}
    assert result["confidence"] == "low"
    assert result["evidence_notes"]
    assert any("知识库" in note for note in result["evidence_notes"])
    assert result["follow_up_questions"]
    assert result["rag_chunks"] == []
