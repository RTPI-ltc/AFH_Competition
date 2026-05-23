from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sdk.observability import CallTrace


@dataclass
class StreamEvent:
    type: str
    data: Any


class StreamHandler:
    def __init__(self, trace: CallTrace | None = None):
        self._trace = trace
        self._buffer: str = ""
        self._current_tool_args: dict[int, str] = {}
        self._current_tool_names: dict[int, str] = {}
        self._usage: dict | None = None

    def process_chunk(self, chunk) -> StreamEvent | None:
        if not chunk.choices:
            if hasattr(chunk, "usage") and chunk.usage:
                self._usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }
                if self._trace:
                    self._trace.input_tokens = chunk.usage.prompt_tokens or 0
                    self._trace.output_tokens = chunk.usage.completion_tokens or 0
            return None

        choice = chunk.choices[0]
        delta = choice.delta

        if delta and delta.content:
            self._buffer += delta.content
            return StreamEvent(type="text", data=delta.content)

        if delta and delta.tool_calls:
            for tc_delta in delta.tool_calls:
                idx = tc_delta.index
                if tc_delta.function:
                    if tc_delta.function.name:
                        self._current_tool_names[idx] = tc_delta.function.name
                    if tc_delta.function.arguments:
                        self._current_tool_args.setdefault(idx, "")
                        self._current_tool_args[idx] += tc_delta.function.arguments

            return StreamEvent(type="tool_call", data={
                "tools": {
                    idx: {
                        "name": self._current_tool_names.get(idx, ""),
                        "arguments": self._current_tool_args.get(idx, ""),
                    }
                    for idx in self._current_tool_names
                }
            })

        if choice.finish_reason:
            return StreamEvent(type="done", data={
                "content": self._buffer,
                "finish_reason": choice.finish_reason,
                "usage": self._usage,
                "tool_calls": [
                    {"name": self._current_tool_names[idx], "arguments": self._current_tool_args.get(idx, "")}
                    for idx in sorted(self._current_tool_names.keys())
                ] if self._current_tool_names else [],
            })

        return None

    def finalize(self):
        if self._trace:
            self._trace.finish_stream(self._buffer, list(self._current_tool_names.values()))

    @property
    def full_content(self) -> str:
        return self._buffer
