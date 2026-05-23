from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent import chat
from agent import database
from agent.graph import build_graph
from agent.llm import model_status
from agent.state import initial_state


app = FastAPI(title="Execution Assistant Agent API", version="0.2.0")
graph = build_graph()
database.init_db()
database.seed_sample_catalog()


class ParseRequest(BaseModel):
    raw_rules: str
    session_id: str | None = None


class ProjectRequest(BaseModel):
    name: str
    description: str = ""


class ConversationRequest(BaseModel):
    project_id: str
    title: str = "新对话"


class ChatRequest(BaseModel):
    project_id: str
    conversation_id: str | None = None
    message: str


class ListingItemRequest(BaseModel):
    product_name: str
    status: str = "待确认"
    notes: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class CatalogProductRequest(BaseModel):
    product_name: str
    brand: str = ""
    category_l1: str = ""
    category_l2: str = ""
    pricing_model: str = "fixed"
    weight_g: float | None = None
    purity: str = ""
    gem_carat: float | None = None
    gem_color: str | None = None
    gem_clarity: str | None = None
    gem_cut: str | None = None
    tag_price_rmb: float = 0
    list_price_rmb: float = 0
    last_30d_min_price: float = 0
    last_90d_min_price: float = 0
    last_365d_min_price: float = 0
    stock: int = 0
    last_90d_sales: int = 0
    review_rate: float = 0
    return_rate: float = 0
    new_product: bool = False
    certificate_ids: list[str] = Field(default_factory=list)
    factory_id: str = ""
    lead_time_days: int = 0
    active_campaigns: list[str] = Field(default_factory=list)
    status: str = "在售"
    notes: str = ""


class ClarifyRequest(BaseModel):
    session_id: str | None = None
    raw_rules: str
    parsed_rules: list[dict[str, Any]]
    risk_points: list[dict[str, Any]]
    clarification_questions: list[str]
    clarification_answers: dict[str, str]
    checklist: list[dict[str, Any]]
    decision_flow: list[dict[str, Any]]
    counter_examples: list[dict[str, Any]]
    checklist_history: list[list[dict[str, Any]]] = []


class VerifyRequest(BaseModel):
    session_id: str | None = None
    raw_rules: str
    parsed_rules: list[dict[str, Any]]
    risk_points: list[dict[str, Any]]
    clarification_questions: list[str]
    clarification_answers: dict[str, str]
    checklist: list[dict[str, Any]]
    decision_flow: list[dict[str, Any]]
    counter_examples: list[dict[str, Any]]
    product_input: dict[str, Any]
    checklist_history: list[list[dict[str, Any]]] = []


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "db_path": str(database.get_db_path()), **model_status()}


@app.get("/sessions")
def sessions(limit: int = 20) -> dict[str, Any]:
    return {"sessions": database.list_sessions(limit)}


@app.get("/sessions/{session_id}")
def session_history(session_id: str) -> dict[str, Any]:
    return database.get_session_history(session_id)


@app.get("/projects")
def projects() -> dict[str, Any]:
    items = database.list_projects()
    if not items:
        project_id = database.create_project("默认项目", "系统自动创建的默认项目")
        database.create_conversation(project_id, "默认对话")
        items = database.list_projects()
    return {"projects": items}


@app.post("/projects")
def create_project(req: ProjectRequest) -> dict[str, Any]:
    project_id = database.create_project(req.name, req.description)
    conversation_id = database.create_conversation(project_id, "默认对话")
    return {"project_id": project_id, "conversation_id": conversation_id}


@app.delete("/projects/{project_id}")
def delete_project(project_id: str) -> dict[str, str]:
    database.delete_project(project_id)
    return {"status": "ok"}


@app.get("/projects/{project_id}/conversations")
def conversations(project_id: str) -> dict[str, Any]:
    project_id = database.ensure_project(project_id)
    items = database.list_conversations(project_id)
    if not items:
        database.create_conversation(project_id, "默认对话")
        items = database.list_conversations(project_id)
    return {"conversations": items}


@app.post("/conversations")
def create_conversation(req: ConversationRequest) -> dict[str, str]:
    project_id = database.ensure_project(req.project_id)
    conversation_id = database.create_conversation(project_id, req.title)
    return {"conversation_id": conversation_id}


@app.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, str]:
    database.delete_conversation(conversation_id)
    return {"status": "ok"}


@app.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: str) -> dict[str, Any]:
    return {"messages": database.list_conversation_messages(conversation_id)}


@app.post("/chat")
def chat_with_agent(req: ChatRequest) -> dict[str, Any]:
    project_id = database.ensure_project(req.project_id)
    conversation_id = database.ensure_conversation(project_id, req.conversation_id, title=req.message[:30] or "新对话")
    result = chat.handle_chat(project_id, conversation_id, req.message)
    return {"project_id": project_id, "conversation_id": conversation_id, **result}


@app.get("/projects/{project_id}/listing-items")
def listing_items(project_id: str) -> dict[str, Any]:
    project_id = database.ensure_project(project_id)
    return {"items": database.list_listing_items(project_id)}


@app.post("/projects/{project_id}/listing-items")
def create_listing_item(project_id: str, req: ListingItemRequest) -> dict[str, str]:
    project_id = database.ensure_project(project_id)
    item_id = database.add_listing_item(
        project_id,
        req.product_name,
        details=req.details,
        status=req.status,
        notes=req.notes,
    )
    return {"item_id": item_id}


@app.delete("/listing-items/{item_id}")
def delete_listing_item(item_id: str) -> dict[str, str]:
    database.delete_listing_item(item_id)
    return {"status": "ok"}


@app.get("/catalog/products")
def catalog_products(q: str = "", limit: int = 100) -> dict[str, Any]:
    return {"products": database.list_catalog_products(q, limit)}


@app.post("/catalog/products")
def create_catalog_product(req: CatalogProductRequest) -> dict[str, Any]:
    product_id = database.create_catalog_product(req.model_dump())
    return {"product": database.get_catalog_product(product_id)}


@app.get("/catalog/products/{product_id}")
def catalog_product(product_id: str) -> dict[str, Any]:
    return {"product": database.get_catalog_product(product_id)}


@app.put("/catalog/products/{product_id}")
def update_catalog_product(product_id: str, req: CatalogProductRequest) -> dict[str, Any]:
    database.update_catalog_product(product_id, req.model_dump())
    return {"product": database.get_catalog_product(product_id)}


@app.delete("/catalog/products/{product_id}")
def delete_catalog_product(product_id: str) -> dict[str, str]:
    database.delete_catalog_product(product_id)
    return {"status": "ok"}


@app.post("/parse")
def parse_rules(req: ParseRequest) -> dict[str, Any]:
    session_id = database.ensure_session(req.session_id, title=req.raw_rules[:40] or "Rule parsing")
    database.log_message(session_id, "user", req.raw_rules, {"event": "parse_request"})

    state = initial_state(req.raw_rules)
    result = graph.invoke(state)
    result["session_id"] = session_id

    database.save_rule_run(session_id, "parse", result)
    database.log_message(
        session_id,
        "assistant",
        f"Parsed {len(result.get('parsed_rules', []))} rules and built {len(result.get('checklist', []))} checklist items.",
        {"event": "parse_result"},
    )
    return result


@app.post("/clarify")
def clarify_and_rebuild(req: ClarifyRequest) -> dict[str, Any]:
    session_id = database.ensure_session(req.session_id, title=req.raw_rules[:40] or "Clarification")
    database.log_message(session_id, "user", str(req.clarification_answers), {"event": "clarify_request"})

    state = initial_state(req.raw_rules)
    state.update({
        "parsed_rules": req.parsed_rules,
        "risk_points": req.risk_points,
        "clarification_questions": req.clarification_questions,
        "clarification_answers": req.clarification_answers,
        "checklist": req.checklist,
        "decision_flow": req.decision_flow,
        "counter_examples": req.counter_examples,
        "human_confirmed": True,
        "checklist_history": req.checklist_history,
    })
    result = graph.invoke(state)
    result["session_id"] = session_id

    database.save_rule_run(session_id, "clarify", result)
    database.log_message(session_id, "assistant", "Updated checklist after human clarification.", {"event": "clarify_result"})
    return result


@app.post("/verify")
def verify_product(req: VerifyRequest) -> dict[str, Any]:
    session_id = database.ensure_session(req.session_id, title=req.raw_rules[:40] or "Product verification")
    product_id = database.save_product(session_id, req.product_input)
    database.log_message(
        session_id,
        "user",
        str(req.product_input),
        {"event": "verify_request", "product_id": product_id},
    )

    state = initial_state(req.raw_rules, req.product_input)
    state.update({
        "parsed_rules": req.parsed_rules,
        "risk_points": req.risk_points,
        "clarification_questions": req.clarification_questions,
        "clarification_answers": req.clarification_answers,
        "checklist": req.checklist,
        "decision_flow": req.decision_flow,
        "counter_examples": req.counter_examples,
        "human_confirmed": True,
        "checklist_history": req.checklist_history,
    })
    result = graph.invoke(state)
    result["session_id"] = session_id

    database.save_verification_run(session_id, product_id, req.product_input, result)
    database.save_rule_run(session_id, "verify", result)
    database.log_message(
        session_id,
        "assistant",
        f"Product verification finished with decision: {result.get('final_decision', '')}",
        {"event": "verify_result", "product_id": product_id},
    )
    return result
