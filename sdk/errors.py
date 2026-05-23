from __future__ import annotations

import asyncio
import functools
from enum import Enum

import openai


class ErrorCode(str, Enum):
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTH_FAILED = "auth_failed"
    INVALID_RESPONSE = "invalid_response"
    TOOL_EXECUTION = "tool_execution"
    CONTEXT_TOO_LONG = "context_too_long"


RETRYABLE = {ErrorCode.TIMEOUT, ErrorCode.RATE_LIMIT}


class SDKError(Exception):
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code.value}] {message}")

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE

    @property
    def requires_human(self) -> bool:
        return self.code in {ErrorCode.AUTH_FAILED, ErrorCode.CONTEXT_TOO_LONG}


def classify_openai_error(e: openai.OpenAIError) -> SDKError:
    if isinstance(e, openai.APITimeoutError):
        return SDKError(ErrorCode.TIMEOUT, str(e))
    if isinstance(e, openai.RateLimitError):
        return SDKError(ErrorCode.RATE_LIMIT, str(e))
    if isinstance(e, openai.AuthenticationError):
        return SDKError(ErrorCode.AUTH_FAILED, str(e))
    if isinstance(e, openai.BadRequestError):
        msg = str(e)
        if "context_length" in msg or "max_tokens" in msg:
            return SDKError(ErrorCode.CONTEXT_TOO_LONG, msg)
        return SDKError(ErrorCode.INVALID_RESPONSE, msg)
    if isinstance(e, openai.APIConnectionError):
        return SDKError(ErrorCode.TIMEOUT, str(e))
    return SDKError(ErrorCode.INVALID_RESPONSE, str(e))


def retry_on_transient(max_attempts: int = 3, base_delay: float = 1.0):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except SDKError as e:
                    if not e.retryable or attempt == max_attempts - 1:
                        raise
                    last_error = e
                    await asyncio.sleep(base_delay * (2 ** attempt))
                except openai.OpenAIError as e:
                    sdk_err = classify_openai_error(e)
                    if not sdk_err.retryable or attempt == max_attempts - 1:
                        raise sdk_err from e
                    last_error = sdk_err
                    await asyncio.sleep(base_delay * (2 ** attempt))
            raise last_error
        return wrapper
    return decorator
