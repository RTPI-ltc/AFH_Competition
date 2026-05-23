from __future__ import annotations

import json
from typing import Any

from agent.llm import call_llm, llm_available, parse_llm_json
from agent.prompts import CHECKLIST_BUILDER_SYSTEM, CHECKLIST_BUILDER_USER
from agent.state import AgentState, ChecklistItem, CounterExample, DecisionStep


def _rule_label(rule: dict[str, Any]) -> str:
    return str(rule.get("rule") or rule.get("source_text") or "未命名规则")


def deterministic_checklist_build(state: AgentState) -> dict[str, list[Any]]:
    checklist: list[ChecklistItem] = []
    decision_flow: list[DecisionStep] = []
    counter_examples: list[CounterExample] = []

    for index, rule in enumerate(state.get("parsed_rules", []), start=1):
        label = _rule_label(rule)
        checklist.append({
            "id": f"check_{index}",
            "item": f"确认{label}",
            "source_text": str(rule.get("source_text", label)),
            "risk_level": rule.get("risk_level", "low"),
            "confidence": float(rule.get("confidence", 0.7)),
            "requires_human": bool(rule.get("requires_human") or rule.get("ambiguous")),
        })
        decision_flow.append({
            "step": index,
            "question": f"商品是否满足：{label}？",
            "yes_action": "继续下一项检查",
            "no_action": "标记为不符合活动报名要求",
        })

        field = rule.get("field")
        value = rule.get("value")
        if field == "sales_30d":
            counter_examples.append({"scenario": f"近30天销量{int(value) - 1}件，差1件不达标", "triggered_rule": label})
        elif field == "rating":
            pct = int(float(value) * 100)
            counter_examples.append({"scenario": f"好评率{pct - 1}%，低于门槛", "triggered_rule": label})
        elif field == "stock":
            counter_examples.append({"scenario": f"库存{int(value) - 1}件，临近但不满足", "triggered_rule": label})
        elif field == "price":
            counter_examples.append({"scenario": "活动价比近30天最低价高0.01元", "triggered_rule": label})
        elif field == "discount":
            counter_examples.append({"scenario": f"折扣为{float(value) - 0.1:.1f}折，略低于要求", "triggered_rule": label})
        elif field == "mutual_exclusion":
            counter_examples.append({"scenario": "商品已参加品牌日，同时尝试报名618", "triggered_rule": label})

    if not counter_examples and checklist:
        counter_examples.append({"scenario": "规则存在口径不清，需人工判断边界案例", "triggered_rule": checklist[0]["item"]})

    history = list(state.get("checklist_history", []))
    if checklist:
        history.append(checklist)

    return {
        "checklist": checklist,
        "decision_flow": decision_flow,
        "counter_examples": counter_examples[:5],
        "checklist_history": history,
    }


def checklist_builder(state: AgentState) -> dict[str, list[Any]]:
    if llm_available():
        try:
            prompt = CHECKLIST_BUILDER_USER.format(
                parsed_rules=json.dumps(state.get("parsed_rules", []), ensure_ascii=False),
                risk_points=json.dumps(state.get("risk_points", []), ensure_ascii=False),
                clarification_answers=json.dumps(state.get("clarification_answers", {}), ensure_ascii=False),
            )
            result = parse_llm_json(call_llm(CHECKLIST_BUILDER_SYSTEM, prompt))
            checklist = result.get("checklist", [])
            history = list(state.get("checklist_history", []))
            if checklist:
                history.append(checklist)
            return {
                "checklist": checklist,
                "decision_flow": result.get("decision_flow", []),
                "counter_examples": result.get("counter_examples", []),
                "checklist_history": history,
            }
        except Exception as exc:
            history = list(state.get("checklist_history", []))
            return {
                "checklist": [],
                "decision_flow": [],
                "counter_examples": [],
                "checklist_history": history,
                "risk_points": state.get("risk_points", []) + [{
                    "description": "模型生成检查清单失败，未执行本地 fallback。",
                    "severity": "high",
                    "suggestion": f"检查 API key、网络或模型返回 JSON 格式。错误：{exc}",
                }],
            }
    return deterministic_checklist_build(state)
