from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from .message import MessageResponse

class ConversationBase(BaseModel):
    title: Optional[str] = None

class ConversationCreate(ConversationBase):
    pass

class ConversationUpdate(ConversationBase):
    title: Optional[str] = None

class ConversationResponse(ConversationBase):
    id: UUID
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ConversationWithMessages(ConversationResponse):
    messages: List[MessageResponse] = []

class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int
    skip: int
    limit: int 