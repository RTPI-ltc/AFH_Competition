from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field

logger = logging.getLogger("sdk.trace")


@dataclass
class CallTrace:
    model: str
    tools: list[str] | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls_count: int = 0
    error: str | None = None

    @classmethod
    def start(cls, model: str, tools: list[str] | None = None) -> CallTrace:
        return cls(model=model, tools=tools)

    def finish(self, response):
        self.end_time = time.time()
        if hasattr(response, "usage") and response.usage:
            self.input_tokens = response.usage.prompt_tokens or 0
            self.output_tokens = response.usage.completion_tokens or 0
        self._log()

    def finish_stream(self, content: str, tool_calls: list):
        self.end_time = time.time()
        self.tool_calls_count = len(tool_calls)
        self._log()

    def finish_with_error(self, error: str):
        self.end_time = time.time()
        self.error = error
        self._log()

    def _log(self):
        duration = (self.end_time or time.time()) - self.start_time
        logger.info(
            "LLM call: model=%s duration=%.2fs tokens=%d+%d tools=%d error=%s",
            self.model, duration,
            self.input_tokens, self.output_tokens,
            self.tool_calls_count, self.error,
        )

    @property
    def duration_ms(self) -> float:
        return ((self.end_time or time.time()) - self.start_time) * 1000
