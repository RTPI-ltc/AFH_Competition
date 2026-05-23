"""Chat API - SSE streaming endpoint."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..models.schemas import ChatRequest
from ..services.agent import add_message, get_knowledge_content
from ..services.llm import stream_chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """Stream chat response from the Agent via SSE."""
    task_id = request.task_id
    message = request.message.strip()

    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # Save user message
    add_message(task_id, "user", message)

    # Build knowledge context from selected knowledge bases
    knowledge_context = ""
    if request.knowledge_ids:
        contexts = []
        for kb_id in request.knowledge_ids:
            content = get_knowledge_content(kb_id)
            if content:
                contexts.append(content)
        knowledge_context = "\n\n".join(contexts)

    # Stream LLM response
    async def event_stream():
        full_text = ""
        async for chunk in stream_chat(message, knowledge_context):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
