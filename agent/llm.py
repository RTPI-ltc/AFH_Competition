from __future__ import annotations

import json
import os
from typing import Any

DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv()


def llm_available() -> bool:
    return bool(get_api_key())


def get_api_key() -> str:
    if os.getenv("AFH_DISABLE_LLM") == "1":
        return ""
    _load_dotenv_if_available()
    return os.getenv("DEEPSEEK_API_KEY") or DEEPSEEK_API_KEY


def model_status() -> dict[str, str | bool]:
    return {
        "llm_available": llm_available(),
        "model": DEEPSEEK_MODEL if llm_available() else "deterministic-fallback",
        "base_url": DEEPSEEK_BASE_URL if llm_available() else "",
    }


def call_llm(system: str, user: str) -> str:
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError("openai package is not installed") from exc

    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=4096,
        temperature=0.1,
        timeout=30.0,
    )
    return response.choices[0].message.content or ""


def parse_llm_json(raw_response: str) -> dict[str, Any]:
    text = raw_response.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return json.loads(text)
