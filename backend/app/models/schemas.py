"""Pydantic data models for the application."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ChatRequest(BaseModel):
    task_id: str = Field(..., description="Task/session ID")
    message: str = Field(..., min_length=1, description="User message")
    knowledge_ids: list[str] = Field(default_factory=list, description="Selected knowledge base IDs")


class TaskCreateResponse(BaseModel):
    task_id: str
    created_at: str


class HistoryItem(BaseModel):
    task_id: str
    title: str
    created_at: str
    message_count: int


class HistoryDetail(BaseModel):
    task_id: str
    title: str
    created_at: str
    messages: list[dict]


class KnowledgeItem(BaseModel):
    id: str
    name: str
    type: str  # "official" or "personal"
    description: str = ""
    created_at: str = ""
    file_type: str = ""


class KnowledgeUploadResponse(BaseModel):
    id: str
    name: str
    message: str


class DeleteResponse(BaseModel):
    success: bool
    message: str = ""
