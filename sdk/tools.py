from __future__ import annotations

import json
import inspect
from typing import Any, Callable

_REGISTRY: dict[str, dict[str, Any]] = {}


def tool(name: str, description: str, parameters: dict[str, type] | None = None):
    def decorator(func: Callable) -> Callable:
        schema = _build_function_tool_param(name, description, parameters or {})
        _REGISTRY[name] = {
            "schema": schema,
            "handler": func,
        }
        func._tool_name = name
        return func
    return decorator


def _build_function_tool_param(
    name: str, description: str, params: dict[str, type]
) -> dict[str, Any]:
    properties: dict[str, dict] = {}
    required: list[str] = []

    for param_name, param_type in params.items():
        properties[param_name] = _python_type_to_json_schema(param_type)
        required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _python_type_to_json_schema(t: type) -> dict[str, str]:
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    return {"type": mapping.get(t, "string")}


class ToolRegistry:
    def get_schemas(self, tool_names: list[str]) -> list[dict[str, Any]]:
        return [
            _REGISTRY[name]["schema"]
            for name in tool_names
            if name in _REGISTRY
        ]

    def list_registered(self) -> list[str]:
        return list(_REGISTRY.keys())

    async def execute(self, name: str, arguments: str) -> str:
        if name not in _REGISTRY:
            return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)

        handler = _REGISTRY[name]["handler"]
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid arguments: {e}"}, ensure_ascii=False)

        try:
            if inspect.iscoroutinefunction(handler):
                result = await handler(args)
            else:
                result = handler(args)
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
