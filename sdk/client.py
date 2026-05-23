from __future__ import annotations

import json
from typing import Any, AsyncGenerator

import openai
from openai import AsyncOpenAI

from sdk.config import SDKConfig
from sdk.errors import SDKError, ErrorCode, classify_openai_error, retry_on_transient
from sdk.observability import CallTrace
from sdk.streaming import StreamHandler, StreamEvent
from sdk.tools import ToolRegistry


class LLMClient:
    def __init__(self, config: SDKConfig | None = None):
        self.config = config or SDKConfig()
        if not self.config.LLM_API_KEY:
            raise SDKError(ErrorCode.AUTH_FAILED, "LLM_API_KEY is not configured")

        self._client = AsyncOpenAI(
            api_key=self.config.LLM_API_KEY,
            base_url=self.config.LLM_BASE_URL,
            timeout=self.config.TIMEOUT,
            max_retries=self.config.MAX_RETRIES,
        )
        self._tool_registry = ToolRegistry()

    @retry_on_transient(max_attempts=3)
    async def call(
        self,
        system: str,
        user: str,
        *,
        tools: list[str] | None = None,
        stream: bool | None = None,
        json_mode: bool = False,
    ) -> str | AsyncGenerator[StreamEvent, None]:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        kwargs: dict[str, Any] = {
            "model": self.config.LLM_MODEL,
            "messages": messages,
            "max_tokens": self.config.MAX_TOKENS,
            "temperature": self.config.TEMPERATURE,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
            if "json" not in messages[0]["content"].lower():
                messages[0]["content"] += "\n\nPlease respond in valid JSON format."

        if tools:
            kwargs["tools"] = self._tool_registry.get_schemas(tools)

        use_stream = stream if stream is not None else self.config.STREAM_ENABLED
        trace = CallTrace.start(model=self.config.LLM_MODEL, tools=tools)

        try:
            if use_stream:
                return self._stream_call(kwargs, trace)
            else:
                response = await self._client.chat.completions.create(**kwargs)
                trace.finish(response)
                return response.choices[0].message.content or ""
        except openai.OpenAIError as e:
            sdk_err = classify_openai_error(e)
            trace.finish_with_error(sdk_err.message)
            raise sdk_err from e

    async def _stream_call(
        self, kwargs: dict[str, Any], trace: CallTrace
    ) -> AsyncGenerator[StreamEvent, None]:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}

        stream = await self._client.chat.completions.create(**kwargs)
        handler = StreamHandler(trace)

        async for chunk in stream:
            event = handler.process_chunk(chunk)
            if event:
                yield event

        handler.finalize()

    @retry_on_transient(max_attempts=2)
    async def call_with_tools(
        self,
        system: str,
        user: str,
        tools: list[str],
        *,
        max_rounds: int = 5,
    ) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        tool_schemas = self._tool_registry.get_schemas(tools)
        trace = CallTrace.start(model=self.config.LLM_MODEL, tools=tools)

        try:
            for round_idx in range(max_rounds):
                response = await self._client.chat.completions.create(
                    model=self.config.LLM_MODEL,
                    messages=messages,
                    tools=tool_schemas,
                    max_tokens=self.config.MAX_TOKENS,
                    temperature=self.config.TEMPERATURE,
                )
                msg = response.choices[0].message

                if not msg.tool_calls:
                    trace.finish(response)
                    return {
                        "content": msg.content or "",
                        "rounds": round_idx + 1,
                        "tool_calls_total": trace.tool_calls_count,
                    }

                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                })

                for tc in msg.tool_calls:
                    trace.tool_calls_count += 1
                    result = await self._tool_registry.execute(
                        tc.function.name, tc.function.arguments
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

        except openai.OpenAIError as e:
            sdk_err = classify_openai_error(e)
            trace.finish_with_error(sdk_err.message)
            raise sdk_err from e

        trace.finish_with_error(f"max_rounds={max_rounds} exceeded")
        return {
            "content": messages[-1].get("content", ""),
            "rounds": max_rounds,
            "tool_calls_total": trace.tool_calls_count,
            "truncated": True,
        }
