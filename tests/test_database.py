from __future__ import annotations

import os

from agent import database
from agent import chat


def test_database_persists_session_messages_and_product(tmp_path):
    db_path = tmp_path / "afh_test.db"
    os.environ["AFH_DB_PATH"] = str(db_path)

    created_path = database.init_db()
    session_id = database.create_session("test session")
    database.log_message(session_id, "user", "hello", {"kind": "chat"})

    state = {
        "raw_rules": "rules",
        "parsed_rules": [{"rule": "sales>=100"}],
        "risk_points": [],
        "clarification_questions": [],
        "clarification_answers": {},
        "checklist": [{"item": "check sales"}],
        "decision_flow": [],
        "counter_examples": [],
        "final_decision": "通过",
        "verification_result": [{"rule": "sales>=100", "passed": True}],
    }
    database.save_rule_run(session_id, "parse", state)
    product_id = database.save_product(session_id, {"name": "item A", "sales_30d": 120})
    database.save_verification_run(session_id, product_id, {"name": "item A"}, state)

    history = database.get_session_history(session_id)

    assert created_path == db_path
    assert db_path.exists()
    assert history["session"]["id"] == session_id
    assert history["messages"][0]["content"] == "hello"
    assert history["products"][0]["product"]["name"] == "item A"
    assert history["verifications"][0]["final_decision"] == "通过"

    os.environ.pop("AFH_DB_PATH", None)


def test_project_conversation_listing_and_chat_fallback(tmp_path):
    db_path = tmp_path / "workspace.db"
    os.environ["AFH_DB_PATH"] = str(db_path)
    os.environ["AFH_DISABLE_LLM"] = "1"

    database.init_db()
    project_id = database.create_project("618 大促", "测试项目")
    conversation_id = database.create_conversation(project_id, "选品讨论")

    result = chat.handle_chat(project_id, conversation_id, "把足金项链A加入上架清单")
    listing = database.list_listing_items(project_id)
    conversations = database.list_conversations(project_id)
    messages = database.list_conversation_messages(conversation_id)

    assert conversations[0]["id"] == conversation_id
    assert len(messages) == 2
    assert result["applied_actions"]
    assert listing[0]["product_name"]

    database.delete_conversation(conversation_id)
    assert database.list_conversations(project_id) == []

    database.delete_project(project_id)
    assert database.list_projects() == []

    os.environ.pop("AFH_DB_PATH", None)


def test_catalog_product_crud_auto_code(tmp_path):
    db_path = tmp_path / "catalog.db"
    os.environ["AFH_DB_PATH"] = str(db_path)

    database.init_db()
    first_id = database.create_catalog_product({
        "name": "足金项链A",
        "category": "黄金",
        "brand": "AFH",
        "sku": "SKU-A",
        "price": 999,
        "stock": 100,
        "sales_30d": 20,
        "rating": 96.5,
        "status": "在售",
        "notes": "首件商品",
    })
    second_id = database.create_catalog_product({"name": "钻石戒指B"})

    first = database.get_catalog_product(first_id)
    second = database.get_catalog_product(second_id)
    assert first["product_code"] == "SP000001"
    assert second["product_code"] == "SP000002"

    database.update_catalog_product(first_id, {
        "name": "足金项链A+",
        "category": "黄金",
        "brand": "AFH",
        "sku": "SKU-A",
        "price": 1099,
        "stock": 88,
        "sales_30d": 30,
        "rating": 97,
        "status": "待上架",
        "notes": "已更新",
    })
    updated = database.get_catalog_product(first_id)
    assert updated["name"] == "足金项链A+"
    assert updated["stock"] == 88
    assert len(database.list_catalog_products("足金")) == 1

    database.delete_catalog_product(first_id)
    assert database.get_catalog_product(first_id) is None
    assert len(database.list_catalog_products("")) == 1

    os.environ.pop("AFH_DB_PATH", None)
