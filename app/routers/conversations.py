from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.exceptions import handle_database_errors, NotFoundError
from app.schemas.auth import TokenData
from app.crud.conversation import conversation_crud
from app.schemas.conversation import (
    ConversationCreate, 
    ConversationUpdate, 
    ConversationResponse, 
    ConversationWithMessages,
    ConversationListResponse
)
from typing import Optional
from uuid import UUID

router = APIRouter()

@router.post("/", response_model=ConversationResponse)
@handle_database_errors
async def create_conversation(
    conversation: ConversationCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new conversation"""
    return await conversation_crud.create_with_extra(
        db, obj_in=conversation, extra_data={"user_id": current_user.user_id}
    )

@router.get("/", response_model=ConversationListResponse)
@handle_database_errors
async def get_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversations for the current user"""
    conversations, total = await conversation_crud.get_by_field(
        db, field="user_id", value=current_user.user_id, skip=skip, limit=limit
    )
    
    return ConversationListResponse(
        conversations=conversations,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{conversation_id}", response_model=ConversationResponse)
@handle_database_errors
async def get_conversation(
    conversation_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific conversation"""
    return await conversation_crud.get_by_user_id(
        db, id=conversation_id, user_id=current_user.user_id
    )

@router.get("/{conversation_id}/with-messages", response_model=ConversationWithMessages)
@handle_database_errors
async def get_conversation_with_messages(
    conversation_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a conversation with its messages"""
    return await conversation_crud.get_with_relations(
        db, id=conversation_id, relations=["messages"]
    )

@router.put("/{conversation_id}", response_model=ConversationResponse)
@handle_database_errors
async def update_conversation(
    conversation_id: UUID,
    conversation_update: ConversationUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a conversation"""
    conversation = await conversation_crud.get_by_user_id(
        db, id=conversation_id, user_id=current_user.user_id
    )
    
    return await conversation_crud.update(
        db, db_obj=conversation, obj_in=conversation_update
    )

@router.delete("/{conversation_id}")
@handle_database_errors
async def delete_conversation(
    conversation_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a conversation and all its child objects"""
    success = await conversation_crud.soft_delete_with_cascade(
        db, conversation_id=conversation_id, user_id=current_user.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )
    
    return {"success": True, "message": "Conversation deleted successfully"} 