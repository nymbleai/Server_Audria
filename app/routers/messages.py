from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.exceptions import handle_database_errors, NotFoundError
from app.schemas.auth import TokenData
from app.crud.message import message_crud
from app.crud.conversation import conversation_crud
from app.schemas.message import (
    MessageCreate, 
    MessageUpdate, 
    MessageResponse, 
    MessageListResponse
)
from app.models.message import MessageRole
from typing import Optional
from uuid import UUID

router = APIRouter()

@router.post("/", response_model=MessageResponse)
@handle_database_errors
async def create_message(
    message: MessageCreate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new message"""
    # Verify conversation belongs to user
    await conversation_crud.get_by_user_id(
        db, id=message.conversation_id, user_id=current_user.user_id
    )
    
    return await message_crud.create(db, obj_in=message)

@router.get("/conversation/{conversation_id}", response_model=MessageListResponse)
@handle_database_errors
async def get_conversation_messages(
    conversation_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a specific conversation"""
    # Verify conversation belongs to user
    await conversation_crud.get_by_user_id(
        db, id=conversation_id, user_id=current_user.user_id
    )
    
    messages, total = await message_crud.get_by_field(
        db, field="conversation_id", value=conversation_id, skip=skip, limit=limit
    )
    
    return MessageListResponse(
        messages=messages,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{message_id}", response_model=MessageResponse)
@handle_database_errors
async def get_message(
    message_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific message"""
    return await message_crud.get_by_user_id(
        db, id=message_id, user_id=current_user.user_id
    )

@router.put("/{message_id}", response_model=MessageResponse)
@handle_database_errors
async def update_message(
    message_id: UUID,
    message_update: MessageUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a message"""
    message = await message_crud.get_by_user_id(
        db, id=message_id, user_id=current_user.user_id
    )
    
    return await message_crud.update(
        db, db_obj=message, obj_in=message_update
    )

@router.delete("/{message_id}")
@handle_database_errors
async def delete_message(
    message_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a message"""
    success = await message_crud.soft_delete_by_user_id(
        db, id=message_id, user_id=current_user.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message"
        )
    
    return {"success": True, "message": "Message deleted successfully"}

@router.get("/conversation/{conversation_id}/history")
@handle_database_errors
async def get_conversation_history(
    conversation_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get conversation history for AI context"""
    # Verify conversation belongs to user
    await conversation_crud.get_by_user_id(
        db, id=conversation_id, user_id=current_user.user_id
    )
    
    messages, total = await message_crud.get_by_field(
        db, field="conversation_id", value=conversation_id, limit=limit
    )
    
    # Return in chronological order (reversed)
    return {
        "success": True,
        "messages": list(reversed(messages)),
        "conversation_id": conversation_id,
        "total_messages": total
    } 