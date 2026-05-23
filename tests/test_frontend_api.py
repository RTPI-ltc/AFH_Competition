from __future__ import annotations

import importlib
import os

from fastapi.testclient import TestClient


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "frontend_api.db"))
    monkeypatch.setenv("AFH_DISABLE_LLM", "1")
    import api.main as main

    importlib.reload(main)
    return TestClient(main.app)


def test_frontend_products_use_sqlite_sku_catalog(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/products")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 20
    assert "黄金" in data["categories"]
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
    assert {item["brand"] for item in data["products"]} <= fictional_brands
    assert all(item["review_rate"] <= 1 for item in data["products"])

    created = client.post(
        "/api/products",
        json={
            "product_name": "足金测试吊坠",
            "brand": "云璟珠宝",
            "category_l1": "黄金",
            "category_l2": "足金",
            "tag_price_rmb": 999,
            "stock": 10,
        },
    )
    assert created.status_code == 200
    product = created.json()["product"]
    assert product["sku_id"].startswith("SKU")

    deleted = client.delete(f"/api/products/{product['sku_id']}")
    assert deleted.status_code == 200


def test_frontend_task_history_and_stream_chat(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    project = client.post("/api/projects?name=前端联调项目").json()
    task = client.post(f"/api/task/new?project_id={project['id']}").json()

    stream = client.post(
        "/api/chat/stream",
        json={"task_id": task["task_id"], "message": "把足金测试吊坠加入上架清单", "knowledge_ids": []},
    )
    assert stream.status_code == 200
    assert "data:" in stream.text
    assert '"type": "done"' in stream.text

    detail = client.get(f"/api/history/{task['task_id']}").json()
    assert detail["task_id"] == task["task_id"]
    assert [message["role"] for message in detail["messages"]] == ["user", "agent"]

    history = client.get(f"/api/history?project_id={project['id']}").json()
    assert history[0]["task_id"] == task["task_id"]

    os.environ.pop("AFH_DB_PATH", None)
    os.environ.pop("AFH_DISABLE_LLM", None)
