"""History & Project API."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from ..models.schemas import HistoryItem, HistoryDetail, DeleteResponse, TaskCreateResponse
from ..services.agent import (
    create_task,
    get_history,
    get_history_detail,
    delete_task,
    add_message,
    rename_task,
    create_project,
    get_projects,
    rename_project,
)

router = APIRouter(prefix="/api", tags=["history"])


class SaveMessageRequest(BaseModel):
    role: str
    content: str
    msg_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")


# --- Messages ---

@router.post("/history/{task_id}/message")
async def save_message(task_id: str, body: SaveMessageRequest):
    ok = add_message(task_id, body.role, body.content, body.msg_metadata)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True}


# --- Tasks ---

@router.post("/task/new")
async def new_task(project_id: str = Query(default="default")):
    return create_task(project_id)


@router.get("/history")
async def list_history(project_id: str = Query(default=None)):
    return get_history(project_id if project_id else None)


@router.get("/history/{task_id}")
async def get_task_history(task_id: str):
    detail = get_history_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="任务不存在")
    return detail


@router.delete("/history/{task_id}")
async def remove_history(task_id: str):
    if delete_task(task_id):
        return DeleteResponse(success=True, message="删除成功")
    raise HTTPException(status_code=404, detail="任务不存在")


# --- Projects ---

@router.get("/projects")
async def list_projects():
    return get_projects()


@router.post("/projects")
async def new_project(name: str = Query(default="新项目")):
    return create_project(name)


@router.put("/projects/{project_id}/rename")
async def rename_project_route(project_id: str, name: str = Query(...)):
    if not rename_project(project_id, name):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"success": True}


@router.put("/history/{task_id}/rename")
async def rename_task_route(task_id: str, name: str = Query(...)):
    if not rename_task(task_id, name):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True}


# --- Summarize ---

@router.post("/history/{task_id}/summarize")
async def summarize_task(task_id: str):
    from ..services.llm import summarize_task_messages
    detail = get_history_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="任务不存在")
    summary = await summarize_task_messages(detail["messages"])
    return summary
