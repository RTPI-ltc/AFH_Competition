from __future__ import annotations

import json
import os
from typing import Any

from agent import database

PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "key_envs": ("DEEPSEEK_API_KEY",),
    },
    "aliyun": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "key_envs": ("ALIYUN_API_KEY", "DASHSCOPE_API_KEY"),
    },
}


def _load_dotenv_if_available() -> None:
    if os.getenv("AFH_SKIP_DOTENV") == "1":
        return
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(override=True)


def llm_available() -> bool:
    return bool(_configured_llm_candidates())


def get_provider() -> str:
    _load_dotenv_if_available()
    provider = os.getenv("LLM_PROVIDER", "deepseek").strip().lower()
    return provider if provider in PROVIDER_DEFAULTS else "deepseek"


def get_api_key() -> str:
    if os.getenv("AFH_DISABLE_LLM") == "1":
        return ""
    _load_dotenv_if_available()
    provider = get_provider()
    for key_name in ("LLM_API_KEY", *PROVIDER_DEFAULTS[provider]["key_envs"]):
        value = os.getenv(key_name)
        if value:
            return value
    return ""


def get_base_url() -> str:
    _load_dotenv_if_available()
    provider = get_provider()
    return os.getenv("LLM_BASE_URL") or PROVIDER_DEFAULTS[provider]["base_url"]


def get_model() -> str:
    _load_dotenv_if_available()
    provider = get_provider()
    return os.getenv("LLM_MODEL") or PROVIDER_DEFAULTS[provider]["model"]


def get_timeout_seconds() -> float:
    _load_dotenv_if_available()
    try:
        return max(10.0, float(os.getenv("LLM_TIMEOUT_SECONDS", "45")))
    except ValueError:
        return 45.0


def get_max_tokens() -> int:
    _load_dotenv_if_available()
    try:
        return max(512, min(4096, int(os.getenv("LLM_MAX_TOKENS", "2048"))))
    except ValueError:
        return 2048


def model_status() -> dict[str, str | bool]:
    candidates = _configured_llm_candidates()
    available = bool(candidates)
    primary = candidates[0] if candidates else {}
    return {
        "llm_available": available,
        "provider": str(primary.get("provider") or get_provider()) if available else "fallback",
        "model": str(primary.get("model") or get_model()) if available else "deterministic-fallback",
        "base_url": str(primary.get("base_url") or get_base_url()) if available else "",
        "config_count": len(candidates),
    }


def _configured_llm_candidates() -> list[dict[str, Any]]:
    if os.getenv("AFH_DISABLE_LLM") == "1":
        return []
    candidates: list[dict[str, Any]] = []
    try:
        for item in database.list_llm_api_configs(include_disabled=False, reveal_key=True):
            if item.get("api_key") and item.get("base_url") and item.get("model"):
                candidates.append({
                    "id": item.get("id"),
                    "name": item.get("name") or "LLM API",
                    "provider": "database",
                    "api_key": item["api_key"],
                    "base_url": item["base_url"],
                    "model": item["model"],
                })
    except Exception:
        pass

    env_key = get_api_key()
    if env_key:
        candidates.append({
            "id": None,
            "name": "Environment",
            "provider": get_provider(),
            "api_key": env_key,
            "base_url": get_base_url(),
            "model": get_model(),
        })
    return candidates


def _call_llm_with_config(config: dict[str, Any], system: str, user: str) -> str:
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("openai package is not installed") from exc

    client = OpenAI(api_key=str(config["api_key"]), base_url=str(config["base_url"]))
    response = client.chat.completions.create(
        model=str(config["model"]),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=get_max_tokens(),
        temperature=0.1,
        timeout=get_timeout_seconds(),
    )
    return response.choices[0].message.content or ""


def call_llm(system: str, user: str) -> str:
    candidates = _configured_llm_candidates()
    if not candidates:
        raise RuntimeError("LLM API key is not configured")

    errors: list[str] = []
    for config in candidates:
        config_id = config.get("id")
        label = f"{config.get('name')}({config.get('model')})"
        try:
            result = _call_llm_with_config(config, system, user)
            if config_id:
                database.update_llm_api_config_status(str(config_id), "ok", "")
            return result
        except Exception as exc:
            error = f"{label}: {exc}"
            errors.append(error)
            if config_id:
                database.update_llm_api_config_status(str(config_id), "error", str(exc))
            continue
    raise RuntimeError("All configured LLM API keys failed: " + " | ".join(errors))


def parse_llm_json(raw_response: str) -> dict[str, Any]:
    text = raw_response.strip()
    if text.startswith("json\n"):
        text = text[5:].strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise
