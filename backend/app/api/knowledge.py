"""Knowledge base API."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from ..models.schemas import KnowledgeItem, KnowledgeUploadResponse, DeleteResponse
from ..services.agent import (
    get_official_knowledge,
    get_personal_knowledge,
    upload_knowledge,
    delete_knowledge,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/official", response_model=list[KnowledgeItem])
async def list_official():
    """Get official knowledge base list."""
    return get_official_knowledge()


@router.get("/personal", response_model=list[KnowledgeItem])
async def list_personal():
    """Get personal knowledge base list."""
    return get_personal_knowledge()


@router.post("/upload", response_model=KnowledgeUploadResponse)
async def upload(
    name: str = Form(...),
    content: str = Form(default=""),
    file: UploadFile = File(default=None),
):
    """Upload a knowledge base (text or file)."""
    kb_content = content

    if file:
        try:
            raw = await file.read()
            kb_content = raw.decode("utf-8")
        except UnicodeDecodeError:
            kb_content = raw.decode("gbk", errors="ignore")

        file_type = file.filename.split(".")[-1] if file.filename else "txt"
    else:
        file_type = "text"

    if not kb_content.strip():
        raise HTTPException(status_code=400, detail="知识库内容不能为空")

    return upload_knowledge(name or "未命名知识库", kb_content, file_type)


@router.delete("/{kb_id}", response_model=DeleteResponse)
async def remove(kb_id: str):
    """Delete a personal knowledge base."""
    if delete_knowledge(kb_id):
        return DeleteResponse(success=True, message="删除成功")
    raise HTTPException(status_code=404, detail="知识库不存在")
