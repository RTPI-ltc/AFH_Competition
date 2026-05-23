from __future__ import annotations

from typing import Any, Literal, TypedDict


RiskLevel = Literal["high", "medium", "low"]
Decision = Literal["通过", "不通过", "建议人工确认", ""]


class ParsedRule(TypedDict, total=False):
    id: str
    rule: str
    source_text: str
    field: str
    operator: str
    value: Any
    unit: str
    confidence: float
    ambiguous: bool
    ambiguity_note: str
    requires_human: bool
    risk_level: RiskLevel


class RiskPoint(TypedDict, total=False):
    description: str
    severity: RiskLevel
    suggestion: str


class ChecklistItem(TypedDict, total=False):
    id: str
    item: str
    source_text: str
    risk_level: RiskLevel
    confidence: float
    requires_human: bool


class DecisionStep(TypedDict, total=False):
    step: int
    question: str
    yes_action: str
    no_action: str


class CounterExample(TypedDict, total=False):
    scenario: str
    triggered_rule: str


class VerificationItem(TypedDict, total=False):
    rule: str
    passed: bool | None
    confidence: float
    note: str
    requires_human: bool


class AgentState(TypedDict):
    raw_rules: str
    parsed_rules: list[ParsedRule]
    risk_points: list[RiskPoint]
    clarification_questions: list[str]
    clarification_answers: dict[str, str]
    checklist: list[ChecklistItem]
    decision_flow: list[DecisionStep]
    counter_examples: list[CounterExample]
    human_confirmed: bool
    product_input: dict[str, Any]
    verification_result: list[VerificationItem]
    final_decision: Decision
    checklist_history: list[list[ChecklistItem]]


def initial_state(raw_rules: str = "", product_input: dict[str, Any] | None = None) -> AgentState:
    return {
        "raw_rules": raw_rules,
        "parsed_rules": [],
        "risk_points": [],
        "clarification_questions": [],
        "clarification_answers": {},
        "checklist": [],
        "decision_flow": [],
        "counter_examples": [],
        "human_confirmed": False,
        "product_input": product_input or {},
        "verification_result": [],
        "final_decision": "",
        "checklist_history": [],
    }
