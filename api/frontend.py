from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import chat, database
from agent.rag import index_uploaded_bytes, kb_store


router = APIRouter(prefix="/api", tags=["frontend"])

_official_knowledge: dict[str, dict[str, str]] = {
    "official_tmall618": {
        "id": "official_tmall618",
        "name": "天猫618大促选品规则",
        "type": "official",
        "description": "天猫618大促活动选品标准规则模板",
        "content": (
            "天猫618大促选品规则\n"
            "1. 参与商品需满足近30天销量、好评率、库存等基础门槛。\n"
            "2. 活动价不得高于历史最低价，折扣力度需满足平台要求。\n"
            "3. 同品类报名 SKU 数量需要控制，已参加互斥活动的商品需剔除。"
        ),
    },
    "official_jd1111": {
        "id": "official_jd1111",
        "name": "京东双11活动规则",
        "type": "official",
        "description": "京东双11活动通用规则模板",
        "content": (
            "京东双11活动规则\n"
            "1. 商品需满足销量、评价、价格保护和库存要求。\n"
            "2. 报名后需关注发货时效、库存锁定和活动互斥。"
        ),
    },
}


class FrontChatRequest(BaseModel):
    task_id: str
    message: str
    knowledge_ids: list[str] = Field(default_factory=list)


class SaveMessageRequest(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] | None = None


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


def _rate_for_frontend(value: Any) -> float:
    number = float(value or 0)
    return number / 100 if number > 1 else number


def _product_for_frontend(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "sku_id": item["sku_id"],
        "product_name": item["product_name"],
        "brand": item["brand"],
        "category_l1": item["category_l1"],
        "category_l2": item["category_l2"],
        "pricing_model": item["pricing_model"],
        "weight_g": item.get("weight_g"),
        "purity": item.get("purity") or None,
        "gem_carat": item.get("gem_carat"),
        "gem_color": item.get("gem_color") or None,
        "gem_clarity": item.get("gem_clarity") or None,
        "gem_cut": item.get("gem_cut") or None,
        "tag_price_rmb": float(item.get("tag_price_rmb") or 0),
        "list_price_rmb": item.get("list_price_rmb"),
        "last_30d_min_price": item.get("last_30d_min_price"),
        "last_90d_min_price": item.get("last_90d_min_price"),
        "last_365d_min_price": item.get("last_365d_min_price"),
        "stock": int(item.get("stock") or 0),
        "last_90d_sales": int(item.get("last_90d_sales") or 0),
        "review_rate": _rate_for_frontend(item.get("review_rate")),
        "return_rate": _rate_for_frontend(item.get("return_rate")),
        "new_product": bool(item.get("new_product")),
        "certificate_ids": item.get("certificate_ids") or [],
        "factory_id": item.get("factory_id") or "",
        "lead_time_days": int(item.get("lead_time_days") or 0),
        "active_campaigns": item.get("active_campaigns") or [],
    }


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/health")
def frontend_health() -> dict[str, str]:
    return {"status": "ok"}


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
    with database.connect() as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name.strip()[:120] or "未命名任务", task_id),
        )
    database.touch_project(row["project_id"])
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

    def event_stream():
        result = chat.handle_chat(
            row["project_id"],
            request.task_id,
            request.message,
            knowledge_ids=list(request.knowledge_ids or []),
        )
        reply = result.get("reply", "")
        if reply:
            yield _sse({"type": "text", "content": reply})
        actions = result.get("actions") or []
        if actions:
            yield _sse({
                "type": "checklist",
                "items": [
                    {
                        "condition": item.get("product_name") or item.get("type") or "待处理动作",
                        "priority": "medium",
                        "detail": item.get("notes") or item.get("status") or "",
                    }
                    for item in actions
                ],
            })
        yield _sse({"type": "done"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/products")
def frontend_products(
    category_l1: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict[str, Any]:
    products = [_product_for_frontend(item) for item in database.list_catalog_products(search or "", limit=1000)]
    if category_l1:
        products = [item for item in products if item["category_l1"] == category_l1]
    all_products = [_product_for_frontend(item) for item in database.list_catalog_products(limit=1000)]
    categories = sorted({item["category_l1"] for item in all_products if item["category_l1"]})
    return {"products": products, "categories": categories, "total": len(products)}


@router.post("/products")
def frontend_add_product(product: dict[str, Any]) -> dict[str, Any]:
    product_id = database.create_catalog_product(product)
    item = database.get_catalog_product(product_id)
    return {"success": True, "product": _product_for_frontend(item)}


@router.delete("/products/{sku_id}")
def frontend_delete_product(sku_id: str) -> dict[str, bool]:
    matched = next(
        (item for item in database.list_catalog_products(limit=1000) if item["sku_id"] == sku_id),
        None,
    )
    if not matched:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    database.delete_catalog_product(matched["id"])
    return {"success": True}


@router.get("/knowledge/official")
def frontend_official_knowledge() -> list[dict[str, str]]:
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
        result = index_uploaded_bytes(knowledge_id, files_payload)
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


def _summary_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    user_messages = [item["content"] for item in messages if item["role"] == "user"]
    title = user_messages[-1][:30] if user_messages else "暂无对话"
    return {
        "title": title,
        "rule_points": ["已基于当前对话沉淀规则要点"] if messages else [],
        "recommendations": [{"item": "继续补充活动规则与商品约束", "reason": "信息越完整，执行清单越可靠"}] if messages else [],
        "checks": [{"name": "对话记录", "status": "已保存"}] if messages else [],
        "risks": [],
    }


@router.post("/history/{task_id}/summarize")
def frontend_summarize_task(task_id: str) -> dict[str, Any]:
    detail = frontend_history_detail(task_id)
    return _summary_from_messages(detail["messages"])


@router.post("/projects/{project_id}/summarize")
def frontend_summarize_project(project_id: str) -> dict[str, Any]:
    resolved_project_id = _resolve_project_id(project_id)
    messages: list[dict[str, Any]] = []
    for item in database.list_conversations(resolved_project_id):
        messages.extend(_format_message(row) for row in database.list_conversation_messages(item["id"], limit=10000))
    return _summary_from_messages(messages)
