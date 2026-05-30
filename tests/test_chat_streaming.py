from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def project_and_conv(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "stream_chat.db"))
    from agent import database

    database.init_db()
    project_id = database.ensure_project(str(uuid.uuid4()), name="流式输出测试项目")
    conv_id = database.ensure_conversation(project_id, str(uuid.uuid4()), title="流式测试会话")
    return database, project_id, conv_id


def test_stream_chat_emits_incremental_text_and_persists(project_and_conv, monkeypatch):
    from agent import chat

    database, project_id, conv_id = project_and_conv
    chunks = [
        {
            "kb_id": "kb_course",
            "source_file": "chapter-1.md",
            "score": 0.91,
            "dense_score": 0.88,
            "bm25_score": 12.4,
            "rrf_score": 0.04,
            "retrieval_mode": "hybrid",
            "retrieval_backend": "cpu",
            "gpu_mode": "auto",
            "text": "第一章介绍课程目标、作业要求和复习建议。",
        }
    ]
    diagnostics = {
        "retrieval_mode": "hybrid",
        "retrieval_backend": "cpu",
        "gpu_mode": "auto",
        "semantic_error": "",
        "retrieval_notices": [],
    }
    seen_prompt: dict[str, str] = {}

    monkeypatch.setattr(chat, "llm_available", lambda: True)
    monkeypatch.setattr(chat, "retrieve_with_diagnostics", lambda *_args, **_kwargs: (chunks, diagnostics))

    def fake_stream_llm(system: str, user: str):
        seen_prompt["system"] = system
        seen_prompt["user"] = user
        yield "第一段回答，"
        yield "第二段回答。"

    monkeypatch.setattr(chat, "stream_llm", fake_stream_llm)

    events = list(
        chat.stream_chat(
            project_id,
            conv_id,
            "帮我总结第一章要点",
            knowledge_ids=["kb_course"],
            agent_id="course-ta",
        )
    )

    assert events[0]["type"] == "agent_state"
    assert events[0]["item"]["phase"] == "retrieving"
    assert any(event["type"] == "rag_chunks" for event in events)

    text_events = [event for event in events if event["type"] == "text"]
    assert [event["content"] for event in text_events] == ["第一段回答，", "第二段回答。"]
    assert events[-1] == {"type": "done"}
    assert "不要返回 JSON" in seen_prompt["system"]
    assert "retrieved_chunk_count" in seen_prompt["user"]

    final_state = [event["item"] for event in events if event["type"] == "agent_state"][-1]
    assert final_state["phase"] == "done"
    assert final_state["agent_id"] == "course-ta"
    assert final_state["confidence"] == "medium"
    assert final_state["timings_ms"]["retrieval"] >= 0
    assert final_state["timings_ms"]["agent"] >= 0

    messages = database.list_conversation_messages(conv_id)
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[-1]["content"] == "第一段回答，第二段回答。"
    assert messages[-1]["metadata"]["rag_chunks"][0]["source_file"] == "chapter-1.md"
