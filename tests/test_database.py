from __future__ import annotations

import os
import sqlite3

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
        "product_name": "足金项链A",
        "category_l1": "黄金",
        "category_l2": "足金",
        "brand": "云璟珠宝",
        "pricing_model": "weight",
        "weight_g": 12.5,
        "purity": "999",
        "tag_price_rmb": 1299,
        "list_price_rmb": 999,
        "last_30d_min_price": 949,
        "last_90d_min_price": 899,
        "last_365d_min_price": 859,
        "stock": 100,
        "last_90d_sales": 20,
        "review_rate": 96.5,
        "return_rate": 1.5,
        "new_product": True,
        "certificate_ids": ["CERT-TEST-001"],
        "factory_id": "F-TEST",
        "lead_time_days": 7,
        "active_campaigns": ["tmall:test"],
        "status": "在售",
        "notes": "首件商品",
    })
    second_id = database.create_catalog_product({"product_name": "钻石戒指B"})

    first = database.get_catalog_product(first_id)
    second = database.get_catalog_product(second_id)
    assert first["sku_id"] == "SKU000001"
    assert second["sku_id"] == "SKU000002"
    assert first["product_code"] == "SKU000001"
    assert first["category_l1"] == "黄金"
    assert first["category_l2"] == "足金"
    assert first["certificate_ids"] == ["CERT-TEST-001"]
    assert first["active_campaigns"] == ["tmall:test"]
    assert first["new_product"] is True

    database.update_catalog_product(first_id, {
        "product_name": "足金项链A+",
        "category_l1": "黄金",
        "category_l2": "古法金",
        "brand": "云璟珠宝",
        "pricing_model": "weight",
        "weight_g": 13,
        "purity": "999",
        "tag_price_rmb": 1399,
        "list_price_rmb": 1099,
        "last_30d_min_price": 1049,
        "last_90d_min_price": 999,
        "last_365d_min_price": 959,
        "stock": 88,
        "last_90d_sales": 30,
        "review_rate": 97,
        "return_rate": 1.2,
        "new_product": False,
        "certificate_ids": ["CERT-TEST-002"],
        "factory_id": "F-TEST",
        "lead_time_days": 8,
        "active_campaigns": [],
        "status": "待上架",
        "notes": "已更新",
    })
    updated = database.get_catalog_product(first_id)
    assert updated["product_name"] == "足金项链A+"
    assert updated["stock"] == 88
    assert updated["category_l2"] == "古法金"
    assert len(database.list_catalog_products("足金")) == 1

    database.delete_catalog_product(first_id)
    assert database.get_catalog_product(first_id) is None
    assert len(database.list_catalog_products("")) == 1

    os.environ.pop("AFH_DB_PATH", None)


def test_seed_sample_catalog_uses_fictional_sku_brands(tmp_path):
    db_path = tmp_path / "sample_catalog.db"
    os.environ["AFH_DB_PATH"] = str(db_path)

    database.init_db()
    inserted = database.seed_sample_catalog(force=True)
    products = database.list_catalog_products(limit=50)
    fictional_brands = {
        "云璟珠宝",
        "星禾金作",
        "禾光珠宝",
        "珑曜金业",
        "璟澜珠宝",
        "星诺婚饰",
        "曜石切工",
        "翠岚坊",
        "月汐珍珠",
        "铂映工坊",
        "银澈饰品",
    }

    assert inserted == 20
    assert len(products) == 20
    assert sorted(item["sku_id"] for item in products)[0] == "SKU000001"
    assert all(item["sku_id"].startswith("SKU") for item in products)
    assert all(item["product_name"] for item in products)
    assert {item["brand"] for item in products} <= fictional_brands

    os.environ.pop("AFH_DB_PATH", None)


def test_init_db_migrates_legacy_product_catalog(tmp_path):
    db_path = tmp_path / "legacy_catalog.db"
    os.environ["AFH_DB_PATH"] = str(db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE product_catalog (
                id TEXT PRIMARY KEY,
                product_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                brand TEXT NOT NULL DEFAULT '',
                sku TEXT NOT NULL DEFAULT '',
                price REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0,
                sales_30d INTEGER NOT NULL DEFAULT 0,
                rating REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT '在售',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO product_catalog (
                id, product_code, name, category, brand, sku, price,
                stock, sales_30d, rating, status, notes
            )
            VALUES ('legacy-1', 'SP000001', '旧款足金吊坠', '黄金', '云璟珠宝',
                    'OLD-SKU', 999, 12, 8, 95, '在售', 'legacy')
            """
        )

    database.init_db()
    item = database.get_catalog_product("legacy-1")

    assert item["sku_id"] == "SP000001"
    assert item["product_name"] == "旧款足金吊坠"
    assert item["category_l1"] == "黄金"
    assert item["list_price_rmb"] == 999
    assert item["last_90d_sales"] == 8
    assert item["review_rate"] == 95

    os.environ.pop("AFH_DB_PATH", None)
