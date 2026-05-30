from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import chat, database
from agent.agents import list_agent_specs
from agent.llm import call_llm, model_status
from agent.ingestion import ingest_uploaded_bytes
from agent.rag import kb_store
from agent.rag.embedder import embedding_runtime_status
from agent.rag.indexer import index_text


router = APIRouter(prefix="/api", tags=["frontend"])

_official_knowledge: dict[str, dict[str, str]] = {
    "official_airs_hackathon": {
        "id": "official_airs_hackathon",
        "name": "AIRS 黑客松赛事知识样例",
        "type": "official",
        "description": "覆盖赛事规则、提交材料、评审标准和常见问题的演示知识库。",
        "content": (
            "AIRS 黑客松赛事知识样例\n"
            "参赛团队需要在截止时间前提交项目说明文档、可运行 Demo、演示视频和附件清单。"
            "项目说明文档建议包含问题背景、目标用户、核心功能、技术路线、数据来源、风险控制和后续计划。\n"
            "评审重点包括业务价值、技术实现完整性、可信与安全机制、创新性、演示清晰度和落地可行性。"
            "若提交材料缺少 Demo 运行说明、依赖安装方式、数据来源说明或人工复核边界，需要标记为高优先级补充项。\n"
            "常见问题包括：是否允许使用开源组件、是否需要公开完整数据、是否必须提供在线部署地址、"
            "以及模型回答是否需要引用来源。推荐做法是优先使用开源组件完成可运行闭环，敏感资料只展示授权片段。"
        ),
    },
    "official_general_course": {
        "id": "official_general_course",
        "name": "通识课 AI 助教知识样例",
        "type": "official",
        "description": "覆盖课程资料问答、复习提纲、练习题和资料范围提示的演示知识库。",
        "content": (
            "通识课 AI 助教知识样例\n"
            "课程资料通常包括课程大纲、讲义、阅读材料、作业要求、考试范围和教师答疑记录。"
            "AI 助教回答课程问题时，应优先引用课程资料，不应把课程资料之外的推断包装成确定结论。\n"
            "复习提纲应围绕核心概念、关键案例、重要阅读材料和常见误区组织。练习题可以包含概念解释题、"
            "材料分析题、对比题和开放讨论题，并给出参考答案或评分要点。\n"
            "当学生提问超出课程范围，或知识库没有对应资料时，系统应提示证据不足，并建议学生补充章节、"
            "讲义页码、教师说明或授权阅读材料。教师侧看板应关注高频问题、薄弱知识点、未命中问题和资料更新建议。"
        ),
    },
}


class FrontChatRequest(BaseModel):
    task_id: str
    message: str
    knowledge_ids: list[str] = Field(default_factory=list)
    agent_id: str | None = None


class SaveMessageRequest(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] | None = None


class LlmApiConfigRequest(BaseModel):
    name: str = "LLM API"
    model: str
    base_url: str
    api_key: str | None = None
    enabled: bool = True
    sort_order: int = 100


def _resolve_project_id(project_id: str | None = None) -> str:
    if project_id and project_id != "default":
        return database.ensure_project(project_id)
    projects = database.list_projects()
    if projects:
        return projects[0]["id"]
    return database.ensure_project(None, "默认项目")


def _conversation_row(task_id: str) -> dict[str, Any] | None:
    database.init_db()
    with database.connect() as conn:
        row = conn.execute(
            """
            SELECT id, project_id, title, created_at, updated_at
            FROM conversations
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()
    return dict(row) if row else None


def _format_message(row: dict[str, Any]) -> dict[str, Any]:
    role = "agent" if row["role"] in {"assistant", "agent"} else "user"
    return {
        "role": role,
        "content": row["content"],
        "timestamp": row["created_at"],
        "metadata": row.get("metadata") or {},
    }


def _history_item(conversation: dict[str, Any]) -> dict[str, Any]:
    messages = database.list_conversation_messages(conversation["id"], limit=10000)
    return {
        "task_id": conversation["id"],
        "title": conversation["title"],
        "created_at": conversation["created_at"],
        "message_count": len(messages),
        "project_id": conversation["project_id"],
    }


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/health")
def frontend_health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/agents")
def frontend_agents() -> list[dict[str, Any]]:
    return list_agent_specs()


@router.get("/llm/health")
def frontend_llm_health() -> dict[str, Any]:
    status = model_status()
    if not status.get("llm_available"):
        return {**status, "status": "fallback"}
    try:
        reply = call_llm("你只返回 ok", "请返回 ok")
    except Exception as exc:
        return {**status, "status": "error", "error": str(exc)}
    return {**status, "status": "ok", "reply": reply.strip()[:20]}


@router.get("/runtime/status")
def frontend_runtime_status() -> dict[str, Any]:
    return {
        "rag": embedding_runtime_status(),
    }


@router.get("/llm/configs")
def frontend_llm_configs() -> list[dict[str, Any]]:
    return database.list_llm_api_configs()


@router.post("/llm/configs")
def frontend_create_llm_config(body: LlmApiConfigRequest) -> dict[str, Any]:
    try:
        config_id = database.create_llm_api_config(body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    item = database.get_llm_api_config(config_id)
    return {"success": True, "config": item}


@router.put("/llm/configs/{config_id}")
def frontend_update_llm_config(config_id: str, body: LlmApiConfigRequest) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)
    if not body.api_key:
        payload.pop("api_key", None)
    try:
        database.update_llm_api_config(config_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="API 配置不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "config": database.get_llm_api_config(config_id)}


@router.delete("/llm/configs/{config_id}")
def frontend_delete_llm_config(config_id: str) -> dict[str, bool]:
    database.delete_llm_api_config(config_id)
    return {"success": True}


@router.get("/projects")
def frontend_projects() -> list[dict[str, Any]]:
    project_id = _resolve_project_id("default")
    projects = database.list_projects()
    if not any(item["id"] == project_id for item in projects):
        projects = database.list_projects()
    return [
        {"id": item["id"], "name": item["name"], "created_at": item["created_at"]}
        for item in projects
    ]


@router.post("/projects")
def frontend_create_project(name: str = Query(default="新项目")) -> dict[str, Any]:
    project_id = database.create_project(name)
    item = next(project for project in database.list_projects() if project["id"] == project_id)
    return {"id": item["id"], "name": item["name"], "created_at": item["created_at"]}


@router.put("/projects/{project_id}/rename")
def frontend_rename_project(project_id: str, name: str = Query(...)) -> dict[str, bool]:
    if not any(item["id"] == project_id for item in database.list_projects()):
        raise HTTPException(status_code=404, detail="项目不存在")
    database.update_project(project_id, name)
    return {"success": True}


@router.post("/task/new")
def frontend_create_task(project_id: str = Query(default="default")) -> dict[str, Any]:
    resolved_project_id = _resolve_project_id(project_id)
    task_id = database.create_conversation(resolved_project_id, "新任务")
    row = _conversation_row(task_id)
    return {"task_id": task_id, "created_at": row["created_at"] if row else "", "project_id": resolved_project_id}


@router.get("/history")
def frontend_history(project_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    resolved_project_id = _resolve_project_id(project_id)
    return [_history_item(item) for item in database.list_conversations(resolved_project_id)]


@router.get("/history/{task_id}")
def frontend_history_detail(task_id: str) -> dict[str, Any]:
    row = _conversation_row(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    messages = [_format_message(item) for item in database.list_conversation_messages(task_id, limit=10000)]
    return {
        "task_id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"],
        "messages": messages,
    }


@router.delete("/history/{task_id}")
def frontend_delete_history(task_id: str) -> dict[str, bool]:
    if not _conversation_row(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    database.delete_conversation(task_id)
    return {"success": True}


@router.put("/history/{task_id}/rename")
def frontend_rename_history(task_id: str, name: str = Query(...)) -> dict[str, bool]:
    row = _conversation_row(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    database.update_conversation_title(task_id, name)
    return {"success": True}


@router.post("/history/{task_id}/message")
def frontend_save_message(task_id: str, body: SaveMessageRequest) -> dict[str, bool]:
    if not _conversation_row(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    role = "assistant" if body.role == "agent" else body.role
    messages = database.list_conversation_messages(task_id, limit=10000)
    if messages:
        last = messages[-1]
        if last["role"] == role and last["content"] == body.content:
            return {"success": True}
    database.add_conversation_message(task_id, role, body.content, body.metadata or {})
    return {"success": True}


@router.post("/chat/stream")
def frontend_chat_stream(request: FrontChatRequest) -> StreamingResponse:
    row = _conversation_row(request.task_id)
    if not row:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    if row["title"] in {"新任务", "新对话", "默认对话", "未命名任务"}:
        database.update_conversation_title(request.task_id, request.message.strip()[:30])

    def event_stream():
        try:
            for event in chat.stream_chat(
                row["project_id"],
                request.task_id,
                request.message,
                knowledge_ids=list(request.knowledge_ids or []),
                agent_id=request.agent_id,
            ):
                yield _sse(event)
        except Exception as exc:
            yield _sse({
                "type": "text",
                "content": f"接口处理失败：{exc}。我没有改动当前项目数据，请稍后重试或换一种问法。",
            })
            yield _sse({
                "type": "agent_state",
                "item": {
                    "agent_id": request.agent_id or "",
                    "agent_name": "",
                    "runtime_backend": "agentscope-compatible-fallback",
                    "confidence": "low",
                    "evidence_notes": ["本轮请求没有完成，需要检查后端日志或重试。"],
                    "follow_up_questions": [],
                    "retrieval_mode": "failed",
                    "retrieval_backend": "",
                    "gpu_mode": "",
                    "semantic_error": str(exc),
                },
            })
            yield _sse({"type": "done"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _ensure_official_knowledge_indexed() -> None:
    for item in _official_knowledge.values():
        kb_id = item["id"]
        if not database.get_knowledge_base(kb_id):
            database.create_knowledge_base(
                name=item["name"],
                description=item["description"],
                kb_type="official",
                file_type="txt",
                index_path=str(kb_store(kb_id).directory),
                knowledge_id=kb_id,
            )
        result = index_text(kb_id, f"{item['name']}.txt", item["content"])
        database.update_knowledge_base_stats(
            kb_id,
            file_count=max(result.files_indexed, 1),
            chunk_count=result.chunks_total,
            embedding_backend=result.embedding_backend,
            index_path=str(kb_store(kb_id).directory),
            name=item["name"],
            description=item["description"],
        )


@router.get("/knowledge/official")
def frontend_official_knowledge() -> list[dict[str, str]]:
    _ensure_official_knowledge_indexed()
    return [
        {key: item[key] for key in ("id", "name", "type", "description")}
        for item in _official_knowledge.values()
    ]


@router.get("/knowledge/personal")
def frontend_personal_knowledge() -> list[dict[str, Any]]:
    items = database.list_knowledge_bases("personal")
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "type": item["type"],
            "description": item["description"],
            "created_at": item["created_at"],
            "file_type": item.get("file_type", "mixed"),
            "file_count": item.get("file_count", 0),
            "chunk_count": item.get("chunk_count", 0),
            "embedding_backend": item.get("embedding_backend", ""),
        }
        for item in items
    ]


@router.post("/knowledge/upload")
async def frontend_upload_knowledge(request: Request) -> dict[str, Any]:
    form = await request.form()
    name = str(form.get("name") or "").strip() or "未命名知识库"
    description = str(form.get("description") or "用户上传的知识库").strip()
    content = str(form.get("content") or "").strip()

    files_payload: list[tuple[str, bytes]] = []
    seen_files: set[str] = set()
    for key in ("files", "file"):
        for raw in form.getlist(key):
            if hasattr(raw, "filename") and hasattr(raw, "read"):
                filename = (raw.filename or "").strip()
                if not filename or filename in seen_files:
                    continue
                data = await raw.read()
                if not data:
                    continue
                files_payload.append((filename, data))
                seen_files.add(filename)

    if not files_payload and not content:
        raise HTTPException(status_code=400, detail="知识库内容不能为空")

    if content and not files_payload:
        files_payload.append(("用户输入文本.txt", content.encode("utf-8")))

    knowledge_id = database.create_knowledge_base(
        name=name,
        description=description,
        kb_type="personal",
        file_type=_detect_file_type(files_payload),
    )
    store = kb_store(knowledge_id)
    database.update_knowledge_base_stats(knowledge_id, index_path=str(store.directory))

    try:
        result = ingest_uploaded_bytes(knowledge_id, files_payload)
    except Exception as exc:
        store.destroy()
        database.delete_knowledge_base(knowledge_id)
        raise HTTPException(status_code=500, detail=f"索引失败：{exc}") from exc

    database.update_knowledge_base_stats(
        knowledge_id,
        file_count=result.files_indexed,
        chunk_count=result.chunks_total,
        embedding_backend=result.embedding_backend,
    )

    return {
        "id": knowledge_id,
        "name": name,
        "files_indexed": result.files_indexed,
        "files_skipped": result.files_skipped,
        "chunks_added": result.chunks_added,
        "chunks_total": result.chunks_total,
        "embedding_backend": result.embedding_backend,
        "rag_backend": result.backend,
        "rag_architecture": result.architecture,
        "content_types": list(result.content_types),
        "raganything_available": result.raganything_available,
        "errors": result.errors,
    }


@router.delete("/knowledge/{knowledge_id}")
def frontend_delete_knowledge(knowledge_id: str) -> dict[str, bool]:
    try:
        kb_store(knowledge_id).destroy()
    except Exception:
        pass
    database.delete_knowledge_base(knowledge_id)
    return {"success": True}


def _detect_file_type(files: list[tuple[str, bytes]]) -> str:
    if not files:
        return "mixed"
    suffixes = {item[0].rsplit(".", 1)[-1].lower() if "." in item[0] else "txt" for item in files}
    if len(suffixes) == 1:
        return next(iter(suffixes))
    return "mixed"


def _project_name(project_id: str) -> str:
    project = next((item for item in database.list_projects() if item["id"] == project_id), None)
    return project["name"] if project else "当前项目"


def _normalize_text_item(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("description", "condition", "detail", "reason", "name"):
            if value.get(key):
                return str(value[key]).strip()
    return str(value or "").strip()


def _unique_text(items: list[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = item.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _collect_metadata(messages: list[dict[str, Any]], key: str) -> list[Any]:
    collected: list[Any] = []
    for message in messages:
        metadata = message.get("metadata") or {}
        value = metadata.get(key)
        if isinstance(value, list):
            collected.extend(value)
    return collected


def _summary_from_messages(
    messages: list[dict[str, Any]],
    project_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    user_messages = [item["content"] for item in messages if item["role"] == "user"]
    summary_title = title or (user_messages[-1][:30] if user_messages else "暂无对话")
    _ = project_id
    assistant_messages = [item for item in messages if item["role"] in {"assistant", "agent"}]
    evidence_notes = _unique_text([_normalize_text_item(item) for item in _collect_metadata(messages, "evidence_notes")])
    follow_up_questions = _unique_text([_normalize_text_item(item) for item in _collect_metadata(messages, "follow_up_questions")])
    rag_sources = _collect_metadata(messages, "rag_chunks")
    agents = _unique_text([
        str((message.get("metadata") or {}).get("agent_name") or "").strip()
        for message in assistant_messages
        if (message.get("metadata") or {}).get("agent_name")
    ])
    source_preview = [
        {
            "source_file": str(item.get("source_file") or ""),
            "kb_id": str(item.get("kb_id") or ""),
            "snippet": str(item.get("snippet") or ""),
        }
        for item in rag_sources
        if isinstance(item, dict)
    ][:8]

    return {
        "title": summary_title,
        "overview": f"共沉淀 {len(user_messages)} 个用户问题，{len(assistant_messages)} 条 Agent 回复，{len(rag_sources)} 条引用片段。",
        "agents": agents,
        "evidence_notes": evidence_notes,
        "follow_up_questions": follow_up_questions,
        "rag_sources": source_preview,
    }


def _normalize_priority_items(items: list[Any]) -> list[str]:
    return [_normalize_text_item(item) for item in items if _normalize_text_item(item)]


@router.post("/history/{task_id}/summarize")
def frontend_summarize_task(task_id: str) -> dict[str, Any]:
    row = _conversation_row(task_id)
    detail = frontend_history_detail(task_id)
    return _summary_from_messages(detail["messages"], row["project_id"] if row else None, detail["title"])


@router.post("/projects/{project_id}/summarize")
def frontend_summarize_project(project_id: str) -> dict[str, Any]:
    resolved_project_id = _resolve_project_id(project_id)
    messages: list[dict[str, Any]] = []
    for item in database.list_conversations(resolved_project_id):
        messages.extend(_format_message(row) for row in database.list_conversation_messages(item["id"], limit=10000))
    return _summary_from_messages(messages, resolved_project_id, _project_name(resolved_project_id))
