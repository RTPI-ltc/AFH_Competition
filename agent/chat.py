from __future__ import annotations

import json
import re
from typing import Any

from agent import database
from agent.llm import call_llm, llm_available, parse_llm_json
from agent.rag import append_context_to_system, retrieve_safe


CHAT_SYSTEM = """你是一个珠宝电商运营执行助手。
你要围绕当前项目的上架清单、活动规则、商品报名和运营执行回答用户。

你可以根据用户自然语言建议增减上架商品。输出必须是 JSON：
{
  "reply": "给用户看的中文回复",
  "actions": [
    {
      "type": "add_listing_item|remove_listing_item|none",
      "product_name": "商品名称",
      "status": "待确认|拟上架|已上架|需补充信息|不建议上架",
      "notes": "原因或备注",
      "details": {"任意结构化信息": "值"}
    }
  ]
}

如果用户只是咨询，不需要动作，actions 返回空数组。
不要编造已经不存在的数据库记录；不确定时先说明需要补充信息。"""


def _fallback_reply(message: str, listing_items: list[dict[str, Any]]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    add_match = re.search(r"(?:加入|添加|放入|新增).*?(?:清单|上架).*?([A-Za-z0-9\u4e00-\u9fff]+)", message)
    if add_match:
        product_name = add_match.group(1).strip(" ，。,.")
        actions.append({
            "type": "add_listing_item",
            "product_name": product_name,
            "status": "待确认",
            "notes": "由自然语言 fallback 识别加入上架清单。",
            "details": {"source": "fallback"},
        })
        return {"reply": f"已识别到你想把“{product_name}”加入上架清单，我先标记为待确认。", "actions": actions}

    names = "、".join(item["product_name"] for item in listing_items[:5]) or "暂无商品"
    return {
        "reply": f"我会围绕当前项目的上架清单协助你。当前清单包含：{names}。你可以直接说“把足金项链A加入上架清单”或“评估这个商品能不能上架”。",
        "actions": [],
    }


def _extract_product_name(message: str, action_words: str) -> str:
    patterns = [
        rf"(?:把|将)?(.+?)(?:{action_words})(?:到|入)?(?:上架清单|清单)",
        rf"(?:{action_words})(?:上架清单|清单)?[:： ]+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            return match.group(1).strip(" ，。,.、\"'“”")
    return ""


def _quick_listing_intent(message: str, listing_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    add_words = "加入|添加|放入|新增|加到|加入到"
    remove_words = "移除|删除|去掉|移出|从清单删除|从上架清单删除"

    if re.search(add_words, message) and re.search("上架|清单", message):
        product_name = _extract_product_name(message, add_words)
        if product_name:
            return {
                "reply": f"好的，已将“{product_name}”加入当前项目的上架清单，状态标记为“待确认”。",
                "actions": [{
                    "type": "add_listing_item",
                    "product_name": product_name,
                    "status": "待确认",
                    "notes": "由自然语言指令快速加入，未调用模型。",
                    "details": {"source": "quick_intent"},
                }],
            }

    if re.search(remove_words, message) and re.search("上架|清单", message):
        product_name = _extract_product_name(message, remove_words)
        if not product_name:
            product_name = next((item["product_name"] for item in listing_items if item["product_name"] in message), "")
        if product_name:
            return {
                "reply": f"好的，已尝试从当前项目的上架清单移除“{product_name}”。",
                "actions": [{
                    "type": "remove_listing_item",
                    "product_name": product_name,
                    "status": "待确认",
                    "notes": "由自然语言指令快速移除，未调用模型。",
                    "details": {"source": "quick_intent"},
                }],
            }

    return None


def _build_user_prompt(message: str, project: dict[str, Any], listing_items: list[dict[str, Any]], history: list[dict[str, Any]]) -> str:
    compact_history = [
        {"role": item["role"], "content": item["content"]}
        for item in history[-10:]
    ]
    return json.dumps(
        {
            "project": project,
            "listing_items": listing_items,
            "recent_messages": compact_history,
            "user_message": message,
        },
        ensure_ascii=False,
    )


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
            "snippet": snippet,
        })
    return summary


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

    system_prompt, retrieved_chunks = _build_system_prompt(message, kb_ids)
    rag_summary = _rag_summary(retrieved_chunks)

    quick = _quick_listing_intent(message, listing_items)
    if quick is not None:
        parsed = quick
    elif llm_available():
        try:
            raw = call_llm(system_prompt, _build_user_prompt(message, project, listing_items, history))
            parsed = parse_llm_json(raw)
        except Exception as exc:
            parsed = {
                "reply": f"模型调用失败，我没有改动上架清单。错误：{exc}",
                "actions": [],
            }
    else:
        parsed = _fallback_reply(message, listing_items)

    actions = parsed.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    applied_actions = _apply_actions(project_id, conversation_id, actions)
    reply = str(parsed.get("reply") or "我已收到。")

    database.add_conversation_message(
        conversation_id,
        "assistant",
        reply,
        {
            "event": "chat_reply",
            "actions": actions,
            "applied_actions": applied_actions,
            "rag_chunks": rag_summary,
            "knowledge_ids": kb_ids,
        },
    )
    return {
        "reply": reply,
        "actions": actions,
        "applied_actions": applied_actions,
        "rag_chunks": rag_summary,
        "messages": database.list_conversation_messages(conversation_id),
        "listing_items": database.list_listing_items(project_id),
    }
