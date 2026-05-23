from __future__ import annotations

import json
from typing import Any

from agent.llm import call_llm, llm_available, parse_llm_json
from agent.prompts import PRODUCT_VERIFIER_SYSTEM, PRODUCT_VERIFIER_USER
from agent.state import AgentState, VerificationItem


def _get_number(product: dict[str, Any], key: str, default: float = 0) -> float:
    try:
        return float(product.get(key, default))
    except (TypeError, ValueError):
        return default


def _verify_rule(rule: dict[str, Any], product: dict[str, Any], human_confirmed: bool = False) -> VerificationItem:
    label = str(rule.get("rule", "未命名规则"))
    field = rule.get("field")
    confidence = float(rule.get("confidence", 0.7))

    if bool(rule.get("requires_human")) and not human_confirmed:
        return {
            "rule": label,
            "passed": None,
            "confidence": min(confidence, 0.69),
            "note": rule.get("ambiguity_note", "该规则需要人工确认口径。"),
            "requires_human": True,
        }

    passed: bool | None = None
    note = ""

    if field == "sales_30d":
        actual = _get_number(product, "sales_30d")
        target = float(rule.get("value", 0))
        passed = actual >= target
        note = f"近30天销量为{actual:g}件，要求不少于{target:g}件。"
    elif field == "rating":
        actual = _get_number(product, "rating")
        if actual > 1:
            actual = actual / 100
        target = float(rule.get("value", 0))
        passed = actual >= target
        note = f"好评率为{actual * 100:.1f}%，要求不低于{target * 100:.1f}%。"
    elif field == "stock":
        actual = _get_number(product, "stock")
        target = float(rule.get("value", 0))
        passed = actual >= target
        note = f"库存为{actual:g}件，要求不少于{target:g}件。"
    elif field == "price":
        price = _get_number(product, "price")
        lowest = _get_number(product, "lowest_price_30d")
        passed = price <= lowest if lowest > 0 else None
        note = "缺少近30天最低价。" if passed is None else f"活动价{price:g}元，近30天最低价{lowest:g}元。"
    elif field == "discount":
        actual = _get_number(product, "discount")
        target = float(rule.get("value", 0))
        passed = actual >= target if actual > 0 else None
        note = "缺少折扣力度。" if passed is None else f"折扣为{actual:g}折，要求不低于{target:g}折。"
    elif field == "category_sku_limit":
        value = rule.get("value", {})
        category = value.get("category") if isinstance(value, dict) else ""
        limit = float(value.get("limit", 0)) if isinstance(value, dict) else 0
        actual_category = str(product.get("category", ""))
        sku_count = _get_number(product, "category_sku_count")
        if actual_category == category:
            passed = sku_count <= limit if sku_count > 0 else None
            note = "缺少该品类报名SKU数量。" if passed is None else f"{category}类报名SKU数为{sku_count:g}，上限{limit:g}。"
        else:
            passed = True
            note = f"商品品类为{actual_category or '未填写'}，不触发{category}类SKU上限。"
    elif field == "mutual_exclusion":
        in_brand_day = bool(product.get("in_brand_day", False))
        passed = not in_brand_day
        note = "商品已参加品牌日活动。" if in_brand_day else "未发现品牌日互斥报名。"
    else:
        return {
            "rule": label,
            "passed": None,
            "confidence": min(confidence, 0.6),
            "note": "当前 demo 无法确定性核查该规则。",
            "requires_human": True,
        }

    requires_human = passed is None
    return {
        "rule": label,
        "passed": passed,
        "confidence": confidence if not requires_human else min(confidence, 0.69),
        "note": note,
        "requires_human": requires_human,
    }


def deterministic_product_verify(state: AgentState) -> dict[str, Any]:
    product = state.get("product_input", {})
    human_confirmed = bool(state.get("human_confirmed", False))
    results = [_verify_rule(rule, product, human_confirmed) for rule in state.get("parsed_rules", [])]

    if not results:
        return {
            "verification_result": [{
                "rule": "未生成检查规则",
                "passed": None,
                "confidence": 0.0,
                "note": "请先解析活动规则。",
                "requires_human": True,
            }],
            "final_decision": "建议人工确认",
        }

    if any(item.get("requires_human") for item in results):
        decision = "建议人工确认"
    elif any(item.get("passed") is False for item in results):
        decision = "不通过"
    else:
        decision = "通过"

    return {"verification_result": results, "final_decision": decision}


def product_verifier(state: AgentState) -> dict[str, Any]:
    if llm_available():
        try:
            prompt = PRODUCT_VERIFIER_USER.format(
                product_input=json.dumps(state.get("product_input", {}), ensure_ascii=False),
                checklist=json.dumps(state.get("checklist", []), ensure_ascii=False),
                decision_flow=json.dumps(state.get("decision_flow", []), ensure_ascii=False),
            )
            result = parse_llm_json(call_llm(PRODUCT_VERIFIER_SYSTEM, prompt))
            return {
                "verification_result": result.get("verification_result", []),
                "final_decision": result.get("final_decision", "建议人工确认"),
            }
        except Exception as exc:
            return {
                "verification_result": [{
                    "rule": "模型核查失败",
                    "passed": None,
                    "confidence": 0.0,
                    "note": f"未执行本地 fallback。请检查 API key、网络或模型返回 JSON 格式。错误：{exc}",
                    "requires_human": True,
                }],
                "final_decision": "建议人工确认",
            }
    return deterministic_product_verify(state)
