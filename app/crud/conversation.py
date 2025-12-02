from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from sqlalchemy.orm import selectinload
from .base import CRUDBase
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.file import File
from app.schemas.conversation import ConversationCreate, ConversationUpdate
from uuid import UUID
from app.core.exceptions import NotFoundError

class CRUDConversation(CRUDBase[Conversation, ConversationCreate, ConversationUpdate]):
    async def soft_delete_with_cascade(
        self, db: AsyncSession, *, conversation_id: UUID, user_id: str, raise_if_not_found: bool = True
    ) -> bool:
        """Soft delete a conversation and all its child objects"""
        from .message import message_crud
        from .file import file_crud
        
        updated_messages = await message_crud.update_by_field(
            db, field="conversation_id", value=conversation_id, obj_in={"is_deleted": True}
        )
        
        updated_files = await file_crud.update_by_field(
            db, field="conversation_id", value=conversation_id, obj_in={"is_deleted": True}
        )
        
        return await self.soft_delete_by_user_id(
            db, id=conversation_id, user_id=user_id, raise_if_not_found=raise_if_not_found
        )

conversation_crud = CRUDConversation(Conversation) 