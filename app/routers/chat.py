from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.auth import TokenData
from app.core.auth import get_current_user
from openai import AsyncOpenAI
from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.crud.message import message_crud
from uuid import UUID as _UUID
from app.core.message_queue import queue_user_message, queue_assistant_message
from app.core.prompts import SYSTEM_PROMPT_GENERAL_CHAT
import time

router = APIRouter()

@router.post("/message", response_model=ChatResponse)
async def send_chat_message(
    chat_request: ChatRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a chat message (non-streaming version)"""
    try:
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI API not configured"
            )
        
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        
        # Build OpenAI messages with conversation history if available
        messages = [{"role": "system", "content": SYSTEM_PROMPT_GENERAL_CHAT}]
        if chat_request.conversation_id:
            try:
                conv_uuid = _UUID(chat_request.conversation_id)
                history, _ = await message_crud.get_multi(
                    db,
                    filters={"conversation_id": conv_uuid},
                    limit=24,
                    order_by="created_at",
                    order_desc=True
                )
                # Use most recent messages first from DB, then reverse to chronological
                for m in reversed(history):
                    role = getattr(m, "role", None)
                    content = getattr(m, "content", "")
                    if role and content:
                        messages.append({
                            "role": role.value if hasattr(role, "value") else str(role),
                            "content": content
                        })
            except Exception:
                # Ignore history retrieval errors and proceed
                pass

        # Append the current user message
        messages.append({"role": "user", "content": chat_request.message})

        # Create a chat completion
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=500
        )
        
        assistant_message = response.choices[0].message.content
        
        return ChatResponse(
            success=True,
            message=assistant_message,
            conversation_id=chat_request.conversation_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat error: {str(e)}"
        )

@router.get("/status")
async def chat_status():
    """Check chat service status"""
    try:
        return JSONResponse(
            content={
                "success": True,
                "message": "Chat service is running",
                "openai_configured": bool(settings.openai_api_key),
                "websocket_endpoint": "/ws/chat/{user_id}"
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "success": False,
                "error": str(e)
            },
            status_code=500
        ) 