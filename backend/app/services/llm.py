"""LLM service for calling OpenAI-compatible APIs with streaming support."""
import json
from typing import AsyncIterator, Optional
import httpx
from ..core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


SYSTEM_PROMPT = """你是一个电商活动规则执行辅助Agent。你的任务是：
1. 解析用户提供的活动规则文本
2. 提取所有规则条件，生成逐条检查清单
3. 识别潜在风险点和冲突
4. 标注需要人工确认或补充的信息

请直接输出JSON，格式如下：
{
  "summary": "规则概述的一句话总结",
  "checklist": [{"condition": "条件描述", "priority": "high|medium|low", "detail": "具体数值/要求"}],
  "risks": [{"description": "风险描述", "severity": "high|medium"}],
  "needs_clarification": ["需要确认或补充的信息"]
}

注意：
- priority: high=必须满足的核心条件, medium=重要但可协商, low=建议性条件
- severity: high=可能导致活动失败, medium=有影响但可控
- 没有对应内容时返回空数组[]
"""


async def stream_chat(
    message: str,
    knowledge_context: str = "",
    model: Optional[str] = None,
) -> AsyncIterator[str]:
    """Stream chat response from LLM, yielding SSE-formatted data chunks."""
    model_name = model or LLM_MODEL

    user_content = message
    if knowledge_context:
        user_content = f"参考以下知识库内容：\n{knowledge_context}\n\n用户问题：{message}"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{LLM_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            full_text = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_text += content
                            yield _format_sse("text", content)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    # Parse full response for structured data
    structured = _parse_agent_response(full_text)

    # Send checklist
    if structured.get("checklist"):
        yield _format_sse("checklist", structured["checklist"])

    # Send risks
    if structured.get("risks"):
        yield _format_sse("risks", structured["risks"])

    # Send clarifications
    if structured.get("needs_clarification"):
        yield _format_sse("clarification", structured["needs_clarification"])

    yield _format_sse("done", "")


def _format_sse(event_type: str, content) -> str:
    """Format data as SSE event."""
    payload = {"type": event_type}
    if isinstance(content, str):
        payload["content"] = content
    else:
        payload["items"] = content
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _parse_agent_response(text: str) -> dict:
    """Try to parse JSON from LLM response text."""
    # Try to find JSON block
    text = text.strip()
    # Remove markdown code block markers
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        return {
            "summary": "",
            "checklist": [],
            "risks": [],
            "needs_clarification": [],
        }


SUMMARIZE_PROMPT = """你是一个电商活动规则汇总助手。根据以下对话记录，提取关键信息并生成汇总。

请提取：
1. 讨论的活动规则要点
2. AI推荐的商品/品类（如有）
3. 需要关注的检查项
4. 风险点

输出JSON格式：
{
  "title": "汇总标题",
  "rule_points": ["规则要点1", "规则要点2"],
  "recommendations": [{"item": "商品/品类名", "reason": "推荐理由"}],
  "checks": [{"name": "检查项", "status": "通过/需关注"}],
  "risks": ["风险1", "风险2"]
}
如果没有相关内容，对应数组返回空[]。
只输出JSON，不要其他文字。"""


async def summarize_task_messages(messages: list[dict]) -> dict:
    """Summarize task messages into product recommendations."""
    # Build conversation text
    conversation = ""
    for msg in messages:
        role = "用户" if msg["role"] == "user" else "Agent"
        content = msg.get("content", "")
        # Also include checklist/risks from metadata
        meta = msg.get("metadata", {})
        if meta.get("checklist"):
            items = [c.get("condition", "") for c in meta["checklist"]]
            content += "\n[检查清单: " + "; ".join(items) + "]"
        if meta.get("risks"):
            items = [r.get("description", "") for r in meta["risks"]]
            content += "\n[风险: " + "; ".join(items) + "]"
        conversation += f"{role}: {content}\n"

    if not conversation.strip():
        return {"title": "无内容", "rule_points": [], "recommendations": [], "checks": [], "risks": []}

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SUMMARIZE_PROMPT},
            {"role": "user", "content": conversation[:8000]},
        ],
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_agent_response(text)


PROJECT_SUMMARIZE_PROMPT = """你是一个项目汇总助手。根据以下项目中所有子对话记录，生成项目级别的综合汇总。

请提取：
1. 项目讨论的所有活动规则要点
2. AI推荐的所有商品/品类（去重）
3. 关键检查项及其总体状态
4. 所有风险点（去重）

输出JSON格式：
{
  "title": "项目汇总标题",
  "rule_points": ["规则1", "规则2"],
  "recommendations": [{"item": "商品/品类名", "reason": "推荐理由"}],
  "checks": [{"name": "检查项", "status": "通过/需关注"}],
  "risks": ["风险1", "风险2"]
}
只输出JSON。"""


async def summarize_project_tasks(messages: list[dict], task_count: int) -> dict:
    """Summarize all tasks in a project."""
    conversation = f"该项目包含 {task_count} 个对话任务。\n"
    for i, msg in enumerate(messages):
        role = "用户" if msg["role"] == "user" else "Agent"
        content = msg.get("content", "")
        meta = msg.get("metadata", {})
        if meta.get("checklist"):
            items = [c.get("condition", "") for c in meta["checklist"]]
            content += "\n[检查清单: " + "; ".join(items) + "]"
        if meta.get("risks"):
            items = [r.get("description", "") for r in meta["risks"]]
            content += "\n[风险: " + "; ".join(items) + "]"
        conversation += f"{role}: {content}\n"
        if len(conversation) > 12000:
            conversation += "...(内容截断)"
            break

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": PROJECT_SUMMARIZE_PROMPT},
            {"role": "user", "content": conversation},
        ],
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{LLM_BASE_URL}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_agent_response(text)
