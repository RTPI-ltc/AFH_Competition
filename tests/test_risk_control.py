from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "risk_control.db"))
    from agent import database

    database.init_db()
    project_id = database.ensure_project(str(uuid.uuid4()), name="风控测试项目")
    conversation_id = database.ensure_conversation(project_id, str(uuid.uuid4()), title="风控测试对话")
    return database, project_id, conversation_id


def _create_risky_product(database):
    return database.create_catalog_product({
        "sku_id": "SKU900001",
        "product_name": "风控测试金镯",
        "brand": "云璟珠宝",
        "category_l1": "黄金",
        "category_l2": "古法金",
        "pricing_model": "fixed",
        "tag_price_rmb": 1999,
        "list_price_rmb": 2199,
        "last_30d_min_price": 1899,
        "last_90d_min_price": 1799,
        "stock": 8,
        "last_90d_sales": 80,
        "review_rate": 94.5,
        "return_rate": 3.6,
        "certificate_ids": [],
        "active_campaigns": ["tmall:brand_day"],
    })


def test_risk_control_blocks_high_risk_listing_actions(tmp_path, monkeypatch):
    database, project_id, conversation_id = _setup_db(tmp_path, monkeypatch)
    _create_risky_product(database)

    from agent import chat
    from agent import risk_control

    risk_control.RISK_EVENT_DIR = tmp_path / "risk_events"

    def fake_llm(*_args):
        return """
        {
          "reply": "建议上架风控测试金镯，保证升值，活动价9999元。",
          "actions": [
            {
              "type": "add_listing_item",
              "sku_id": "SKU900001",
              "product_name": "风控测试金镯",
              "status": "拟上架",
              "notes": "模型推荐"
            }
          ],
          "recommendations": [
            {
              "sku_id": "SKU900001",
              "product_name": "风控测试金镯",
              "priority": "high",
              "score": 95,
              "reason": "测试"
            }
          ],
          "priority_analysis": [],
          "checklist": [],
          "risks": [],
          "needs_clarification": [],
          "confirmation": {"required": false}
        }
        """

    monkeypatch.setattr(chat, "llm_available", lambda: True)
    monkeypatch.setattr(chat, "call_llm", fake_llm)

    result = chat.handle_chat(project_id, conversation_id, "把风控测试金镯加入上架清单")

    assert result["actions"] == []
    assert result["applied_actions"] == []
    assert database.list_listing_items(project_id) == []
    assert result["risk_control"]["should_block_actions"] is True
    codes = {item["code"] for item in result["risk_control"]["findings"]}
    assert {"promise_pattern", "price_mismatch", "campaign_conflict", "price_protection"} <= codes
    assert result["risks"]
    assert any("风控发现高风险项" in item for item in result["needs_clarification"])
    assert list((tmp_path / "risk_events").glob("*.jsonl"))


def test_risk_control_keeps_medium_risks_without_blocking(tmp_path, monkeypatch):
    database, project_id, conversation_id = _setup_db(tmp_path, monkeypatch)
    database.create_catalog_product({
        "sku_id": "SKU900002",
        "product_name": "证书待补银链",
        "brand": "银澈饰品",
        "category_l1": "银饰",
        "category_l2": "项链",
        "pricing_model": "fixed",
        "tag_price_rmb": 599,
        "list_price_rmb": 599,
        "last_30d_min_price": 599,
        "last_90d_min_price": 599,
        "stock": 100,
        "last_90d_sales": 30,
        "review_rate": 96,
        "return_rate": 1.5,
        "certificate_ids": [],
        "active_campaigns": [],
    })

    from agent import chat
    from agent import risk_control

    risk_control.RISK_EVENT_DIR = tmp_path / "risk_events"
    monkeypatch.setattr(chat, "llm_available", lambda: True)
    monkeypatch.setattr(
        chat,
        "call_llm",
        lambda *_args: """
        {
          "reply": "建议将证书待补银链加入清单，价格599元。",
          "actions": [{"type": "add_listing_item", "sku_id": "SKU900002", "product_name": "证书待补银链", "status": "待确认"}],
          "recommendations": [{"sku_id": "SKU900002", "product_name": "证书待补银链", "priority": "medium", "score": 80, "reason": "价格带合适"}],
          "priority_analysis": [],
          "checklist": [],
          "risks": [],
          "needs_clarification": [],
          "confirmation": {"required": false}
        }
        """,
    )

    result = chat.handle_chat(project_id, conversation_id, "把证书待补银链加入上架清单")

    assert result["applied_actions"]
    assert database.list_listing_items(project_id)
    assert result["risk_control"]["should_block_actions"] is False
    assert "certificate_missing" in {item["code"] for item in result["risk_control"]["findings"]}
