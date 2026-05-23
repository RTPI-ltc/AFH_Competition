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
    assert task["project_id"] == project["id"]
    immediate_history = client.get(f"/api/history?project_id={project['id']}").json()
    assert immediate_history[0]["task_id"] == task["task_id"]
    assert immediate_history[0]["title"] == "新任务"

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
    assert history[0]["title"] == "把足金测试吊坠加入上架清单"

    os.environ.pop("AFH_DB_PATH", None)
    os.environ.pop("AFH_DISABLE_LLM", None)


def test_frontend_recommendation_flow_waits_for_confirmation(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    import agent.chat as chat_module

    def fake_call_llm(system: str, user: str) -> str:
        if "确认执行上一个上架方案" in user:
            return """
            {
              "reply": "已确认方案，按模型结果写入上架清单，状态为拟上架。",
              "actions": [
                {
                  "type": "add_listing_item",
                  "product_name": "5G黄金小蛮腰耳钉1.2g",
                  "status": "拟上架",
                  "notes": "用户确认模型方案",
                  "details": {"source": "model_confirmed"}
                }
              ],
              "recommendations": [],
              "priority_analysis": [],
              "checklist": [],
              "risks": [],
              "needs_clarification": [],
              "confirmation": {"required": false, "status": "confirmed"}
            }
            """
        return """
        {
          "reply": "我基于商品库推荐 5G黄金小蛮腰耳钉1.2g 优先上架。",
          "actions": [],
          "recommendations": [
            {
              "sku_id": "SKU000006",
              "product_name": "5G黄金小蛮腰耳钉1.2g",
              "priority": "high",
              "score": 91,
              "reason": "模型判断库存、销量、评价较优"
            }
          ],
          "priority_analysis": ["模型认为该 SKU 优先级最高。"],
          "checklist": [{"condition": "确认活动价", "priority": "high", "detail": "模型要求人工确认价格口径。"}],
          "risks": [],
          "needs_clarification": ["活动价是否低于价格保护线。"],
          "confirmation": {"required": true, "question": "是否确认？", "confirm_label": "确认方案", "revise_label": "继续调整"}
        }
        """

    monkeypatch.setattr(chat_module, "llm_available", lambda: True)
    monkeypatch.setattr(chat_module, "call_llm", fake_call_llm)

    project = client.post("/api/projects?name=618选品项目").json()
    task = client.post(f"/api/task/new?project_id={project['id']}").json()

    stream = client.post(
        "/api/chat/stream",
        json={"task_id": task["task_id"], "message": "推荐我上架什么商品", "knowledge_ids": []},
    )
    assert stream.status_code == 200
    assert '"type": "recommendations"' in stream.text
    assert '"type": "confirmation"' in stream.text
    assert "请提供商品" not in stream.text

    detail = client.get(f"/api/history/{task['task_id']}").json()
    metadata = detail["messages"][-1]["metadata"]
    assert metadata["recommendations"]
    assert metadata["checklist"]
    assert metadata["needs_clarification"]
    assert metadata["confirmation"]["required"] is True

    listing_before = client.get(f"/projects/{project['id']}/listing-items").json()
    assert listing_before["items"] == []

    confirmed = client.post(
        "/api/chat/stream",
        json={"task_id": task["task_id"], "message": "确认执行上一个上架方案", "knowledge_ids": []},
    )
    assert confirmed.status_code == 200
    assert "拟上架" in confirmed.text

    listing_after = client.get(f"/projects/{project['id']}/listing-items").json()
    assert listing_after["items"]
    assert {item["status"] for item in listing_after["items"]} == {"拟上架"}

    summary = client.post(f"/api/projects/{project['id']}/summarize").json()
    assert summary["final_selection"]
    assert summary["final_selection"][0]["product_name"] == "5G黄金小蛮腰耳钉1.2g"
    assert summary["selection_reasons"]
    assert summary["attention_items"]
    assert summary["confirmed_listing"]
    assert summary["confirmed_listing"][0]["status"] == "拟上架"

    os.environ.pop("AFH_DB_PATH", None)
    os.environ.pop("AFH_DISABLE_LLM", None)


def test_frontend_lightweight_chat_uses_model(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    import agent.chat as chat_module

    monkeypatch.setattr(chat_module, "llm_available", lambda: True)
    monkeypatch.setattr(
        chat_module,
        "call_llm",
        lambda system, user: """
        {
          "reply": "模型回答：你好，我在。",
          "actions": [],
          "recommendations": [],
          "priority_analysis": [],
          "checklist": [],
          "risks": [],
          "needs_clarification": [],
          "confirmation": {"required": false}
        }
        """,
    )

    task = client.post("/api/task/new?project_id=default").json()
    stream = client.post(
        "/api/chat/stream",
        json={"task_id": task["task_id"], "message": "你好", "knowledge_ids": []},
    )

    assert stream.status_code == 200
    assert "模型回答：你好，我在。" in stream.text
    assert '"type": "done"' in stream.text
    assert "模型未配置" not in stream.text

    os.environ.pop("AFH_DB_PATH", None)
    os.environ.pop("AFH_DISABLE_LLM", None)


def test_frontend_knowledge_upload_accepts_multimodal_files(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/knowledge/upload",
        data={"name": "多模态知识库", "content": ""},
        files={
            "files": (
                "sample.png",
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
                "image/png",
            )
        },
    )
    assert response.status_code == 200
    knowledge_id = response.json()["id"]

    personal = client.get("/api/knowledge/personal").json()
    item = next(item for item in personal if item["id"] == knowledge_id)
    assert item["file_type"] == "multimodal"
    assert "多模态素材" in item["description"]

    os.environ.pop("AFH_DB_PATH", None)
    os.environ.pop("AFH_DISABLE_LLM", None)


def test_frontend_knowledge_upload_extracts_pdf_text(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    pdf = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >> endobj
4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
5 0 obj << /Length 44 >> stream
BT /F1 24 Tf 100 700 Td (PDF upload text) Tj ET
endstream endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000241 00000 n
0000000311 00000 n
trailer << /Root 1 0 R /Size 6 >>
startxref
405
%%EOF
"""

    response = client.post(
        "/api/knowledge/upload",
        data={"name": "PDF规则", "content": ""},
        files={"files": ("rules.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 200
    knowledge_id = response.json()["id"]

    assert knowledge_id
    item = next(item for item in client.get("/api/knowledge/personal").json() if item["id"] == knowledge_id)
    assert item["file_type"] == "multimodal"
    assert "已抽取文本" in item["description"]

    os.environ.pop("AFH_DB_PATH", None)
    os.environ.pop("AFH_DISABLE_LLM", None)
