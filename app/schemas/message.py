from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.message import MessageRole

class MessageBase(BaseModel):
    role: MessageRole
    content: str
    model_used: Optional[str] = None

class MessageCreate(MessageBase):
    conversation_id: UUID

class MessageUpdate(BaseModel):
    content: Optional[str] = None
    model_used: Optional[str] = None

class MessageResponse(MessageBase):
    id: UUID
    conversation_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int
    skip: int
    limit: int 