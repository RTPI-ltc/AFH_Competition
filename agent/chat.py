from __future__ import annotations

import json
import os
import re
from typing import Any

from agent import database
from agent.llm import call_llm, llm_available, parse_llm_json
from agent.rag import append_context_to_system, retrieve_safe
from agent.risk_control import apply_risk_audit, audit_chat_result


CHAT_SYSTEM = """你是珠宝电商运营执行助手，所有 chatbox 回复都必须由模型生成。

你会收到当前项目、当前上架清单、商品数据库摘要（catalog_products）、最近对话和用户消息。请基于这些真实数据回答，不要要求用户重新提供商品库里已经有的信息。

输出尽量使用严格 JSON：
{
  "reply": "给用户看的中文回答",
  "recommendations": [
    {
      "sku_id": "必须来自 catalog_products 列表的 sku_id",
      "product_name": "商品名称",
      "priority": "high|medium|low",
      "score": 0-100,
      "reason": "推荐原因（结合销量/库存/价格/活动冲突）"
    }
  ],
  "priority_analysis": ["优先级分析要点"],
  "checklist": [
    {"condition": "检查事项", "priority": "high|medium|low", "detail": "执行说明"}
  ],
  "risks": [
    {"description": "风险说明", "severity": "high|medium"}
  ],
  "needs_clarification": ["需要人工确认的信息"],
  "confirmation": {
    "required": true,
    "question": "是否确认按这个方案推进？",
    "confirm_label": "确认方案",
    "revise_label": "继续调整"
  },
  "actions": [
    {
      "type": "add_listing_item|remove_listing_item|none",
      "product_name": "商品名称（必须与 catalog_products 中的 product_name 完全一致）",
      "status": "待确认|拟上架|已上架|需补充信息|不建议上架",
      "notes": "原因或备注",
      "details": {}
    }
  ]
}

严格要求：
1. recommendations 与 actions 的 sku_id / product_name 必须严格来自 catalog_products，不得编造、缩写或重命名。
2. 计重商品 (pricing_model="weight") 的成交价按 weight_g × 当前金价计算，list_price_rmb 可能为 0，请用 tag_price_rmb 作为参考价。
3. 价格保护：若 list_price_rmb 高于 last_30d_min_price 或 last_90d_min_price，需在 risks 提示。
4. 活动互斥：active_campaigns 非空说明该 SKU 已参加其他活动，新报名前要在 needs_clarification 中确认是否冲突。
5. 如果用户询问的商品/品类不在 catalog_products 列表，必须在 needs_clarification 写明"未在当前商品库摘要中找到 XX，请扩大检索范围或上传补充数据"，不得伪造 SKU。
6. 用户问推荐/选品/上架方案时，最多推荐 3 个 SKU，reply 控制在 300 字以内。
7. 只有用户明确要求加入、移除、确认方案时，才返回 add_listing_item 或 remove_listing_item actions。
8. 信息不足时标注 needs_clarification，不要编造已经确认。
"""


CATALOG_CONTEXT_LIMIT = 12
HISTORY_CONTEXT_LIMIT = 6
TEXT_FIELD_LIMIT = 500
CONFIRM_PLAN_TRIGGER = "确认执行上一个上架方案"
BUSINESS_KEYWORDS = (
    "推荐", "选品", "上架", "商品", "sku", "SKU",
    "清单", "方案", "风险", "检查", "确认", "移除",
    "加入", "添加", "报名", "活动",
    "价格", "定价", "折扣", "毛利", "成本",
    "库存", "销量", "好评", "退货",
    "品类", "黄金", "钻石", "铂金", "银饰", "珍珠", "玉石", "翡翠", "镶嵌",
    "克", "克重", "成色", "纯度", "证书",
    "品牌", "工厂",
)


SKU_PATTERN = re.compile(r"SKU\d{4,8}", re.IGNORECASE)
CATEGORY_KEYWORDS = (
    "黄金", "钻石", "铂金", "银饰", "925银", "珍珠", "玉石", "翡翠", "镶嵌",
    "古法金", "足金", "千足金", "万足金", "硬足金", "5G黄金", "K金",
    "求婚钻戒", "钻戒", "耳钉", "项链", "手镯", "吊坠", "手链",
)
BRAND_KEYWORDS = (
    "云璟珠宝", "星禾金作", "禾光珠宝", "珑曜金业", "璟澜珠宝",
    "星诺婚饰", "曜石切工", "翠岚坊", "月汐珍珠", "铂映工坊", "银澈饰品",
)


def _context_limit(env_name: str, default: int, lower: int, upper: int) -> int:
    try:
        value = int(os.getenv(env_name, str(default)))
    except ValueError:
        return default
    return max(lower, min(upper, value))


def _clip_text(value: Any, limit: int = TEXT_FIELD_LIMIT) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[:limit]}..."


def _compact_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": project.get("id"),
        "name": project.get("name"),
        "description": _clip_text(project.get("description"), 240),
    }


def _compact_listing_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "product_name": item.get("product_name"),
        "status": item.get("status"),
        "notes": _clip_text(item.get("notes"), 160),
    }


def _compact_history_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    compact: dict[str, Any] = {
        "role": item.get("role"),
        "content": _clip_text(item.get("content")),
    }
    useful_metadata = {
        key: metadata.get(key)
        for key in ("recommendations", "needs_clarification", "confirmation")
        if metadata.get(key)
    }
    if useful_metadata:
        compact["metadata"] = useful_metadata
    return compact


def _compact_catalog_product(item: dict[str, Any]) -> dict[str, Any]:
    gem: dict[str, Any] = {}
    for src, dst in (("gem_carat", "carat"), ("gem_color", "color"), ("gem_clarity", "clarity"), ("gem_cut", "cut")):
        value = item.get(src)
        if value not in (None, "", 0):
            gem[dst] = value
    payload: dict[str, Any] = {
        "sku_id": item.get("sku_id"),
        "product_name": item.get("product_name"),
        "brand": item.get("brand"),
        "category": " / ".join(part for part in [item.get("category_l1"), item.get("category_l2")] if part),
        "pricing_model": item.get("pricing_model"),
        "weight_g": item.get("weight_g"),
        "purity": item.get("purity") or None,
        "tag_price_rmb": item.get("tag_price_rmb"),
        "list_price_rmb": item.get("list_price_rmb"),
        "last_30d_min_price": item.get("last_30d_min_price"),
        "last_90d_min_price": item.get("last_90d_min_price"),
        "last_365d_min_price": item.get("last_365d_min_price"),
        "stock": item.get("stock"),
        "last_90d_sales": item.get("last_90d_sales"),
        "review_rate": item.get("review_rate"),
        "return_rate": item.get("return_rate"),
        "new_product": bool(item.get("new_product")),
        "active_campaigns": item.get("active_campaigns") or [],
        "certificate_ids": item.get("certificate_ids") or [],
        "lead_time_days": item.get("lead_time_days"),
        "factory_id": item.get("factory_id") or None,
    }
    if gem:
        payload["gem"] = gem
    return payload


def _product_context_score(item: dict[str, Any]) -> float:
    review_rate = float(item.get("review_rate") or 0)
    return_rate = float(item.get("return_rate") or 0)
    return (
        float(item.get("last_90d_sales") or 0) * 0.45
        + float(item.get("stock") or 0) * 0.03
        + review_rate * 2
        - return_rate * 3
        + (15 if item.get("new_product") else 0)
    )


def _extract_query_entities(message: str) -> dict[str, list[str]]:
    """Pick out SKU codes, categories, brands from the user message so we can
    bias catalog candidates toward what the user is actually asking about."""
    entities: dict[str, list[str]] = {"skus": [], "categories": [], "brands": []}
    if not message:
        return entities
    for raw in SKU_PATTERN.findall(message):
        normalized = raw.upper()
        if normalized not in entities["skus"]:
            entities["skus"].append(normalized)
    lower = message
    for keyword in CATEGORY_KEYWORDS:
        if keyword in lower and keyword not in entities["categories"]:
            entities["categories"].append(keyword)
    for brand in BRAND_KEYWORDS:
        if brand in lower and brand not in entities["brands"]:
            entities["brands"].append(brand)
    return entities


def _catalog_candidates(message: str, limit: int) -> list[dict[str, Any]]:
    """Return up to `limit` compact products. Prioritises matches against
    entities extracted from `message`; fills remaining slots with popularity."""
    keyed: dict[str, dict[str, Any]] = {}

    def absorb(items: list[dict[str, Any]]) -> None:
        for item in items:
            sku = str(item.get("sku_id") or "").upper()
            if not sku or sku in keyed:
                continue
            keyed[sku] = item

    entities = _extract_query_entities(message)
    # Targeted queries first — SKU lookups, brand/category contains.
    for query in entities["skus"]:
        absorb(database.list_catalog_products(query, limit=4))
        if len(keyed) >= limit:
            break
    if len(keyed) < limit:
        for query in entities["brands"]:
            absorb(database.list_catalog_products(query, limit=6))
            if len(keyed) >= limit:
                break
    if len(keyed) < limit:
        for query in entities["categories"]:
            absorb(database.list_catalog_products(query, limit=6))
            if len(keyed) >= limit:
                break
    # Always reserve some slots for popularity-ranked products so the model
    # sees a healthy backbone even when the targeted queries miss.
    backbone_slots = max(limit - len(keyed), max(limit // 2, 4))
    backbone = database.list_catalog_products("", limit=max(backbone_slots * 4, 40))
    ranked = sorted(backbone, key=_product_context_score, reverse=True)
    absorb(ranked[: backbone_slots * 2])

    selected = list(keyed.values())[:limit]
    return [_compact_catalog_product(item) for item in selected]


def _needs_business_context(message: str) -> bool:
    normalized = message.strip()
    return any(keyword in normalized for keyword in BUSINESS_KEYWORDS)


def _build_user_prompt(
    message: str,
    project: dict[str, Any],
    listing_items: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> str:
    needs_business_context = _needs_business_context(message)
    history_limit = _context_limit("CHAT_HISTORY_CONTEXT_LIMIT", HISTORY_CONTEXT_LIMIT, 2, 12)
    catalog_limit = _context_limit("CHAT_CATALOG_CONTEXT_LIMIT", CATALOG_CONTEXT_LIMIT, 8, 60)
    compact_history = [
        _compact_history_item(item)
        for item in history[-history_limit:]
    ]
    catalog: list[dict[str, Any]] = []
    entities: dict[str, list[str]] = {"skus": [], "categories": [], "brands": []}
    if needs_business_context:
        catalog = _catalog_candidates(message, catalog_limit)
        entities = _extract_query_entities(message)
    listing_context: list[dict[str, Any]] = []
    if needs_business_context:
        listing_context = [_compact_listing_item(item) for item in listing_items]
    return json.dumps(
        {
            "project": _compact_project(project),
            "listing_items": listing_context,
            "catalog_products": catalog,
            "catalog_context": {
                "limit": catalog_limit,
                "returned": len(catalog),
                "included": needs_business_context,
                "matched_entities": entities,
                "note": (
                    "catalog_products 是真实商品库的压缩摘要。"
                    "matched_entities 是从用户消息中提取的 SKU / 品类 / 品牌，已优先用它们筛选 catalog。"
                    "若用户的目标 SKU 不在列表里，说明商品库可能没有这条记录或被检索遗漏，请在 needs_clarification 中说明，不要伪造数据。"
                ),
            },
            "recent_messages": compact_history,
            "user_message": message,
            "instruction": (
                "本轮回复必须由模型完成。不要走本地 fallback。"
                "如果商品库摘要和上架清单为空，说明本轮不是选品/上架任务，请像正常助手一样简短回答，不要输出推荐、检查清单、风险或确认按钮，也不要向用户提及内部字段名。"
                "如果商品库摘要不为空，请最多推荐 3 个 SKU，reply 控制在 300 字以内，分析项保持精简。"
                "请尽量返回符合系统格式的 JSON。"
            ),
        },
        ensure_ascii=False,
    )


def _parse_model_response(raw: str) -> dict[str, Any]:
    try:
        parsed = parse_llm_json(raw)
    except Exception:
        reply_match = re.search(r'"reply"\s*:\s*"(?P<reply>(?:\\.|[^"\\])*)"', raw, re.S)
        if reply_match:
            try:
                reply = json.loads(f'"{reply_match.group("reply")}"')
            except json.JSONDecodeError:
                reply = reply_match.group("reply")
        elif raw.lstrip().startswith("{"):
            reply = "模型返回了结构化内容，但格式不完整，已拦截原始 JSON。请重试或换一种说法。"
        else:
            reply = raw.strip() or "模型返回为空。"
        return {
            "reply": reply,
            "actions": [],
            "recommendations": [],
            "priority_analysis": [],
            "checklist": [],
            "risks": [],
            "needs_clarification": [],
            "confirmation": {"required": False},
        }
    if not isinstance(parsed, dict):
        return {
            "reply": str(parsed),
            "actions": [],
            "recommendations": [],
            "priority_analysis": [],
            "checklist": [],
            "risks": [],
            "needs_clarification": [],
            "confirmation": {"required": False},
        }
    return parsed


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _metadata(
    parsed: dict[str, Any],
    actions: list[dict[str, Any]],
    applied_actions: list[dict[str, Any]],
    rag_chunks: list[dict[str, Any]] | None = None,
    knowledge_ids: list[str] | None = None,
) -> dict[str, Any]:
    confirmation = parsed.get("confirmation") if isinstance(parsed.get("confirmation"), dict) else {"required": False}
    return {
        "event": "chat_reply",
        "actions": actions,
        "applied_actions": applied_actions,
        "recommendations": _list_or_empty(parsed.get("recommendations")),
        "priority_analysis": _list_or_empty(parsed.get("priority_analysis")),
        "checklist": _list_or_empty(parsed.get("checklist")),
        "risks": _list_or_empty(parsed.get("risks")),
        "needs_clarification": _list_or_empty(parsed.get("needs_clarification")),
        "confirmation": confirmation,
        "rag_chunks": rag_chunks or [],
        "knowledge_ids": knowledge_ids or [],
        "risk_control": parsed.get("risk_control") or {},
    }


def _latest_recommendations_from_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in reversed(history):
        if item.get("role") not in {"assistant", "agent"}:
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        recommendations = metadata.get("recommendations")
        if isinstance(recommendations, list) and recommendations:
            return [rec for rec in recommendations if isinstance(rec, dict)]
    return []


def _apply_previous_recommendations(
    project_id: str,
    conversation_id: str,
    history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recommendations = _latest_recommendations_from_history(history)
    if not recommendations:
        return []

    current_names = {
        str(item.get("product_name") or "").strip()
        for item in database.list_listing_items(project_id)
    }
    by_sku, by_name = _catalog_lookup_indices()
    applied: list[dict[str, Any]] = []

    for rec in recommendations:
        product = _match_catalog(rec, by_sku, by_name)
        product_name = str((product or rec).get("product_name") or "").strip()
        if not product_name or product_name in current_names:
            continue
        sku_id = (product or rec).get("sku_id") or ""
        reason = str(rec.get("reason") or rec.get("notes") or "来自上一轮上架方案确认。").strip()
        details = {
            "sku_id": sku_id,
            "source": "confirmed_previous_recommendation",
        }
        if product:
            details.update({
                "brand": product.get("brand") or "",
                "category": " / ".join(
                    part for part in [product.get("category_l1"), product.get("category_l2")] if part
                ),
            })
        item_id = database.add_listing_item(
            project_id,
            product_name,
            details=details,
            status="拟上架",
            notes=reason,
            source_conversation_id=conversation_id,
        )
        current_names.add(product_name)
        applied.append({
            "type": "add_listing_item",
            "item_id": item_id,
            "product_name": product_name,
            "sku_id": sku_id,
        })
    return applied


def _sanitize_non_business_response(parsed: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(parsed)
    for key in ("actions", "recommendations", "priority_analysis", "checklist", "risks", "needs_clarification"):
        cleaned[key] = []
    cleaned["confirmation"] = {"required": False}
    return cleaned


def _catalog_lookup_indices() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return (by_sku, by_name) lookup tables over the full catalog."""
    by_sku: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for product in database.list_catalog_products(limit=2000):
        sku = str(product.get("sku_id") or "").upper()
        name = str(product.get("product_name") or "").strip()
        if sku:
            by_sku[sku] = product
        if name:
            by_name[name] = product
    return by_sku, by_name


def _match_catalog(
    item: dict[str, Any],
    by_sku: dict[str, dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    sku_raw = str(item.get("sku_id") or "").upper().strip()
    if sku_raw and sku_raw in by_sku:
        return by_sku[sku_raw]
    name = str(item.get("product_name") or "").strip()
    if not name:
        return None
    if name in by_name:
        return by_name[name]
    # Lenient fallback: the model may have lightly paraphrased the name.
    candidates = [p for p in by_name.values() if name and (name in p["product_name"] or p["product_name"] in name)]
    if len(candidates) == 1:
        return candidates[0]
    return None


def _enrich_recommendation(rec: dict[str, Any], product: dict[str, Any]) -> dict[str, Any]:
    """Replace whatever the model said with authoritative DB values for the
    parts the user is most likely to act on (sku, price, stock, sales)."""
    enriched = dict(rec)
    enriched["sku_id"] = product.get("sku_id") or rec.get("sku_id")
    enriched["product_name"] = product.get("product_name") or rec.get("product_name")
    enriched["brand"] = product.get("brand")
    enriched["category"] = " / ".join(
        part for part in [product.get("category_l1"), product.get("category_l2")] if part
    )
    enriched["pricing_model"] = product.get("pricing_model")
    enriched["tag_price_rmb"] = product.get("tag_price_rmb")
    enriched["list_price_rmb"] = product.get("list_price_rmb")
    enriched["last_30d_min_price"] = product.get("last_30d_min_price")
    enriched["last_90d_min_price"] = product.get("last_90d_min_price")
    enriched["stock"] = product.get("stock")
    enriched["last_90d_sales"] = product.get("last_90d_sales")
    enriched["review_rate"] = product.get("review_rate")
    enriched["return_rate"] = product.get("return_rate")
    enriched["active_campaigns"] = product.get("active_campaigns") or []
    enriched["validated"] = True
    return enriched


def _validate_and_enrich(parsed: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Drop hallucinated SKUs and enrich valid ones with real DB data.

    Returns (parsed_with_validated_lists, dropped_records). Dropped recs are
    surfaced to the user via needs_clarification so they know something went
    sideways rather than silently disappearing.
    """
    by_sku, by_name = _catalog_lookup_indices()

    raw_recommendations = parsed.get("recommendations") if isinstance(parsed.get("recommendations"), list) else []
    valid_recs: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for rec in raw_recommendations:
        if not isinstance(rec, dict):
            continue
        product = _match_catalog(rec, by_sku, by_name)
        if product is None:
            dropped.append({"kind": "recommendation", "item": rec})
            continue
        valid_recs.append(_enrich_recommendation(rec, product))

    raw_actions = parsed.get("actions") if isinstance(parsed.get("actions"), list) else []
    valid_actions: list[dict[str, Any]] = []
    for action in raw_actions:
        if not isinstance(action, dict):
            continue
        action_type = action.get("type")
        # remove and no-op actions don't require an existing catalog row.
        if action_type not in ("add_listing_item",):
            valid_actions.append(action)
            continue
        product = _match_catalog(action, by_sku, by_name)
        if product is None:
            dropped.append({"kind": "action", "item": action})
            continue
        normalized = dict(action)
        normalized["product_name"] = product["product_name"]
        details = action.get("details") if isinstance(action.get("details"), dict) else {}
        details = dict(details)
        details.setdefault("sku_id", product.get("sku_id"))
        details.setdefault("brand", product.get("brand"))
        details.setdefault("category", " / ".join(
            part for part in [product.get("category_l1"), product.get("category_l2")] if part
        ))
        normalized["details"] = details
        valid_actions.append(normalized)

    if dropped:
        existing = parsed.get("needs_clarification")
        clarifications = list(existing) if isinstance(existing, list) else []
        names = [
            str(d["item"].get("product_name") or d["item"].get("sku_id") or "未知")
            for d in dropped
        ]
        message = (
            f"模型提到了 {len(dropped)} 条不在商品库中的项："
            + "、".join(dict.fromkeys(names))
            + "。已自动从结果中剔除，请确认是否要扩大商品库或上传补充资料。"
        )
        clarifications.insert(0, message)
        parsed["needs_clarification"] = clarifications

    parsed["recommendations"] = valid_recs
    parsed["actions"] = valid_actions
    return parsed, dropped


def _apply_actions(project_id: str, conversation_id: str, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    current_items = database.list_listing_items(project_id)
    for action in actions:
        action_type = action.get("type")
        product_name = str(action.get("product_name") or "").strip()
        if action_type == "add_listing_item" and product_name:
            item_id = database.add_listing_item(
                project_id,
                product_name,
                details=action.get("details") if isinstance(action.get("details"), dict) else {},
                status=str(action.get("status") or "待确认"),
                notes=str(action.get("notes") or ""),
                source_conversation_id=conversation_id,
            )
            applied.append({"type": action_type, "item_id": item_id, "product_name": product_name})
        elif action_type == "remove_listing_item" and product_name:
            matched = next((item for item in current_items if item["product_name"] == product_name), None)
            if matched:
                database.delete_listing_item(matched["id"])
                applied.append({"type": action_type, "item_id": matched["id"], "product_name": product_name})
    return applied


def _build_system_prompt(message: str, knowledge_ids: list[str]) -> tuple[str, list[dict[str, Any]]]:
    if not knowledge_ids:
        return CHAT_SYSTEM, []
    chunks = retrieve_safe(message, knowledge_ids)
    if not chunks:
        return CHAT_SYSTEM, []
    return append_context_to_system(CHAT_SYSTEM, chunks), chunks


def _rag_summary(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        snippet = text[:160] + ("…" if len(text) > 160 else "")
        summary.append({
            "kb_id": chunk.get("kb_id") or "",
            "source_file": chunk.get("source_file") or "",
            "score": chunk.get("score"),
            "dense_score": chunk.get("dense_score"),
            "bm25_score": chunk.get("bm25_score"),
            "rrf_score": chunk.get("rrf_score"),
            "snippet": snippet,
        })
    return summary


def _build_task_summary(project_id: str) -> dict[str, Any]:
    """Snapshot the current listing for a project. Pure read — no writes, no LLM."""
    items = database.list_listing_items(project_id)
    by_name = {p["product_name"]: p for p in database.list_catalog_products(limit=2000)}
    enriched: list[dict[str, Any]] = []
    for it in items:
        product = by_name.get(it["product_name"]) or {}
        enriched.append({
            "product_name": it["product_name"],
            "status": it.get("status") or "",
            "notes": it.get("notes") or "",
            "sku_id": product.get("sku_id", ""),
            "category": " / ".join(
                part for part in [product.get("category_l1"), product.get("category_l2")] if part
            ),
        })
    return {"items": enriched, "total": len(enriched)}


def handle_chat(
    project_id: str,
    conversation_id: str,
    message: str,
    knowledge_ids: list[str] | None = None,
) -> dict[str, Any]:
    projects = database.list_projects()
    project = next((item for item in projects if item["id"] == project_id), {"id": project_id, "name": "当前项目"})
    listing_items = database.list_listing_items(project_id)
    history = database.list_conversation_messages(conversation_id)
    kb_ids = list(knowledge_ids or [])

    database.add_conversation_message(
        conversation_id,
        "user",
        message,
        {"event": "chat", "knowledge_ids": kb_ids},
    )

    if message.strip() == CONFIRM_PLAN_TRIGGER:
        applied_actions = _apply_previous_recommendations(project_id, conversation_id, history)
        summary = _build_task_summary(project_id)
        if summary["total"]:
            if applied_actions:
                reply = f"已确认执行上一个上架方案，并写入 {len(applied_actions)} 个商品。当前上架清单共 {summary['total']} 条。"
            else:
                reply = f"已为你汇总当前上架清单，共 {summary['total']} 条。"
        else:
            reply = "当前上架清单为空，也没有找到上一轮可执行的推荐方案。请先让 Agent 推荐选品后再确认。"
        metadata = {
            "event": "chat_reply",
            "actions": [],
            "applied_actions": applied_actions,
            "recommendations": [],
            "priority_analysis": [],
            "checklist": [],
            "risks": [],
            "needs_clarification": [],
            "confirmation": {"required": False},
            "rag_chunks": [],
            "knowledge_ids": kb_ids,
            "task_summary": summary,
        }
        database.add_conversation_message(conversation_id, "assistant", reply, metadata)
        return {
            "reply": reply,
            **metadata,
            "messages": database.list_conversation_messages(conversation_id),
            "listing_items": database.list_listing_items(project_id),
        }

    system_prompt, retrieved_chunks = _build_system_prompt(message, kb_ids)
    rag_summary = _rag_summary(retrieved_chunks)

    if not llm_available():
        parsed = {
            "reply": "模型未配置，无法回答。本项目已按你的要求关闭 chatbox 本地 fallback；请先配置可用的 LLM API Key。",
            "actions": [],
            "risks": [{"description": "LLM 未配置，本轮没有模型回答。", "severity": "high"}],
            "needs_clarification": [],
            "confirmation": {"required": False},
        }
    else:
        try:
            raw = call_llm(system_prompt, _build_user_prompt(message, project, listing_items, history))
            parsed = _parse_model_response(raw)
            if _needs_business_context(message):
                parsed, _dropped = _validate_and_enrich(parsed)
                parsed = apply_risk_audit(parsed, audit_chat_result(project_id, message, parsed))
            else:
                parsed = _sanitize_non_business_response(parsed)
        except Exception as exc:
            parsed = {
                "reply": f"模型调用失败，我没有走本地 fallback，也没有改动上架清单。错误：{exc}",
                "actions": [],
                "risks": [{"description": "模型调用失败，本轮没有本地 fallback 回答。", "severity": "high"}],
                "needs_clarification": [],
                "confirmation": {"required": False},
            }

    actions = parsed.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    applied_actions = _apply_actions(project_id, conversation_id, actions)
    reply = str(parsed.get("reply") or "模型没有返回可展示内容。")
    metadata = _metadata(parsed, actions, applied_actions, rag_summary, kb_ids)

    database.add_conversation_message(conversation_id, "assistant", reply, metadata)
    return {
        "reply": reply,
        **metadata,
        "messages": database.list_conversation_messages(conversation_id),
        "listing_items": database.list_listing_items(project_id),
    }
