from __future__ import annotations

from agent.rag.prompt_format import append_context_to_system, format_chunks


def test_append_context_returns_original_when_empty() -> None:
    assert append_context_to_system("你好", []) == "你好"


def test_append_context_renders_sections() -> None:
    chunks = [
        {
            "text": "片段A正文",
            "source_file": "rules.md",
            "kb_id": "kb_001",
            "score": 0.91,
        },
        {
            "text": "片段B正文",
            "source_file": "policy.txt",
            "kb_id": "kb_001",
            "score": 0.81,
        },
    ]
    prompt = append_context_to_system("BASE", chunks)
    assert "BASE" in prompt
    assert "知识库参考资料" in prompt
    assert "片段A正文" in prompt
    assert "片段B正文" in prompt
    assert "rules.md" in prompt
    assert "policy.txt" in prompt


def test_format_chunks_handles_missing_metadata() -> None:
    rendered = format_chunks([{"text": "无来源片段"}])
    assert "无来源片段" in rendered
    assert "未知来源" in rendered
