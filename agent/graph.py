from __future__ import annotations

from typing import Any, Callable

from agent.nodes.checklist_builder import checklist_builder
from agent.nodes.human_review_gate import human_review_gate
from agent.nodes.product_verifier import product_verifier
from agent.nodes.rule_parser import rule_parser
from agent.state import AgentState


class SimpleGraph:
    def invoke(self, state: AgentState) -> AgentState:
        next_state = dict(state)
        next_state.update(rule_parser(next_state))
        next_state.update(checklist_builder(next_state))
        if human_review_gate(next_state) == "continue":
            next_state.update(product_verifier(next_state))
        return next_state  # type: ignore[return-value]


def _build_langgraph() -> Any:
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(AgentState)
    workflow.add_node("rule_parser", rule_parser)
    workflow.add_node("checklist_builder", checklist_builder)
    workflow.add_node("product_verifier", product_verifier)

    workflow.set_entry_point("rule_parser")
    workflow.add_edge("rule_parser", "checklist_builder")
    workflow.add_conditional_edges(
        "checklist_builder",
        human_review_gate,
        {"wait_for_human": END, "continue": "product_verifier"},
    )
    workflow.add_edge("product_verifier", END)
    return workflow.compile()


def build_graph() -> Any:
    try:
        return _build_langgraph()
    except Exception:
        return SimpleGraph()


def run_pipeline(state: AgentState) -> AgentState:
    app = build_graph()
    return app.invoke(state)
