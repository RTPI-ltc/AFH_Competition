from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import Any, Callable

from agent.agents import AgentSpec, get_agent_spec


TEXT_FIELD_LIMIT = 700
HISTORY_CONTEXT_LIMIT = 8


@dataclass(frozen=True)
class AgentRunRequest:
    project: dict[str, Any]
    message: str
    agent_id: str | None
    knowledge_ids: list[str]
    retrieved_chunks: list[dict[str, Any]]
    retrieval_error: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class AgentRunResult:
    reply: str
    confidence: str
    evidence_notes: list[str]
    follow_up_questions: list[str]
    agent_id: str
    agent_name: str
    runtime_backend: str
    raw_output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "confidence": self.confidence,
            "evidence_notes": list(self.evidence_notes),
            "follow_up_questions": list(self.follow_up_questions),
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "runtime_backend": self.runtime_backend,
            "raw_output": dict(self.raw_output),
        }


def agentscope_available() -> bool:
    return find_spec("agentscope") is not None


def _runtime_backend() -> str:
    return "agentscope" if agentscope_available() else "agentscope-compatible-fallback"


def _clip_text(value: Any, limit: int = TEXT_FIELD_LIMIT) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[:limit]}..."


def _compact_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": project.get("id"),
        "name": project.get("name"),
        "description": _clip_text(project.get("description"), 240),
    }


def _compact_history_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": item.get("role"),
        "content": _clip_text(item.get("content")),
    }


def _agent_contract(spec: AgentSpec) -> str:
    return json.dumps(
        {
            "selected_agent": {
                "id": spec.id,
                "name": spec.name,
                "scenario": spec.scenario,
                "orchestration_goal": spec.orchestration_goal,
                "capabilities": list(spec.capabilities),
                "tools": list(spec.tools),
                "risk_controls": list(spec.risk_controls),
                "response_style": spec.response_style,
            },
            "output_schema": {
                "reply": "给用户看的中文回答。不要输出固定检查清单、优先级分析卡片、等待确认卡片或电商模板。",
                "confidence": "high|medium|low",
                "evidence_notes": ["引用依据、证据边界或资料缺口"],
                "follow_up_questions": ["需要用户补充的问题"],
            },
        },
        ensure_ascii=False,
    )


def build_system_prompt(spec: AgentSpec) -> str:
    return (
        "你是知识库 Agent 平台的 AgentScope 编排运行时中的一个专业 Agent。\n"
        "当前 Agent 不是由用户 prompt 假扮出来的，而是由系统根据 agent_id 选中的编排节点。\n"
        "你必须遵守所选 Agent 的能力边界、工具边界和风险控制策略。\n\n"
        f"Agent 编排契约：{_agent_contract(spec)}\n\n"
        "回答规则：\n"
        "- 优先依据检索到的知识库片段回答，并自然说明依据。\n"
        "- 证据不足时直接说不足，不要生成固定的检查清单模板。\n"
        "- 不要输出商品、SKU、上架、价格核查等旧电商 Agent 内容。\n"
        "- 不要把用户问题改写成『请作为某 Agent』的提示词；用户原话就是任务输入。\n"
        "- 严格返回 JSON，不要包裹 Markdown 代码块。"
    )


def build_stream_system_prompt(spec: AgentSpec) -> str:
    return (
        "你是知识库 Agent 平台的 AgentScope 编排运行时中的一个已选中 Agent。\n"
        "当前输出将直接流式展示给用户，所以不要返回 JSON，不要输出 Markdown 代码块。\n"
        "你必须遵守所选 Agent 的能力边界、工具边界和风险控制策略。\n\n"
        f"Agent 编排契约：{_agent_contract(spec)}\n\n"
        "回答规则：\n"
        "- 用户原话就是任务输入，不要把它改写成系统 prompt。\n"
        "- 优先依据 retrieved_chunks 中的知识库片段回答，并自然说明依据。\n"
        "- 证据不足时直接说明不足，给出需要补充的资料；不要生成固定检查清单模板。\n"
        "- 不要输出商品、SKU、上架、价格核查等旧电商 Agent 内容。\n"
        "- 只输出给用户看的中文正文。"
    )


def build_user_payload(request: AgentRunRequest) -> str:
    compact_history = [
        _compact_history_item(item)
        for item in request.history[-HISTORY_CONTEXT_LIMIT:]
    ]
    return json.dumps(
        {
            "project": _compact_project(request.project),
            "selected_knowledge_ids": request.knowledge_ids,
            "retrieved_chunk_count": len(request.retrieved_chunks),
            "retrieval_error": request.retrieval_error,
            "retrieved_chunks": [
                {
                    "kb_id": item.get("kb_id") or item.get("knowledge_id") or "",
                    "source_file": item.get("source_file") or "",
                    "score": item.get("score"),
                    "dense_score": item.get("dense_score"),
                    "bm25_score": item.get("bm25_score"),
                    "text": _clip_text(item.get("text"), 900),
                }
                for item in request.retrieved_chunks[:8]
            ],
            "recent_messages": compact_history,
            "user_message": request.message,
            "instruction": (
                "请使用系统选中的 Agent 编排身份处理 user_message。"
                "若 retrieved_chunk_count 为 0 或资料不相关，必须降低 confidence，"
                "在 evidence_notes 或 follow_up_questions 中说明需要补充哪些资料。"
            ),
        },
        ensure_ascii=False,
    )


def _parse_model_response(raw: str, parse_json: Callable[[str], Any]) -> dict[str, Any]:
    try:
        parsed = parse_json(raw)
    except Exception:
        return {
            "reply": raw.strip() or "模型没有返回可展示内容。",
            "confidence": "low",
            "evidence_notes": [],
            "follow_up_questions": [],
        }
    if isinstance(parsed, dict):
        return parsed
    return {
        "reply": str(parsed),
        "confidence": "low",
        "evidence_notes": [],
        "follow_up_questions": [],
    }


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_output(parsed: dict[str, Any], request: AgentRunRequest, spec: AgentSpec) -> AgentRunResult:
    reply = str(parsed.get("reply") or "").strip()
    if not reply:
        reply = "我没有得到足够明确的回答内容，请补充问题或选择相关知识库后重试。"

    confidence = str(parsed.get("confidence") or "medium").strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    evidence_notes = _text_list(parsed.get("evidence_notes"))
    follow_up_questions = _text_list(parsed.get("follow_up_questions"))
    if request.retrieval_error and not evidence_notes:
        evidence_notes.append(request.retrieval_error)
    if not request.retrieved_chunks:
        confidence = "low"
        if not evidence_notes:
            evidence_notes.append("当前问题没有检索到可用的知识库语义证据。")
        if not follow_up_questions:
            follow_up_questions.append("请补充或选择与当前任务直接相关的知识库资料。")

    return AgentRunResult(
        reply=reply,
        confidence=confidence,
        evidence_notes=evidence_notes,
        follow_up_questions=follow_up_questions,
        agent_id=spec.id,
        agent_name=spec.name,
        runtime_backend=_runtime_backend(),
        raw_output=parsed,
    )


def normalize_streamed_result(reply: str, request: AgentRunRequest, spec: AgentSpec) -> AgentRunResult:
    text = reply.strip()
    if not text:
        text = "本轮没有得到可展示的模型输出，请补充问题或稍后重试。"

    evidence_notes: list[str] = []
    for chunk in request.retrieved_chunks[:3]:
        source = str(chunk.get("source_file") or chunk.get("kb_id") or "知识库片段").strip()
        if source:
            evidence_notes.append(f"参考资料：{source}")

    if request.retrieval_error:
        evidence_notes.append(request.retrieval_error)

    follow_up_questions: list[str] = []
    confidence = "medium" if request.retrieved_chunks else "low"
    if not request.retrieved_chunks:
        if not evidence_notes:
            evidence_notes.append("当前问题没有检索到可用的知识库语义证据。")
        follow_up_questions.append("请补充或选择与当前任务直接相关的知识库资料。")

    return AgentRunResult(
        reply=text,
        confidence=confidence,
        evidence_notes=evidence_notes,
        follow_up_questions=follow_up_questions,
        agent_id=spec.id,
        agent_name=spec.name,
        runtime_backend=_runtime_backend(),
        raw_output={"streamed": True},
    )


def fallback_result(request: AgentRunRequest, reason: str) -> AgentRunResult:
    spec = get_agent_spec(request.agent_id)
    notes = ["模型 API Key 尚未配置，本轮只完成 Agent 编排与知识库检索准备。"]
    if request.retrieval_error:
        notes.append(request.retrieval_error)
    if not request.retrieved_chunks:
        notes.append("当前问题没有检索到可用知识库证据。")
    return AgentRunResult(
        reply=(
            f"已选择「{spec.name}」，但{reason}。"
            "请先在 API 配置中添加 OpenAI 兼容模型；如果需要可靠回答，也请确认已选择相关知识库。"
        ),
        confidence="low",
        evidence_notes=notes,
        follow_up_questions=[] if request.retrieved_chunks else ["需要补充或选择与问题相关的知识库。"],
        agent_id=spec.id,
        agent_name=spec.name,
        runtime_backend=_runtime_backend(),
        raw_output={},
    )


def run_agent(
    request: AgentRunRequest,
    *,
    llm_available: Callable[[], bool],
    call_llm: Callable[[str, str], str],
    parse_json: Callable[[str], Any],
) -> AgentRunResult:
    spec = get_agent_spec(request.agent_id)
    if not llm_available():
        return fallback_result(request, "模型 API Key 尚未配置")
    raw = call_llm(build_system_prompt(spec), build_user_payload(request))
    parsed = _parse_model_response(raw, parse_json)
    return normalize_output(parsed, request, spec)


def stream_agent_reply(
    request: AgentRunRequest,
    *,
    llm_available: Callable[[], bool],
    stream_llm: Callable[[str, str], Iterator[str]],
) -> Iterator[str]:
    spec = get_agent_spec(request.agent_id)
    if not llm_available():
        yield fallback_result(request, "模型 API Key 尚未配置").reply
        return
    yield from stream_llm(build_stream_system_prompt(spec), build_user_payload(request))
