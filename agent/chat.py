from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from agent import database
from agent.agents import get_agent_spec
from agent.llm import call_llm, llm_available, parse_llm_json, stream_llm
from agent.rag.embedder import SemanticEmbeddingUnavailable
from agent.rag.retriever import retrieve_with_diagnostics
from agent.runtime import AgentRunRequest, normalize_streamed_result, run_agent, stream_agent_reply


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _retrieve_chunks(message: str, knowledge_ids: list[str]) -> tuple[list[dict[str, Any]], str | None, dict[str, Any]]:
    if not knowledge_ids:
        return [], None, {"retrieval_mode": "no-knowledge-selected", "retrieval_backend": "", "retrieval_notices": []}
    try:
        chunks, diagnostics = retrieve_with_diagnostics(message, knowledge_ids)
        semantic_error = str(diagnostics.get("semantic_error") or "").strip()
        retrieval_error = semantic_error if semantic_error and not chunks else None
        return chunks, retrieval_error, diagnostics
    except SemanticEmbeddingUnavailable as exc:
        return [], str(exc), {
            "retrieval_mode": "failed",
            "retrieval_backend": "",
            "semantic_error": str(exc),
            "retrieval_notices": [str(exc)],
        }
    except Exception as exc:
        message = f"RAG retrieval failed: {exc}"
        return [], message, {
            "retrieval_mode": "failed",
            "retrieval_backend": "",
            "semantic_error": message,
            "retrieval_notices": [message],
        }


def _rag_summary(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for chunk in chunks:
        text = str(chunk.get("text") or "").strip()
        snippet = text[:160] + ("..." if len(text) > 160 else "")
        summary.append(
            {
                "kb_id": chunk.get("kb_id") or "",
                "source_file": chunk.get("source_file") or "",
                "score": chunk.get("score"),
                "dense_score": chunk.get("dense_score"),
                "bm25_score": chunk.get("bm25_score"),
                "rrf_score": chunk.get("rrf_score"),
                "retrieval_mode": chunk.get("retrieval_mode") or "",
                "retrieval_backend": chunk.get("retrieval_backend") or "",
                "gpu_mode": chunk.get("gpu_mode") or "",
                "snippet": snippet,
            }
        )
    return summary


def _metadata(
    agent_result: dict[str, Any],
    rag_chunks: list[dict[str, Any]] | None = None,
    knowledge_ids: list[str] | None = None,
    retrieval_error: str | None = None,
    timings_ms: dict[str, int] | None = None,
    retrieval_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_notes = [str(item) for item in _list_or_empty(agent_result.get("evidence_notes"))]
    diagnostics = retrieval_diagnostics or {}
    for item in _list_or_empty(diagnostics.get("retrieval_notices")):
        text = str(item)
        if text and text not in evidence_notes:
            evidence_notes.append(text)
    semantic_error = str(diagnostics.get("semantic_error") or "").strip()
    if semantic_error and semantic_error not in evidence_notes:
        evidence_notes.append(semantic_error)
    if retrieval_error:
        if retrieval_error not in evidence_notes:
            evidence_notes.append(retrieval_error)
    metadata: dict[str, Any] = {
        "event": "chat_reply",
        "agent_id": agent_result.get("agent_id") or "",
        "agent_name": agent_result.get("agent_name") or "",
        "runtime_backend": agent_result.get("runtime_backend") or "",
        "confidence": "low" if retrieval_error else (agent_result.get("confidence") or "low"),
        "evidence_notes": evidence_notes,
        "follow_up_questions": _list_or_empty(agent_result.get("follow_up_questions")),
        "rag_chunks": rag_chunks or [],
        "knowledge_ids": knowledge_ids or [],
        "timings_ms": timings_ms or {},
        "retrieval_mode": diagnostics.get("retrieval_mode") or "",
        "retrieval_backend": diagnostics.get("retrieval_backend") or "",
        "gpu_mode": diagnostics.get("gpu_mode") or "",
        "semantic_error": semantic_error,
    }
    if retrieval_error:
        metadata["retrieval_error"] = retrieval_error
    return metadata


def _stream_text_chunks(text: str, chunk_size: int = 36) -> Iterator[str]:
    clean = text or ""
    if not clean:
        return
    for start in range(0, len(clean), chunk_size):
        yield clean[start:start + chunk_size]


def stream_chat(
    project_id: str,
    conversation_id: str,
    message: str,
    knowledge_ids: list[str] | None = None,
    agent_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    total_started = time.perf_counter()
    projects = database.list_projects()
    project = next((item for item in projects if item["id"] == project_id), {"id": project_id, "name": "当前项目"})
    history = database.list_conversation_messages(conversation_id)
    kb_ids = list(knowledge_ids or [])
    selected_spec = get_agent_spec(agent_id)

    database.add_conversation_message(
        conversation_id,
        "user",
        message,
        {"event": "chat", "knowledge_ids": kb_ids, "agent_id": selected_spec.id},
    )

    yield {
        "type": "agent_state",
        "item": {
            "phase": "retrieving",
            "agent_id": selected_spec.id,
            "agent_name": selected_spec.name,
            "runtime_backend": "",
            "confidence": "medium",
            "evidence_notes": [],
            "follow_up_questions": [],
            "knowledge_ids": kb_ids,
        },
    }

    retrieval_started = time.perf_counter()
    retrieved_chunks, retrieval_error, retrieval_diagnostics = _retrieve_chunks(message, kb_ids)
    retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)
    rag_summary = _rag_summary(retrieved_chunks)

    partial_metadata = _metadata(
        {
            "agent_id": selected_spec.id,
            "agent_name": selected_spec.name,
            "runtime_backend": "",
            "confidence": "medium",
            "evidence_notes": [],
            "follow_up_questions": [],
        },
        rag_summary,
        kb_ids,
        retrieval_error,
        {"retrieval": retrieval_ms, "agent": 0, "total": int((time.perf_counter() - total_started) * 1000)},
        retrieval_diagnostics,
    )
    partial_metadata["phase"] = "generating"
    yield {"type": "agent_state", "item": partial_metadata}
    if rag_summary:
        yield {"type": "rag_chunks", "items": rag_summary}

    request_payload = AgentRunRequest(
        project=project,
        message=message,
        agent_id=selected_spec.id,
        knowledge_ids=kb_ids,
        retrieved_chunks=retrieved_chunks,
        retrieval_error=retrieval_error,
        history=history,
    )

    agent_started = time.perf_counter()
    reply_parts: list[str] = []
    try:
        if not llm_available():
            agent_result = run_agent(
                request_payload,
                llm_available=llm_available,
                call_llm=call_llm,
                parse_json=parse_llm_json,
            ).to_dict()
            reply = str(agent_result.get("reply") or "")
            for part in _stream_text_chunks(reply):
                reply_parts.append(part)
                yield {"type": "text", "content": part}
        else:
            for part in stream_agent_reply(
                request_payload,
                llm_available=llm_available,
                stream_llm=stream_llm,
            ):
                if not part:
                    continue
                reply_parts.append(part)
                yield {"type": "text", "content": part}
            reply = "".join(reply_parts)
            agent_result = normalize_streamed_result(reply, request_payload, selected_spec).to_dict()
            if not reply_parts:
                reply = str(agent_result.get("reply") or "")
                for part in _stream_text_chunks(reply):
                    reply_parts.append(part)
                    yield {"type": "text", "content": part}
    except Exception as exc:
        if not reply_parts:
            try:
                agent_result = run_agent(
                    request_payload,
                    llm_available=llm_available,
                    call_llm=call_llm,
                    parse_json=parse_llm_json,
                ).to_dict()
                reply = str(agent_result.get("reply") or "")
                for part in _stream_text_chunks(reply):
                    reply_parts.append(part)
                    yield {"type": "text", "content": part}
            except Exception as fallback_exc:
                reply = f"模型调用失败，本轮没有改动项目数据。错误：{fallback_exc}"
                agent_result = {
                    "reply": reply,
                    "confidence": "low",
                    "evidence_notes": ["模型调用失败，需要检查 API Key、base_url 或模型服务状态。"],
                    "follow_up_questions": [],
                    "agent_id": selected_spec.id,
                    "agent_name": selected_spec.name,
                    "runtime_backend": "agentscope-compatible-fallback",
                }
                for part in _stream_text_chunks(reply):
                    reply_parts.append(part)
                    yield {"type": "text", "content": part}
        else:
            note = f"\n\n（模型流式输出中断：{exc}）"
            reply_parts.append(note)
            yield {"type": "text", "content": note}
            agent_result = normalize_streamed_result("".join(reply_parts), request_payload, selected_spec).to_dict()
            agent_result["confidence"] = "low"
            notes = _list_or_empty(agent_result.get("evidence_notes"))
            notes.append(f"模型流式输出中断：{exc}")
            agent_result["evidence_notes"] = notes

    agent_ms = int((time.perf_counter() - agent_started) * 1000)
    reply = str(agent_result.get("reply") or "".join(reply_parts))
    timings_ms = {
        "retrieval": retrieval_ms,
        "agent": agent_ms,
        "total": int((time.perf_counter() - total_started) * 1000),
    }
    metadata = _metadata(agent_result, rag_summary, kb_ids, retrieval_error, timings_ms, retrieval_diagnostics)
    metadata["phase"] = "done"

    database.add_conversation_message(conversation_id, "assistant", reply, metadata)
    yield {"type": "agent_state", "item": metadata}
    yield {"type": "done"}


def handle_chat(
    project_id: str,
    conversation_id: str,
    message: str,
    knowledge_ids: list[str] | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    total_started = time.perf_counter()
    projects = database.list_projects()
    project = next((item for item in projects if item["id"] == project_id), {"id": project_id, "name": "当前项目"})
    history = database.list_conversation_messages(conversation_id)
    kb_ids = list(knowledge_ids or [])
    selected_spec = get_agent_spec(agent_id)

    database.add_conversation_message(
        conversation_id,
        "user",
        message,
        {"event": "chat", "knowledge_ids": kb_ids, "agent_id": selected_spec.id},
    )

    retrieval_started = time.perf_counter()
    retrieved_chunks, retrieval_error, retrieval_diagnostics = _retrieve_chunks(message, kb_ids)
    retrieval_ms = int((time.perf_counter() - retrieval_started) * 1000)
    rag_summary = _rag_summary(retrieved_chunks)

    agent_started = time.perf_counter()
    try:
        agent_result = run_agent(
            AgentRunRequest(
                project=project,
                message=message,
                agent_id=selected_spec.id,
                knowledge_ids=kb_ids,
                retrieved_chunks=retrieved_chunks,
                retrieval_error=retrieval_error,
                history=history,
            ),
            llm_available=llm_available,
            call_llm=call_llm,
            parse_json=parse_llm_json,
        ).to_dict()
    except Exception as exc:
        agent_result = {
            "reply": f"模型调用失败，本轮没有改动项目数据。错误：{exc}",
            "confidence": "low",
            "evidence_notes": ["模型调用失败，需要检查 API Key、base_url 或模型服务状态。"],
            "follow_up_questions": [],
            "agent_id": selected_spec.id,
            "agent_name": selected_spec.name,
            "runtime_backend": "agentscope-compatible-fallback",
        }
    agent_ms = int((time.perf_counter() - agent_started) * 1000)

    reply = str(agent_result.get("reply") or "")
    timings_ms = {
        "retrieval": retrieval_ms,
        "agent": agent_ms,
        "total": int((time.perf_counter() - total_started) * 1000),
    }
    metadata = _metadata(agent_result, rag_summary, kb_ids, retrieval_error, timings_ms, retrieval_diagnostics)

    database.add_conversation_message(conversation_id, "assistant", reply, metadata)
    return {
        "reply": reply,
        **metadata,
        "messages": database.list_conversation_messages(conversation_id),
    }
