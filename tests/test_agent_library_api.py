from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _client() -> TestClient:
    from api.frontend import router

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_agents_endpoint_returns_knowledge_platform_scenarios() -> None:
    response = _client().get("/api/agents")

    assert response.status_code == 200
    agents = response.json()
    assert isinstance(agents, list)
    assert len(agents) == 5

    names = {item["name"] for item in agents}
    assert names == {
        "黑客松助手",
        "课程助教",
        "项目申报助手",
        "企业知识库助手",
        "证据审阅助手",
    }

    scenarios = " ".join(item["scenario"] for item in agents)
    assert "赛事规则" in scenarios
    assert "课程资料" in scenarios
    assert "申报指南" in scenarios
    assert "制度问答" in scenarios
    assert "答案溯源" in scenarios


def test_agents_endpoint_exposes_required_fields_without_ecommerce_terms() -> None:
    agents = _client().get("/api/agents").json()
    required_fields = {
        "id",
        "name",
        "scenario",
        "description",
        "capabilities",
        "suggested_knowledge",
        "tools",
        "output_modes",
        "risk_controls",
    }

    for item in agents:
        assert required_fields <= set(item)
        for field in required_fields:
            assert item[field]
        for field in ("capabilities", "suggested_knowledge", "tools", "output_modes", "risk_controls"):
            assert isinstance(item[field], list)
            assert all(isinstance(value, str) and value.strip() for value in item[field])

    payload_text = json.dumps(agents, ensure_ascii=False)
    assert "电商" not in payload_text
    assert "商品" not in payload_text
    assert "sku" not in payload_text.lower()
