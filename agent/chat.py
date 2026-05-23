from __future__ import annotations

import json
import re
from typing import Any

from agent import database
from agent.llm import call_llm, llm_available, parse_llm_json


CHAT_SYSTEM = """你是珠宝电商运营执行助手。
你的目标不是泛聊，而是帮助运营把活动规则、商品库、上架清单和人工确认点串成可执行方案。

回答必须严格 JSON，结构如下：
{
  "reply": "给用户看的中文回答。先直接回答，再补优先级分析、检查清单、风险点、需人工确认信息。不要要求用户先提供商品，除非商品库为空或问题必须依赖外部信息。",
  "recommendations": [
    {
      "sku_id": "商品编号",
      "product_name": "商品名称",
      "priority": "high|medium|low",
      "score": 0-100,
      "reason": "推荐原因"
    }
  ],
  "priority_analysis": ["优先级分析要点"],
  "checklist": [
    {"condition": "需要检查的事项", "priority": "high|medium|low", "detail": "执行说明"}
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
      "product_name": "商品名称",
      "status": "待确认|拟上架|已上架|需补充信息|不建议上架",
      "notes": "原因或备注",
      "details": {}
    }
  ]
}

约束：
1. 用户问“推荐上架什么/选哪些商品/给方案”时，必须基于商品库主动推荐，不要回复“请提供商品”。
2. 对高风险、低置信、口径不完整的信息要标注人工确认，不要假装已经确认。
3. 只有用户明确确认方案时，才把推荐商品加入上架清单。
4. 如果用户只是要求增删某个商品，可以直接返回 add/remove actions。
"""


RECOMMEND_INTENT = re.compile(r"推荐|选品|上架什么|报什么|报名什么|优先上架|上架方案|给.*方案|怎么上架|帮我.*上架")
CONFIRM_INTENT = re.compile(r"^(确认|同意|执行|可以|就这样|按这个|采纳)$|(?:确认|同意|执行|按这个|采纳).*(?:方案|上架|清单|推荐)")
ADD_WORDS = "加入|添加|放入|新增|加到|加入到"
REMOVE_WORDS = "移除|删除|去掉|移出|从清单删除|从上架清单删除"


def _normalize_rate(value: Any) -> float:
    number = float(value or 0)
    return number if number <= 1 else number / 100


def _money(value: Any) -> float:
    return float(value or 0)


def _score_product(product: dict[str, Any]) -> tuple[int, list[str], list[dict[str, str]]]:
    stock = int(product.get("stock") or 0)
    sales = int(product.get("last_90d_sales") or 0)
    review = _normalize_rate(product.get("review_rate"))
    return_rate = _normalize_rate(product.get("return_rate"))
    list_price = _money(product.get("list_price_rmb"))
    tag_price = _money(product.get("tag_price_rmb"))
    last_30d_min = _money(product.get("last_30d_min_price"))
    active_campaigns = product.get("active_campaigns") or []

    score = 0
    reasons: list[str] = []
    risks: list[dict[str, str]] = []

    if stock >= 500:
        score += 22
        reasons.append(f"库存 {stock} 件，承接活动流量较稳")
    elif stock >= 100:
        score += 15
        reasons.append(f"库存 {stock} 件，可做中等规模报名")
    else:
        score += 6
        risks.append({"description": f"{product['product_name']} 库存仅 {stock} 件，需确认活动锁库和补货能力。", "severity": "medium"})

    if sales >= 500:
        score += 24
        reasons.append(f"近90天销量 {sales}，需求验证充分")
    elif sales >= 100:
        score += 16
        reasons.append(f"近90天销量 {sales}，具备基础动销")
    else:
        score += 7
        risks.append({"description": f"{product['product_name']} 近90天销量 {sales}，需确认活动流量预期。", "severity": "medium"})

    if review >= 0.98:
        score += 18
        reasons.append(f"好评率 {review:.1%}，评价风险较低")
    elif review >= 0.96:
        score += 12
        reasons.append(f"好评率 {review:.1%}，满足基础口碑要求")
    else:
        score += 4
        risks.append({"description": f"{product['product_name']} 好评率 {review:.1%}，可能影响报名或转化。", "severity": "medium"})

    if return_rate <= 0.015:
        score += 10
        reasons.append(f"退货率 {return_rate:.1%}，售后压力低")
    elif return_rate <= 0.03:
        score += 6
    else:
        risks.append({"description": f"{product['product_name']} 退货率 {return_rate:.1%}，需人工复核售后原因。", "severity": "medium"})

    if tag_price > 0 and list_price > 0:
        discount = (tag_price - list_price) / tag_price
        if discount >= 0.08:
            score += 12
            reasons.append(f"标价到日常售价折让约 {discount:.0%}，有活动价格空间")
        elif discount >= 0.03:
            score += 6
        if last_30d_min and list_price > last_30d_min:
            risks.append({"description": f"{product['product_name']} 当前售价高于近30天最低价，活动价口径需确认。", "severity": "high"})
            score -= 8

    if product.get("new_product"):
        score += 5
        reasons.append("新品可作为活动测试款，但需确认平台新品扶持口径")

    if active_campaigns:
        score -= 18
        risks.append({"description": f"{product['product_name']} 已在活动 {', '.join(active_campaigns)} 中，需确认是否互斥报名。", "severity": "high"})

    if product.get("certificate_ids"):
        score += 4
    else:
        risks.append({"description": f"{product['product_name']} 未记录证书编号，上架前需补齐资质。", "severity": "medium"})

    return max(0, min(100, score)), reasons, risks


def _priority(score: int) -> str:
    if score >= 78:
        return "high"
    if score >= 58:
        return "medium"
    return "low"


def _recommend_from_catalog(limit: int = 5) -> dict[str, Any]:
    products = database.list_catalog_products("", limit=1000)
    ranked: list[dict[str, Any]] = []
    risk_pool: list[dict[str, str]] = []
    for product in products:
        score, reasons, risks = _score_product(product)
        ranked.append({**product, "_score": score, "_reasons": reasons})
        risk_pool.extend(risks)

    ranked.sort(key=lambda item: item["_score"], reverse=True)
    selected = ranked[:limit]
    recommendations = [
        {
            "sku_id": item["sku_id"],
            "product_name": item["product_name"],
            "priority": _priority(item["_score"]),
            "score": item["_score"],
            "reason": "；".join(item["_reasons"][:3]) or "商品基础信息完整，可进入人工复核队列",
        }
        for item in selected
    ]

    priority_analysis = [
        "高优先级：库存、动销、好评率和活动价格空间同时较稳的商品，适合先进入报名方案。",
        "中优先级：具备动销基础，但需要确认价格口径、活动互斥或供给能力后再推进。",
        "低优先级：库存、销量、资质或评价存在明显短板，建议暂不作为首批主推。",
    ]
    checklist = [
        {"condition": "核对活动价不高于平台要求的历史最低价口径", "priority": "high", "detail": "重点确认近30天/90天最低价是否含券后价、会员价和跨店满减。"},
        {"condition": "确认推荐 SKU 未参加互斥活动", "priority": "high", "detail": "品牌日、平台大促、站外补贴等活动可能存在互斥。"},
        {"condition": "确认库存锁定、补货周期和发货时效", "priority": "medium", "detail": "库存不足或交付周期过长会影响活动履约。"},
        {"condition": "补齐证书、主图、详情页与售后承诺", "priority": "medium", "detail": "珠宝类商品需要重点检查材质、重量、证书编号和售后规则。"},
    ]
    needs_clarification = [
        "本次活动的价格保护口径和最低价统计周期。",
        "每个品类允许报名的 SKU 数量上限。",
        "推荐商品是否存在品牌日、达人专场或站外补贴等互斥活动。",
    ]
    deduped_risks: list[dict[str, str]] = []
    seen: set[str] = set()
    for risk in risk_pool:
        key = risk["description"]
        if key not in seen:
            deduped_risks.append(risk)
            seen.add(key)
        if len(deduped_risks) >= 5:
            break

    if not products:
        return {
            "reply": "商品库目前为空，我无法给出基于数据的上架推荐。请先在商品管理中导入或新增商品。",
            "recommendations": [],
            "priority_analysis": [],
            "checklist": [{"condition": "先建立商品库", "priority": "high", "detail": "至少需要商品名称、品类、价格、库存、销量和评价数据。"}],
            "risks": [{"description": "缺少商品库会导致推荐不可验证。", "severity": "high"}],
            "needs_clarification": [],
            "confirmation": {"required": False},
            "actions": [],
        }

    lines = ["我先按当前商品库给出首批上架建议，不需要你额外提供商品。", "", "推荐优先级："]
    for index, item in enumerate(recommendations, start=1):
        label = {"high": "高", "medium": "中", "low": "低"}[item["priority"]]
        lines.append(f"{index}. {item['product_name']}（{item['sku_id']}）：{label}优先级，评分 {item['score']}。{item['reason']}")
    lines.extend([
        "",
        "方案口径：先推高分且风险可控的 SKU，价格和活动互斥项在确认后再写入正式上架清单。",
        "如果你确认这些人工项都没问题，我可以把推荐 SKU 加入当前项目的上架清单，状态标记为“拟上架”。",
    ])

    return {
        "reply": "\n".join(lines),
        "recommendations": recommendations,
        "priority_analysis": priority_analysis,
        "checklist": checklist,
        "risks": deduped_risks,
        "needs_clarification": needs_clarification,
        "confirmation": {
            "required": True,
            "question": "是否确认按这个推荐方案加入上架清单？",
            "confirm_label": "确认方案",
            "revise_label": "继续调整",
            "recommended_skus": [item["sku_id"] for item in recommendations],
        },
        "actions": [],
    }


def _latest_pending_plan(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in reversed(history):
        if item.get("role") not in {"assistant", "agent"}:
            continue
        metadata = item.get("metadata") or {}
        confirmation = metadata.get("confirmation") or {}
        recommendations = metadata.get("recommendations") or []
        if confirmation.get("required") and recommendations:
            return metadata
    return None


def _confirm_latest_plan(project_id: str, conversation_id: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    plan = _latest_pending_plan(history)
    if not plan:
        return {
            "reply": "我还没有找到可确认的上架方案。你可以先问“推荐我上架什么”，我会基于商品库生成方案和确认按钮。",
            "actions": [],
            "checklist": [],
            "risks": [],
            "needs_clarification": [],
            "confirmation": {"required": False},
        }

    existing = {item["product_name"] for item in database.list_listing_items(project_id)}
    applied: list[dict[str, Any]] = []
    skipped: list[str] = []
    for recommendation in plan.get("recommendations", []):
        product_name = str(recommendation.get("product_name") or "").strip()
        if not product_name:
            continue
        if product_name in existing:
            skipped.append(product_name)
            continue
        item_id = database.add_listing_item(
            project_id,
            product_name,
            details={
                "source": "confirmed_recommendation",
                "sku_id": recommendation.get("sku_id"),
                "priority": recommendation.get("priority"),
                "score": recommendation.get("score"),
                "reason": recommendation.get("reason"),
            },
            status="拟上架",
            notes="用户已确认 AI 推荐方案，加入拟上架清单。",
            source_conversation_id=conversation_id,
        )
        applied.append({"type": "add_listing_item", "item_id": item_id, "product_name": product_name, "status": "拟上架"})

    added_names = "、".join(item["product_name"] for item in applied) or "无新增商品"
    skipped_text = f"\n已在清单中的商品跳过：{'、'.join(skipped)}。" if skipped else ""
    return {
        "reply": f"已确认方案，并将 {added_names} 加入当前项目上架清单，状态为“拟上架”。{skipped_text}\n下一步建议按检查清单逐项确认价格、活动互斥、库存和证书信息。",
        "actions": [],
        "applied_actions": applied,
        "checklist": [
            {"condition": "锁定拟上架 SKU 的活动价和库存", "priority": "high", "detail": "确认后再进入平台报名。"},
            {"condition": "复核人工确认项", "priority": "high", "detail": "价格保护、互斥活动、品类 SKU 上限都需要运营确认。"},
            {"condition": "准备上架素材", "priority": "medium", "detail": "包括主图、详情、证书、发货和售后说明。"},
        ],
        "risks": plan.get("risks", []),
        "needs_clarification": [],
        "confirmation": {"required": False, "status": "confirmed"},
    }


def _extract_product_name(message: str, action_words: str) -> str:
    patterns = [
        rf"(?:把|将)?(.+?)(?:{action_words})(?:到|入)?(?:上架清单|清单)",
        rf"(?:{action_words})(?:上架清单|清单)?[:： ]+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1).strip(" ，,。.\"'“”")
    return ""


def _quick_listing_intent(message: str, listing_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if re.search(ADD_WORDS, message) and re.search("上架|清单", message):
        product_name = _extract_product_name(message, ADD_WORDS)
        if product_name:
            return {
                "reply": f"好的，已将“{product_name}”加入当前项目的上架清单，状态标记为“待确认”。",
                "actions": [{
                    "type": "add_listing_item",
                    "product_name": product_name,
                    "status": "待确认",
                    "notes": "用户明确要求加入上架清单。",
                    "details": {"source": "quick_intent"},
                }],
                "checklist": [{"condition": f"补齐“{product_name}”的价格、库存、证书和活动互斥信息", "priority": "high", "detail": "待确认后再改为拟上架或已上架。"}],
                "risks": [],
                "needs_clarification": ["该商品的活动价、库存锁定量、证书信息和是否参加互斥活动。"],
                "confirmation": {"required": False},
            }

    if re.search(REMOVE_WORDS, message) and re.search("上架|清单", message):
        product_name = _extract_product_name(message, REMOVE_WORDS)
        if not product_name:
            product_name = next((item["product_name"] for item in listing_items if item["product_name"] in message), "")
        if product_name:
            return {
                "reply": f"好的，已尝试从当前项目的上架清单移除“{product_name}”。",
                "actions": [{
                    "type": "remove_listing_item",
                    "product_name": product_name,
                    "status": "待确认",
                    "notes": "用户明确要求移出上架清单。",
                    "details": {"source": "quick_intent"},
                }],
                "checklist": [],
                "risks": [],
                "needs_clarification": [],
                "confirmation": {"required": False},
            }

    return None


def _build_user_prompt(
    message: str,
    project: dict[str, Any],
    listing_items: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> str:
    compact_history = [{"role": item["role"], "content": item["content"]} for item in history[-10:]]
    catalog = database.list_catalog_products("", limit=30)
    return json.dumps(
        {
            "project": project,
            "listing_items": listing_items,
            "catalog_products": catalog,
            "recent_messages": compact_history,
            "user_message": message,
        },
        ensure_ascii=False,
    )


def _fallback_reply(message: str, listing_items: list[dict[str, Any]]) -> dict[str, Any]:
    if RECOMMEND_INTENT.search(message):
        return _recommend_from_catalog()
    names = "、".join(item["product_name"] for item in listing_items[:5]) or "暂无商品"
    return {
        "reply": f"我可以围绕当前项目的上架清单继续推进。当前清单包含：{names}。如果你问“推荐我上架什么”，我会直接基于商品库给出优先级、检查清单、风险点和确认按钮。",
        "actions": [],
        "checklist": [],
        "risks": [],
        "needs_clarification": [],
        "confirmation": {"required": False},
    }


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


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _metadata(parsed: dict[str, Any], actions: list[dict[str, Any]], applied_actions: list[dict[str, Any]]) -> dict[str, Any]:
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
    }


def handle_chat(project_id: str, conversation_id: str, message: str) -> dict[str, Any]:
    projects = database.list_projects()
    project = next((item for item in projects if item["id"] == project_id), {"id": project_id, "name": "当前项目"})
    listing_items = database.list_listing_items(project_id)
    history = database.list_conversation_messages(conversation_id)

    database.add_conversation_message(conversation_id, "user", message, {"event": "chat"})

    if CONFIRM_INTENT.search(message.strip()):
        parsed = _confirm_latest_plan(project_id, conversation_id, history)
    else:
        quick = _quick_listing_intent(message, listing_items)
        if quick is not None:
            parsed = quick
        elif RECOMMEND_INTENT.search(message):
            parsed = _recommend_from_catalog()
        elif llm_available():
            try:
                raw = call_llm(CHAT_SYSTEM, _build_user_prompt(message, project, listing_items, history))
                parsed = parse_llm_json(raw)
            except Exception as exc:
                parsed = {
                    "reply": f"模型调用失败，我没有改动上架清单。错误：{exc}",
                    "actions": [],
                    "checklist": [],
                    "risks": [{"description": "模型调用失败，本轮建议未经过 LLM 生成。", "severity": "medium"}],
                    "needs_clarification": [],
                    "confirmation": {"required": False},
                }
        else:
            parsed = _fallback_reply(message, listing_items)

    actions = parsed.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    applied_actions = parsed.get("applied_actions")
    if not isinstance(applied_actions, list):
        applied_actions = _apply_actions(project_id, conversation_id, actions)
    reply = str(parsed.get("reply") or "我已收到。")
    metadata = _metadata(parsed, actions, applied_actions)

    database.add_conversation_message(conversation_id, "assistant", reply, metadata)
    return {
        "reply": reply,
        **metadata,
        "messages": database.list_conversation_messages(conversation_id),
        "listing_items": database.list_listing_items(project_id),
    }
