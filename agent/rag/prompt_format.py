from __future__ import annotations

from typing import Iterable


def _format_chunk(index: int, chunk: dict) -> str:
    source = chunk.get("source_file") or chunk.get("source") or "未知来源"
    kb_name = chunk.get("kb_name") or chunk.get("kb_id") or ""
    text = (chunk.get("text") or "").strip()
    score = chunk.get("score")
    header_extra = f"，相关度 {score:.2f}" if isinstance(score, (int, float)) else ""
    header = f"[片段{index}] 来源：{source}（{kb_name}）{header_extra}".rstrip()
    return f"{header}\n{text}"


def format_chunks(chunks: Iterable[dict]) -> str:
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        lines.append(_format_chunk(index, chunk))
    return "\n\n".join(lines)


def append_context_to_system(system_prompt: str, chunks: list[dict]) -> str:
    base = system_prompt.rstrip()
    if not chunks:
        return base
    body = format_chunks(chunks)
    return (
        f"{base}\n\n"
        "===== 知识库参考资料 =====\n"
        f"{body}\n"
        "===== 资料结束 =====\n"
        "请优先利用以上资料回答；若资料不足或与问题无关，请如实说明。"
    )
