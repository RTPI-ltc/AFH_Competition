from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "rag_e2e.db"))
    monkeypatch.setenv("AFH_RAG_ROOT", str(tmp_path / "rag_index"))
    monkeypatch.setenv("AFH_DISABLE_LLM", "1")
    monkeypatch.setenv("AFH_DISABLE_RAG_EMBEDDING", "1")
    import api.main as main

    importlib.reload(main)
    return TestClient(main.app)


def test_upload_list_chat_delete_flow(client: TestClient) -> None:
    upload_text = (
        "天猫618大促规则。\n\n"
        "1. 商品需满足近30天销量、好评率与库存门槛。\n"
        "2. 活动价不得高于历史最低价。\n"
        "3. 同品类报名 SKU 数量需控制。"
    )
    upload = client.post(
        "/api/knowledge/upload",
        data={"name": "618 测试规则", "content": upload_text},
    )
    assert upload.status_code == 200
    upload_body = upload.json()
    assert upload_body["id"].startswith("kb_")
    assert upload_body["chunks_added"] >= 1
    kb_id = upload_body["id"]

    listing = client.get("/api/knowledge/personal").json()
    assert any(item["id"] == kb_id and item["chunk_count"] >= 1 for item in listing)

    project = client.post("/api/projects?name=RAG联调").json()
    task = client.post(f"/api/task/new?project_id={project['id']}").json()
    stream = client.post(
        "/api/chat/stream",
        json={
            "task_id": task["task_id"],
            "message": "天猫618 选品门槛是什么？",
            "knowledge_ids": [kb_id],
        },
    )
    assert stream.status_code == 200
    assert "data:" in stream.text

    detail = client.get(f"/api/history/{task['task_id']}").json()
    metadata = next(
        item.get("metadata", {})
        for item in detail["messages"]
        if item["role"] == "agent"
    )
    assert "rag_chunks" in metadata
    assert isinstance(metadata["rag_chunks"], list)

    delete = client.delete(f"/api/knowledge/{kb_id}")
    assert delete.status_code == 200
    after = client.get("/api/knowledge/personal").json()
    assert not any(item["id"] == kb_id for item in after)


def test_upload_rejects_empty_payload(client: TestClient) -> None:
    response = client.post("/api/knowledge/upload", data={"name": "空"})
    assert response.status_code == 400
