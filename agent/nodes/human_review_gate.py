from __future__ import annotations

from agent.state import AgentState


def human_review_gate(state: AgentState) -> str:
    has_questions = len(state.get("clarification_questions", [])) > 0
    has_low_confidence = any(float(rule.get("confidence", 1.0)) < 0.7 for rule in state.get("parsed_rules", []))
    requires_human = any(bool(rule.get("requires_human")) for rule in state.get("parsed_rules", []))
    already_confirmed = state.get("human_confirmed", False)

    if (has_questions or has_low_confidence or requires_human) and not already_confirmed:
        return "wait_for_human"
    return "continue"
