from __future__ import annotations

import os

import pytest

os.environ["AFH_DISABLE_LLM"] = "1"

from agent.graph import build_graph
from agent.nodes.checklist_builder import checklist_builder
from agent.nodes.human_review_gate import human_review_gate
from agent.nodes.product_verifier import deterministic_product_verify
from agent.nodes.rule_parser import deterministic_rule_parse
from agent.state import initial_state


SAMPLE_RULES = """天猫618大促选品规则
1.参与商品必须满足：近30天销量≥100件；好评率≥95%；库存≥500件。
2.价格要求：活动价不得高于近30天最低价；折扣力度≥7折。
3.品类限制：黄金类自单店最多5个SKU；钻石类自单店最多10个SKU。
4.互斥规则：已参加“品牌日”活动的商品不可重复报名。"""


@pytest.fixture(autouse=True)
def disable_llm_for_graph_tests(monkeypatch):
    monkeypatch.setenv("AFH_DISABLE_LLM", "1")


def test_rule_parser_extracts_sample_rules():
    result = deterministic_rule_parse(SAMPLE_RULES)
    rules = result["parsed_rules"]

    assert len(rules) >= 8
    assert any(rule["field"] == "sales_30d" and rule["value"] == 100 for rule in rules)
    assert any(rule["field"] == "rating" and rule["value"] == 0.95 for rule in rules)
    assert any(rule["field"] == "stock" and rule["value"] == 500 for rule in rules)
    assert any(rule["field"] == "mutual_exclusion" for rule in rules)
    assert result["clarification_questions"]


def test_checklist_builder_outputs_checklist_flow_and_examples():
    state = initial_state(SAMPLE_RULES)
    state.update(deterministic_rule_parse(SAMPLE_RULES))

    result = checklist_builder(state)

    assert len(result["checklist"]) == len(state["parsed_rules"])
    assert len(result["decision_flow"]) == len(state["parsed_rules"])
    assert len(result["counter_examples"]) >= 3
    assert result["checklist_history"]


def test_gate_waits_when_questions_exist():
    state = initial_state("")
    state["clarification_questions"] = ["近30天是自然月还是滚动30天？"]

    assert human_review_gate(state) == "wait_for_human"


def test_gate_continues_after_human_confirmation():
    state = initial_state("")
    state["clarification_questions"] = ["近30天是自然月还是滚动30天？"]
    state["human_confirmed"] = True

    assert human_review_gate(state) == "continue"


def test_product_verifier_rejects_boundary_values():
    state = initial_state(SAMPLE_RULES, {
        "name": "足金项链A",
        "sales_30d": 99,
        "rating": 0.96,
        "stock": 500,
        "price": 999,
        "lowest_price_30d": 999,
        "discount": 7,
        "category": "黄金",
        "category_sku_count": 5,
        "in_brand_day": False,
    })
    parsed = deterministic_rule_parse(SAMPLE_RULES)
    state.update(parsed)
    state["human_confirmed"] = True

    result = deterministic_product_verify(state)

    assert result["final_decision"] == "不通过"
    assert any(item["rule"] == "近30天销量不少于100件" and item["passed"] is False for item in result["verification_result"])


def test_product_verifier_flags_conflicting_brand_day():
    state = initial_state(SAMPLE_RULES, {
        "name": "钻石戒指B",
        "sales_30d": 150,
        "rating": 0.98,
        "stock": 600,
        "price": 1999,
        "lowest_price_30d": 1999,
        "discount": 7.5,
        "category": "钻石",
        "category_sku_count": 10,
        "in_brand_day": True,
    })
    state.update(deterministic_rule_parse(SAMPLE_RULES))
    state["human_confirmed"] = True

    result = deterministic_product_verify(state)

    assert result["final_decision"] == "不通过"
    assert any(item["rule"] == "已参加品牌日活动的商品不可重复报名" and item["passed"] is False for item in result["verification_result"])


def test_full_graph_stops_for_human_review_before_confirmation():
    state = initial_state(SAMPLE_RULES, {"name": "足金项链A", "sales_30d": 120})
    app = build_graph()

    result = app.invoke(state)

    assert result["clarification_questions"]
    assert result["final_decision"] == ""


def test_full_graph_verifies_after_confirmation():
    state = initial_state(SAMPLE_RULES, {
        "name": "足金项链A",
        "sales_30d": 120,
        "rating": 0.96,
        "stock": 800,
        "price": 999,
        "lowest_price_30d": 999,
        "discount": 7.5,
        "category": "黄金",
        "category_sku_count": 3,
        "in_brand_day": False,
    })
    state["human_confirmed"] = True
    state["clarification_answers"] = {
        "'近30天销量'是滚动30天还是自然月口径？": "滚动30天",
        "'近30天最低价'是否包含促销价、券后价或会员价？": "包含券后价",
    }
    app = build_graph()

    result = app.invoke(state)

    assert result["verification_result"]
    assert result["final_decision"] in {"通过", "不通过", "建议人工确认"}
