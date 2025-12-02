from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from .base import CRUDBase
from app.models.message import Message, MessageRole
from app.schemas.message import MessageCreate, MessageUpdate
from uuid import UUID

class CRUDMessage(CRUDBase[Message, MessageCreate, MessageUpdate]):
    pass

message_crud = CRUDMessage(Message) 