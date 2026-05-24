from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "afh_test.db"
    monkeypatch.setenv("AFH_DB_PATH", str(db_path))
    # Force module-level state to re-read env on next call.
    from agent import database

    database.init_db()
    yield db_path


@pytest.fixture()
def project_and_conv(temp_db):
    from agent import database

    project_id = database.ensure_project(str(uuid.uuid4()), name="测试项目")
    conv_id = database.ensure_conversation(project_id, str(uuid.uuid4()), title="测试会话")
    return project_id, conv_id


@pytest.fixture()
def seeded_catalog(temp_db):
    """Insert two products so _build_task_summary can join SKU/category."""
    from agent import database

    p1 = database.create_catalog_product({
        "sku_id": "SKU00001",
        "product_name": "古法金手镯 12g",
        "category_l1": "黄金",
        "category_l2": "手镯",
        "pricing_model": "weight",
        "weight_g": 12,
        "tag_price_rmb": 0,
        "list_price_rmb": 0,
        "stock": 50,
        "last_90d_sales": 30,
    })
    p2 = database.create_catalog_product({
        "sku_id": "SKU00002",
        "product_name": "钻石求婚戒指 30分",
        "category_l1": "钻石",
        "category_l2": "戒指",
        "pricing_model": "fixed",
        "tag_price_rmb": 8888,
        "list_price_rmb": 8888,
        "stock": 10,
        "last_90d_sales": 5,
    })
    return [p1, p2]


def test_confirm_trigger_short_circuits_and_returns_task_summary(
    project_and_conv, seeded_catalog, monkeypatch,
):
    from agent import chat, database

    project_id, conv_id = project_and_conv

    # Pre-populate listing_items so the summary has real content.
    database.add_listing_item(project_id, "古法金手镯 12g", status="拟上架", notes="主推")
    database.add_listing_item(project_id, "钻石求婚戒指 30分", status="待确认", notes="活动冲突待确认")

    # Trip-wire: any LLM call would fail the test.
    def _boom(*_a, **_kw):
        raise AssertionError("LLM must not be called on the confirm-trigger path")

    monkeypatch.setattr(chat, "call_llm", _boom)
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    result = chat.handle_chat(project_id, conv_id, "确认执行上一个上架方案")

    assert result["reply"]
    assert result["reply"].strip() != ""

    summary = result.get("task_summary")
    assert summary is not None
    assert summary["total"] == 2
    names = {item["product_name"] for item in summary["items"]}
    assert names == {"古法金手镯 12g", "钻石求婚戒指 30分"}
    skus = {item["sku_id"] for item in summary["items"]}
    assert skus == {"SKU00001", "SKU00002"}

    # Other cards must be suppressed.
    for key in ("recommendations", "priority_analysis", "checklist", "risks", "needs_clarification"):
        assert result.get(key) == [], f"expected empty {key}, got {result.get(key)!r}"
    assert result.get("confirmation") == {"required": False}


def test_confirm_trigger_writes_previous_recommendations_once(
    project_and_conv, seeded_catalog, monkeypatch,
):
    from agent import chat, database

    project_id, conv_id = project_and_conv
    database.add_conversation_message(
        conv_id,
        "assistant",
        "建议执行这两个商品的上架方案。",
        {
            "event": "chat_reply",
            "recommendations": [
                {"sku_id": "SKU00001", "product_name": "古法金手镯 12g", "reason": "库存和销量适合主推"},
                {"sku_id": "SKU00002", "product_name": "钻石求婚戒指 30分", "reason": "客单价高，适合搭配活动"},
            ],
            "confirmation": {"required": True},
        },
    )

    monkeypatch.setattr(chat, "call_llm", lambda *_a, **_kw: pytest.fail("LLM called"))
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    first = chat.handle_chat(project_id, conv_id, "确认执行上一个上架方案")
    second = chat.handle_chat(project_id, conv_id, "确认执行上一个上架方案")

    after = database.list_listing_items(project_id)
    assert len(after) == 2
    assert first["task_summary"]["total"] == 2
    assert len(first["applied_actions"]) == 2
    assert second["task_summary"]["total"] == 2
    assert second["applied_actions"] == []


def test_confirm_trigger_empty_listing_returns_friendly_reply(
    project_and_conv, monkeypatch,
):
    from agent import chat

    project_id, conv_id = project_and_conv

    monkeypatch.setattr(chat, "call_llm", lambda *_a, **_kw: pytest.fail("LLM called"))
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    result = chat.handle_chat(project_id, conv_id, "确认执行上一个上架方案")

    assert result["task_summary"]["total"] == 0
    assert result["task_summary"]["items"] == []
    assert "为空" in result["reply"]


def test_non_trigger_message_still_goes_through_llm(project_and_conv, monkeypatch):
    from agent import chat

    project_id, conv_id = project_and_conv

    called = {"n": 0}

    def _fake_llm(*_a, **_kw):
        called["n"] += 1
        return '{"reply": "fake reply", "actions": [], "recommendations": []}'

    monkeypatch.setattr(chat, "call_llm", _fake_llm)
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    chat.handle_chat(project_id, conv_id, "确认方案")  # different text
    chat.handle_chat(project_id, conv_id, "你好")

    assert called["n"] == 2, "non-trigger messages must still call LLM"


def test_confirm_trigger_strips_whitespace(project_and_conv, monkeypatch):
    from agent import chat

    project_id, conv_id = project_and_conv

    monkeypatch.setattr(chat, "call_llm", lambda *_a, **_kw: pytest.fail("LLM called"))
    monkeypatch.setattr(chat, "llm_available", lambda: True)

    result = chat.handle_chat(project_id, conv_id, "  确认执行上一个上架方案  ")
    assert result.get("task_summary") is not None
