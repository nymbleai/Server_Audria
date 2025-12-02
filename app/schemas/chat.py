from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class EventType(str, Enum):
    CHAT = "CHAT"
    REVISION = "REVISION"
    # Add future event types here
    # FEEDBACK = "FEEDBACK"
    # ANALYSIS = "ANALYSIS"

class WebSocketMessage(BaseModel):
    event_type: EventType
    prompt: str
    context: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None
    task_id: Optional[str] = None  # For asynchronous processing

class ChatMessage(BaseModel):
    id: Optional[str] = None
    type: MessageType
    content: str
    timestamp: Optional[datetime] = None
    user_id: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    conversation_id: Optional[str] = None
    error: Optional[str] = None

class StreamResponse(BaseModel):
    type: str  # "stream", "complete", "typing", "error"
    content: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    task_id: Optional[str] = None  # For asynchronous task responses

class ConversationHistory(BaseModel):
    conversation_id: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    user_id: str 