from __future__ import annotations

import json
from typing import Any

from agent import database
from agent.llm import call_llm, llm_available, parse_llm_json


CHAT_SYSTEM = """你是珠宝电商运营执行助手，所有 chatbox 回复都必须由模型生成。

你会收到当前项目、当前上架清单、商品数据库、最近对话和用户消息。请基于这些真实数据回答，不要要求用户重新提供商品库里已经有的信息。

输出尽量使用严格 JSON：
{
  "reply": "给用户看的中文回答",
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
      "product_name": "商品名称",
      "status": "待确认|拟上架|已上架|需补充信息|不建议上架",
      "notes": "原因或备注",
      "details": {}
    }
  ]
}

要求：
1. 用户问推荐、选品、上架方案时，必须主动基于商品数据库推荐，不要说“请提供商品”。
2. 在回答基础上补充优先级分析、检查清单、风险点、需要人工确认的信息。
3. 信息不足时标注人工确认项，不要编造已经确认。
4. 只有用户明确要求加入、移除、确认方案时，才返回 add_listing_item 或 remove_listing_item actions。
5. 如果用户只是聊天或询问，不需要动作，actions 返回空数组。
"""


def _build_user_prompt(
    message: str,
    project: dict[str, Any],
    listing_items: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> str:
    compact_history = [
        {
            "role": item["role"],
            "content": item["content"],
            "metadata": item.get("metadata") or {},
        }
        for item in history[-10:]
    ]
    catalog = database.list_catalog_products("", limit=80)
    return json.dumps(
        {
            "project": project,
            "listing_items": listing_items,
            "catalog_products": catalog,
            "recent_messages": compact_history,
            "user_message": message,
            "instruction": "本轮回复必须由模型完成。不要走本地 fallback。请尽量返回符合系统格式的 JSON。",
        },
        ensure_ascii=False,
    )


def _parse_model_response(raw: str) -> dict[str, Any]:
    try:
        parsed = parse_llm_json(raw)
    except Exception:
        return {
            "reply": raw.strip() or "模型返回为空。",
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


def handle_chat(project_id: str, conversation_id: str, message: str) -> dict[str, Any]:
    projects = database.list_projects()
    project = next((item for item in projects if item["id"] == project_id), {"id": project_id, "name": "当前项目"})
    listing_items = database.list_listing_items(project_id)
    history = database.list_conversation_messages(conversation_id)

    database.add_conversation_message(conversation_id, "user", message, {"event": "chat"})

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
            raw = call_llm(CHAT_SYSTEM, _build_user_prompt(message, project, listing_items, history))
            parsed = _parse_model_response(raw)
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
    metadata = _metadata(parsed, actions, applied_actions)

    database.add_conversation_message(conversation_id, "assistant", reply, metadata)
    return {
        "reply": reply,
        **metadata,
        "messages": database.list_conversation_messages(conversation_id),
        "listing_items": database.list_listing_items(project_id),
    }
