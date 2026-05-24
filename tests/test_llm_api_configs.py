from __future__ import annotations

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_llm_call_tries_database_configs_in_order(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "llm_configs.db"))
    monkeypatch.setenv("AFH_SKIP_DOTENV", "1")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("ALIYUN_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)

    from agent import database, llm

    first_id = database.create_llm_api_config({
        "name": "bad",
        "model": "bad-model",
        "base_url": "https://bad.example/v1",
        "api_key": "bad-key",
        "sort_order": 1,
    })
    second_id = database.create_llm_api_config({
        "name": "good",
        "model": "good-model",
        "base_url": "https://good.example/v1",
        "api_key": "good-key",
        "sort_order": 2,
    })

    calls: list[dict[str, str]] = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append({"model": kwargs["model"]})
            if kwargs["model"] == "bad-model":
                raise RuntimeError("bad key")
            message = types.SimpleNamespace(content="ok from good")
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class FakeOpenAI:
        def __init__(self, api_key: str, base_url: str):
            self.api_key = api_key
            self.base_url = base_url
            self.chat = types.SimpleNamespace(completions=FakeCompletions())

    fake_openai = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    assert llm.llm_available() is True
    assert llm.call_llm("system", "user") == "ok from good"
    assert [item["model"] for item in calls] == ["bad-model", "good-model"]

    first = database.get_llm_api_config(first_id)
    second = database.get_llm_api_config(second_id)
    assert first and first["last_status"] == "error"
    assert second and second["last_status"] == "ok"
    assert "api_key" not in second
    assert second["api_key_masked"] == "********"


def test_llm_config_crud_masks_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("AFH_DB_PATH", str(tmp_path / "llm_config_crud.db"))
    from agent import database

    config_id = database.create_llm_api_config({
        "name": "primary",
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-1234567890",
        "sort_order": 10,
    })
    item = database.get_llm_api_config(config_id)
    assert item
    assert "api_key" not in item
    assert item["api_key_masked"] == "sk-1...7890"

    database.update_llm_api_config(config_id, {"name": "backup", "enabled": False, "sort_order": 20})
    updated = database.get_llm_api_config(config_id)
    assert updated
    assert updated["name"] == "backup"
    assert updated["enabled"] is False
    assert updated["sort_order"] == 20
