from __future__ import annotations

import json
import os
from typing import Any

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
    return bool(get_api_key())


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
    available = llm_available()
    return {
        "llm_available": available,
        "provider": get_provider() if available else "fallback",
        "model": get_model() if available else "deterministic-fallback",
        "base_url": get_base_url() if available else "",
    }


def call_llm(system: str, user: str) -> str:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("LLM API key is not configured")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("openai package is not installed") from exc

    client = OpenAI(api_key=api_key, base_url=get_base_url())
    response = client.chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=get_max_tokens(),
        temperature=0.1,
        timeout=get_timeout_seconds(),
    )
    return response.choices[0].message.content or ""


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
