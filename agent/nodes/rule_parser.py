from __future__ import annotations

import re
from typing import Any

from agent.llm import call_llm, llm_available, parse_llm_json
from agent.prompts import RULE_PARSER_SYSTEM, RULE_PARSER_USER
from agent.state import AgentState, ParsedRule, RiskPoint


def _split_rule_text(raw_rules: str) -> list[str]:
    parts = re.split(r"[；;\n]+|\d+[.、]", raw_rules)
    return [part.strip(" 。.：:") for part in parts if part.strip(" 。.：:")]


def _make_rule(
    idx: int,
    rule: str,
    source_text: str,
    field: str,
    operator: str,
    value: Any,
    unit: str,
    confidence: float,
    ambiguous: bool = False,
    ambiguity_note: str = "",
    risk_level: str = "low",
) -> ParsedRule:
    return {
        "id": f"rule_{idx}",
        "rule": rule,
        "source_text": source_text,
        "field": field,
        "operator": operator,
        "value": value,
        "unit": unit,
        "confidence": confidence,
        "ambiguous": ambiguous,
        "ambiguity_note": ambiguity_note,
        "requires_human": ambiguous or confidence < 0.7,
        "risk_level": risk_level,
    }


def deterministic_rule_parse(raw_rules: str) -> dict[str, list[Any]]:
    parsed_rules: list[ParsedRule] = []
    risks: list[RiskPoint] = []
    questions: list[str] = []
    chunks = _split_rule_text(raw_rules)
    idx = 1

    def source_containing(keyword: str) -> str:
        return next((chunk for chunk in chunks if keyword in chunk), raw_rules)

    if re.search(r"近\s*30\s*天.*销量.*(?:>=|≥|不少于|不低于)\s*100", raw_rules):
        source = source_containing("销量")
        parsed_rules.append(_make_rule(idx, "近30天销量不少于100件", source, "sales_30d", ">=", 100, "件", 0.94))
        idx += 1
        questions.append("'近30天销量'是滚动30天还是自然月口径？")
        risks.append({
            "description": "近30天口径可能影响销量判断",
            "severity": "medium",
            "suggestion": "执行前确认平台采用滚动30天还是自然月。",
        })

    rating_match = re.search(r"好评率.*(?:>=|≥|不少于|不低于)\s*(\d+(?:\.\d+)?)\s*%", raw_rules)
    if rating_match:
        value = float(rating_match.group(1)) / 100
        source = source_containing("好评率")
        parsed_rules.append(_make_rule(idx, f"好评率不低于{rating_match.group(1)}%", source, "rating", ">=", value, "%", 0.93))
        idx += 1

    stock_match = re.search(r"库存.*(?:>=|≥|不少于|不低于)\s*(\d+)", raw_rules)
    if stock_match:
        value = int(stock_match.group(1))
        source = source_containing("库存")
        parsed_rules.append(_make_rule(idx, f"库存不少于{value}件", source, "stock", ">=", value, "件", 0.94))
        idx += 1

    if re.search(r"活动价.*(?:不得高于|不高于|<=|≤).*近\s*30\s*天最低价", raw_rules):
        source = source_containing("活动价")
        parsed_rules.append(_make_rule(
            idx,
            "活动价不得高于近30天最低价",
            source,
            "price",
            "<=",
            "lowest_price_30d",
            "元",
            0.86,
            ambiguous=True,
            ambiguity_note="近30天最低价是否包含促销价、券后价或会员价需要确认。",
            risk_level="medium",
        ))
        idx += 1
        questions.append("'近30天最低价'是否包含促销价、券后价或会员价？")
        risks.append({
            "description": "最低价口径不清会导致价格合规误判",
            "severity": "high",
            "suggestion": "让运营确认平台价保/最低价统计口径。",
        })

    discount_match = re.search(r"折扣(?:力度)?\s*(?:>=|≥|不少于|不低于)\s*(\d+(?:\.\d+)?)\s*折", raw_rules)
    if discount_match:
        value = float(discount_match.group(1))
        source = source_containing("折扣")
        parsed_rules.append(_make_rule(idx, f"折扣力度不低于{discount_match.group(1)}折", source, "discount", ">=", value, "折", 0.9))
        idx += 1

    category_patterns = [("黄金", 5), ("钻石", 10)]
    for category, default_limit in category_patterns:
        match = re.search(fr"{category}.*最多\s*(\d+)\s*个?\s*SKU", raw_rules, flags=re.IGNORECASE)
        if match:
            limit = int(match.group(1) or default_limit)
            source = source_containing(category)
            parsed_rules.append(_make_rule(idx, f"{category}类单店最多{limit}个SKU", source, "category_sku_limit", "<=", {"category": category, "limit": limit}, "SKU", 0.91))
            idx += 1

    if re.search(r"品牌日.*(?:不可|不能|不得).*重复报名|已参加.*品牌日.*不可", raw_rules):
        source = source_containing("品牌日")
        parsed_rules.append(_make_rule(idx, "已参加品牌日活动的商品不可重复报名", source, "mutual_exclusion", "==", False, "", 0.92, risk_level="high"))
        risks.append({
            "description": "品牌日与大促报名存在互斥冲突",
            "severity": "high",
            "suggestion": "核查商品当前活动报名状态，避免重复报名。",
        })

    if not parsed_rules and raw_rules.strip():
        parsed_rules.append(_make_rule(
            1,
            "存在未能确定性解析的活动规则",
            raw_rules.strip(),
            "other",
            "review",
            None,
            "",
            0.45,
            ambiguous=True,
            ambiguity_note="当前规则未匹配到内置解析模式，需要人工确认。",
            risk_level="high",
        ))
        questions.append("这段规则需要如何转化为可执行检查项？")

    return {
        "parsed_rules": parsed_rules,
        "risk_points": risks,
        "clarification_questions": list(dict.fromkeys(questions)),
    }


def rule_parser(state: AgentState) -> dict[str, list[Any]]:
    raw_rules = state.get("raw_rules", "")
    if llm_available():
        try:
            prompt = RULE_PARSER_USER.format(raw_rules=raw_rules)
            result = parse_llm_json(call_llm(RULE_PARSER_SYSTEM, prompt))
            return {
                "parsed_rules": result.get("parsed_rules", []),
                "risk_points": result.get("risk_points", []),
                "clarification_questions": result.get("clarification_questions", []),
            }
        except Exception as exc:
            return {
                "parsed_rules": [],
                "risk_points": [{
                    "description": "模型调用失败，未执行本地 fallback。",
                    "severity": "high",
                    "suggestion": f"检查 API key、网络或模型返回格式。错误：{exc}",
                }],
                "clarification_questions": ["模型调用失败，请检查配置后重新解析。"],
            }
    return deterministic_rule_parse(raw_rules)
