from __future__ import annotations

from agent import llm


def test_aliyun_llm_config_uses_openai_compatible_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AFH_SKIP_DOTENV", "1")
    monkeypatch.delenv("AFH_DISABLE_LLM", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "aliyun")
    monkeypatch.setenv("ALIYUN_API_KEY", "test-key")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("LLM_MODEL", "")

    assert llm.get_provider() == "aliyun"
    assert llm.get_api_key() == "test-key"
    assert llm.get_base_url() == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert llm.get_model() == "qwen-plus"
    assert llm.model_status()["provider"] == "aliyun"


def test_generic_llm_env_overrides_provider_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AFH_SKIP_DOTENV", "1")
    monkeypatch.delenv("AFH_DISABLE_LLM", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "aliyun")
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "custom-model")

    assert llm.get_api_key() == "generic-key"
    assert llm.get_base_url() == "https://example.test/v1"
    assert llm.get_model() == "custom-model"


def test_llm_timeout_and_max_tokens_are_configurable(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AFH_SKIP_DOTENV", "1")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("LLM_MAX_TOKENS", "1024")

    assert llm.get_timeout_seconds() == 60
    assert llm.get_max_tokens() == 1024
