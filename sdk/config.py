from __future__ import annotations

from pydantic_settings import BaseSettings


class SDKConfig(BaseSettings):
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"

    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.1
    TIMEOUT: float = 30.0
    MAX_RETRIES: int = 2

    STREAM_ENABLED: bool = True
    HEARTBEAT_INTERVAL: float = 15.0

    SESSION_DIR: str = "data/sessions"
    SESSION_TTL: int = 1800

    model_config = {"env_file": ".env", "env_prefix": ""}
