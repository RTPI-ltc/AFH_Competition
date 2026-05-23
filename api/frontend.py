from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent import chat, database
from agent.llm import call_llm, model_status
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
            result = chat.handle_chat(
                row["project_id"],
                request.task_id,
                request.message,
                knowledge_ids=list(request.knowledge_ids or []),
            )
        except Exception as exc:
            yield _sse({
                "type": "text",
                "content": f"接口处理失败：{exc}。我没有改动当前项目数据，请稍后重试或换一种问法。",
            })
            yield _sse({
                "type": "risks",
                "items": [{"description": "本轮请求没有完成，需人工确认是否重试。", "severity": "medium"}],
            })
            yield _sse({"type": "done"})
            return
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
        for event_type, key in (
            ("recommendations", "recommendations"),
            ("priority_analysis", "priority_analysis"),
            ("checklist", "checklist"),
            ("risks", "risks"),
            ("clarification", "needs_clarification"),
        ):
            items = result.get(key) or []
            if items:
                yield _sse({"type": event_type, "items": items})
        confirmation = result.get("confirmation") or {}
        if confirmation.get("required") or confirmation.get("status"):
            yield _sse({"type": "confirmation", "item": confirmation})
        rag_chunks = result.get("rag_chunks") or []
        if rag_chunks:
            yield _sse({"type": "rag_chunks", "items": rag_chunks})
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


def _project_name(project_id: str) -> str:
    project = next((item for item in database.list_projects() if item["id"] == project_id), None)
    return project["name"] if project else "当前项目"


def _catalog_by_name() -> dict[str, dict[str, Any]]:
    products = database.list_catalog_products(limit=1000)
    return {item["product_name"]: item for item in products}


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


def _recommendation_reason_map(messages: list[dict[str, Any]]) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for item in _collect_metadata(messages, "recommendations"):
        if not isinstance(item, dict):
            continue
        reason = str(item.get("reason") or "").strip()
        if not reason:
            continue
        for key in (item.get("product_name"), item.get("sku_id")):
            if key:
                reasons[str(key)] = reason
    return reasons


def _product_reason(product: dict[str, Any] | None, fallback: str = "") -> str:
    if fallback:
        return fallback
    if not product:
        return "已进入当前项目上架清单，建议按清单状态继续确认。"
    parts = [
        f"近90天销量 {int(product.get('last_90d_sales') or 0)}",
        f"库存 {int(product.get('stock') or 0)}",
        f"好评率 {float(product.get('review_rate') or 0):.1f}%",
        f"退货率 {float(product.get('return_rate') or 0):.1f}%",
    ]
    if product.get("new_product"):
        parts.append("新品可承接活动流量")
    return "，".join(parts)


def _attention_for_product(product: dict[str, Any] | None) -> list[str]:
    if not product:
        return ["清单商品未匹配到商品库详情，需人工核对 SKU、价格、库存和资质。"]
    notes: list[str] = []
    campaigns = product.get("active_campaigns") or []
    if campaigns:
        notes.append(f"{product['product_name']} 已有关联活动 {', '.join(campaigns)}，需确认活动互斥规则。")
    list_price = float(product.get("list_price_rmb") or 0)
    last_90d_min_price = float(product.get("last_90d_min_price") or 0)
    if list_price and last_90d_min_price and list_price > last_90d_min_price:
        notes.append(f"{product['product_name']} 当前价高于近90天最低价，报名价需重新确认价格保护。")
    if int(product.get("stock") or 0) < 100:
        notes.append(f"{product['product_name']} 库存偏低，确认后需锁库存或降低活动预期。")
    if float(product.get("return_rate") or 0) >= 3:
        notes.append(f"{product['product_name']} 退货率偏高，需复核详情页描述和售后风险。")
    if not product.get("certificate_ids"):
        notes.append(f"{product['product_name']} 缺少证书编号，需补齐质检或材质证明。")
    return notes


def _summary_from_messages(
    messages: list[dict[str, Any]],
    project_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    user_messages = [item["content"] for item in messages if item["role"] == "user"]
    summary_title = title or (user_messages[-1][:30] if user_messages else "暂无对话")
    listing_items = database.list_listing_items(project_id) if project_id else []
    catalog = _catalog_by_name()
    reason_map = _recommendation_reason_map(messages)
    recommendations_from_messages = [
        item for item in _collect_metadata(messages, "recommendations")
        if isinstance(item, dict)
    ]

    final_selection: list[dict[str, Any]] = []
    for item in listing_items:
        product = catalog.get(item["product_name"])
        reason = _product_reason(
            product,
            item.get("notes") or reason_map.get(item["product_name"]) or (reason_map.get(product["sku_id"]) if product else ""),
        )
        final_selection.append({
            "sku_id": product.get("sku_id", "") if product else "",
            "product_name": item["product_name"],
            "status": item.get("status", ""),
            "category": " / ".join(part for part in [product.get("category_l1"), product.get("category_l2")] if part) if product else "",
            "reason": reason,
            "key_metrics": {
                "stock": product.get("stock") if product else None,
                "last_90d_sales": product.get("last_90d_sales") if product else None,
                "review_rate": product.get("review_rate") if product else None,
                "return_rate": product.get("return_rate") if product else None,
            },
        })

    if not final_selection:
        for item in recommendations_from_messages[:5]:
            final_selection.append({
                "sku_id": item.get("sku_id", ""),
                "product_name": item.get("product_name") or item.get("item") or "未命名推荐",
                "status": "待确认",
                "category": "",
                "reason": item.get("reason") or "来自对话推荐，尚未确认进入上架清单。",
                "key_metrics": {},
            })

    attention_items = []
    for item in final_selection:
        product = catalog.get(item["product_name"])
        attention_items.extend(_attention_for_product(product))
    attention_items.extend(_normalize_text_item(item) for item in _collect_metadata(messages, "needs_clarification"))
    attention_items.extend(_normalize_text_item(item) for item in _collect_metadata(messages, "risks"))

    checks = [
        {"name": _normalize_text_item(item), "status": "待确认"}
        for item in _collect_metadata(messages, "checklist")
        if _normalize_text_item(item)
    ]
    if listing_items:
        checks.insert(0, {"name": "确认后的上架清单", "status": f"已记录 {len(listing_items)} 个商品"})
    if not checks and messages:
        checks.append({"name": "对话记录", "status": "已保存"})

    recommendations = [
        {"item": item["product_name"], "reason": item["reason"]}
        for item in final_selection
    ]
    rule_points = _unique_text([
        *_normalize_priority_items(_collect_metadata(messages, "priority_analysis")),
        "最终选品需同时复核库存、历史最低价、活动互斥和资质证书。",
    ] if final_selection else [_normalize_text_item(item) for item in _collect_metadata(messages, "priority_analysis")])
    risks = _unique_text([_normalize_text_item(item) for item in _collect_metadata(messages, "risks")])
    return {
        "title": summary_title,
        "overview": (
            f"已形成 {len(final_selection)} 个最终选品，确认清单中有 {len(listing_items)} 个商品。"
            if final_selection else "暂无可汇总的最终选品。"
        ),
        "rule_points": rule_points,
        "recommendations": recommendations,
        "final_selection": final_selection,
        "selection_reasons": [item["reason"] for item in final_selection],
        "attention_items": _unique_text(attention_items),
        "confirmed_listing": [
            {
                "product_name": item["product_name"],
                "status": item.get("status", ""),
                "notes": item.get("notes", ""),
                "sku_id": catalog.get(item["product_name"], {}).get("sku_id", ""),
            }
            for item in listing_items
        ],
        "checks": checks[:10],
        "risks": risks,
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
