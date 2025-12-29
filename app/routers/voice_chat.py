"""
Voice Chat Router
================

Endpoints for initiating calls and managing voice chat sessions.
"""

import secrets
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from pathlib import Path

from app.schemas.voice_chat import (
    InitiateCallRequest,
    InitiateCallResponse,
    VoiceChatTurnRequest,
    VoiceChatTurnResponse
)
from app.core.auth import get_current_user
from app.schemas.auth import TokenData
from app.services.voice_chat_service import get_voice_chat_service
from app.services.supabase_service import supabase_service
from app.core.config import settings
import logging
import tempfile
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for active calls (in production, use Redis or database)
active_calls: Dict[str, Dict] = {}


@router.post(
    "/initiate",
    response_model=InitiateCallResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a voice call",
    tags=["Voice Chat"]
)
async def initiate_call(
    request: InitiateCallRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Initiate a voice call and generate a temporary link.
    
    This creates a call session that can be accessed via the returned link.
    The link expires after 1 hour.
    """
    user_id = str(current_user.user_id)
    
    try:
        # Generate call ID and token
        call_id = uuid.uuid4()
        call_token = secrets.token_urlsafe(32)
        
        # Get scheduled call details if provided
        scheduled_call_data = None
        if request.scheduled_call_id:
            try:
                response = supabase_service.supabase.table('scheduled_calls').select('*').eq('id', str(request.scheduled_call_id)).eq('user_id', user_id).execute()
                if response.data and len(response.data) > 0:
                    scheduled_call_data = response.data[0]
            except Exception as e:
                logger.warning(f"Could not fetch scheduled call data: {e}")
        
        # Store call session
        expires_at = datetime.utcnow() + timedelta(hours=1)
        call_session = {
            "call_id": str(call_id),
            "user_id": user_id,
            "agent_name": request.agent_name,
            "person_id": str(request.person_id) if request.person_id else None,
            "scheduled_call_id": str(request.scheduled_call_id) if request.scheduled_call_id else None,
            "scheduled_call_data": scheduled_call_data,
            "voice_id": request.voice_id,  # Cloned voice from Media Library
            "token": call_token,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "conversation_history": []
        }
        
        active_calls[str(call_id)] = call_session
        
        # Generate call link
        frontend_url = settings.frontend_url.rstrip('/')
        call_link = f"{frontend_url}/voice-chat/{call_id}?token={call_token}"
        
        return InitiateCallResponse(
            call_id=call_id,
            call_token=call_token,
            call_link=call_link,
            expires_at=expires_at.isoformat()
        )
    
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate call: {str(e)}"
        )


@router.post(
    "/turn",
    response_model=VoiceChatTurnResponse,
    summary="Process one turn of voice chat",
    tags=["Voice Chat"]
)
async def process_voice_chat_turn(
    call_id: str = Form(..., description="Call ID"),
    call_token: str = Form(..., description="Call token"),
    audio_file: UploadFile = File(..., description="User's audio recording"),
    language: str = Form("en", description="Language code")
):
    """
    Process one turn of voice chat:
    1. Receives user's audio
    2. Transcribes to text (STT)
    3. Gets AI response (OpenAI)
    4. Generates agent speech (TTS)
    5. Returns agent audio
    
    This is the main loop for voice chat.
    """
    try:
        # Verify call session
        if call_id not in active_calls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call session not found"
            )
        
        call_session = active_calls[call_id]
        
        # Verify token
        if call_session["token"] != call_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid call token"
            )
        
        # Check expiration
        expires_at = datetime.fromisoformat(call_session["expires_at"])
        if datetime.utcnow() > expires_at:
            del active_calls[call_id]
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Call session expired"
            )
        
        # Read audio file
        audio_bytes = await audio_file.read()
        
        # Get voice chat service
        voice_chat_service = get_voice_chat_service()
        
        # Get scheduled call context
        scheduled_call_data = call_session.get("scheduled_call_data")
        leading_topics = scheduled_call_data.get("leading_topics") if scheduled_call_data else None
        leading_reminders = scheduled_call_data.get("leading_reminders") if scheduled_call_data else None
        memories = scheduled_call_data.get("memories") if scheduled_call_data else None
        
        # Process voice chat turn
        result = await voice_chat_service.process_voice_chat_turn(
            user_audio=audio_bytes,
            agent_name=call_session["agent_name"],
            user_id=call_session["user_id"],
            voice_id=call_session.get("voice_id"),  # Use cloned voice from Media Library
            conversation_history=call_session["conversation_history"],
            leading_topics=leading_topics,
            leading_reminders=leading_reminders,
            memories=memories,
            language=language
        )
        
        # Update conversation history
        if result["success"]:
            call_session["conversation_history"].append({
                "role": "user",
                "content": result["user_text"]
            })
            call_session["conversation_history"].append({
                "role": "assistant",
                "content": result["agent_text"]
            })
        
        # Return agent audio file
        if result["success"] and result["agent_audio_path"]:
            audio_path = Path(result["agent_audio_path"])
            if audio_path.exists():
                # Add timing information to response headers for easy access
                headers = {}
                if result.get("timings"):
                    timings = result["timings"]
                    headers["X-STT-Time"] = str(timings.get("stt_seconds", ""))
                    headers["X-OpenAI-Time"] = str(timings.get("openai_seconds", ""))
                    headers["X-TTS-Time"] = str(timings.get("tts_seconds", ""))
                    headers["X-Total-Time"] = str(timings.get("total_seconds", ""))
                    headers["X-Timing-Breakdown"] = (
                        f"STT:{timings.get('stt_seconds', 0)}s|"
                        f"OpenAI:{timings.get('openai_seconds', 0)}s|"
                        f"TTS:{timings.get('tts_seconds', 0)}s|"
                        f"Total:{timings.get('total_seconds', 0)}s"
                    )
                
                # Log timing info for localhost visibility
                if result.get("timings"):
                    timings = result["timings"]
                    logger.info(
                        f"🎯 Response timing - "
                        f"STT: {timings.get('stt_seconds', 0)}s, "
                        f"OpenAI: {timings.get('openai_seconds', 0)}s, "
                        f"TTS: {timings.get('tts_seconds', 0)}s, "
                        f"Total: {timings.get('total_seconds', 0)}s"
                    )
                
                return FileResponse(
                    path=str(audio_path),
                    media_type="audio/wav",
                    filename="agent_response.wav",
                    headers=headers
                )
        
        # If audio generation failed, return JSON response with timing info
        return VoiceChatTurnResponse(
            success=result["success"],
            user_text=result.get("user_text"),
            agent_text=result.get("agent_text"),
            agent_audio_url=None,
            error=result.get("error"),
            timings=result.get("timings")
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing voice chat turn: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process voice chat turn: {str(e)}"
        )


@router.post(
    "/start",
    summary="Start call with agent greeting",
    tags=["Voice Chat"]
)
async def start_call_with_greeting(
    call_id: str = Form(..., description="Call ID"),
    call_token: str = Form(..., description="Call token")
):
    """
    Start the call by having the agent speak first.
    
    The agent will greet the user and ask about the topics/reminders
    that were set when the call was scheduled.
    
    Returns the agent's greeting audio.
    """
    try:
        # Verify call session
        if call_id not in active_calls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call session not found"
            )
        
        call_session = active_calls[call_id]
        
        # Verify token
        if call_session["token"] != call_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid call token"
            )
        
        # Check expiration
        expires_at = datetime.fromisoformat(call_session["expires_at"])
        if datetime.utcnow() > expires_at:
            del active_calls[call_id]
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Call session expired"
            )
        
        # Get scheduled call context
        scheduled_call_data = call_session.get("scheduled_call_data")
        leading_topics = scheduled_call_data.get("leading_topics") if scheduled_call_data else None
        leading_reminders = scheduled_call_data.get("leading_reminders") if scheduled_call_data else None
        memories = scheduled_call_data.get("memories") if scheduled_call_data else None
        agent_name = call_session.get("agent_name", "Agent")
        
        # Generate greeting based on topics/reminders
        greeting_parts = [f"Hello! This is {agent_name}."]
        
        if leading_topics:
            greeting_parts.append(f"I wanted to talk with you about: {leading_topics}")
        elif leading_reminders:
            greeting_parts.append(f"Just a quick reminder: {leading_reminders}")
        elif memories and len(memories) > 0:
            greeting_parts.append(f"I was thinking we could talk about {memories[0]}. How are you feeling today?")
        else:
            greeting_parts.append("How are you doing today? Is there anything you'd like to talk about?")
        
        greeting_text = " ".join(greeting_parts)
        
        # Get voice chat service
        voice_chat_service = get_voice_chat_service()
        
        # Generate greeting audio with timing
        tts_start = time.time()
        agent_audio_path = await voice_chat_service.generate_agent_speech(
            text=greeting_text,
            agent_name=agent_name,
            user_id=call_session["user_id"]
        )
        tts_duration = time.time() - tts_start
        
        logger.info(f"⏱️  Greeting TTS took {tts_duration:.2f}s")
        
        # Add greeting to conversation history
        call_session["conversation_history"].append({
            "role": "assistant",
            "content": greeting_text
        })
        
        # Return audio or JSON with text
        if agent_audio_path and Path(agent_audio_path).exists():
            # Determine media type based on file extension
            file_ext = agent_audio_path.suffix.lower()
            media_type = "audio/mpeg" if file_ext == ".mp3" else "audio/wav"
            
            # Add timing to headers
            headers = {
                "X-TTS-Time": str(round(tts_duration, 2)),
                "X-Greeting-TTS": str(round(tts_duration, 2))
            }
            
            logger.info(f"🎯 Greeting response - TTS: {tts_duration:.2f}s")
            
            return FileResponse(
                path=str(agent_audio_path),
                media_type=media_type,
                filename=f"greeting.{file_ext[1:]}",
                headers=headers
            )
        else:
            # Return JSON with greeting text (audio generation failed)
            return {
                "success": True,
                "agent_text": greeting_text,
                "agent_audio_url": None,
                "error": "Audio generation not available"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting call with greeting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start call: {str(e)}"
        )


@router.get(
    "/{call_id}/status",
    summary="Get call status",
    tags=["Voice Chat"]
)
async def get_call_status(
    call_id: str,
    call_token: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get the status of an active call session.
    """
    if call_id not in active_calls:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call session not found"
        )
    
    call_session = active_calls[call_id]
    
    # Verify token
    if call_session["token"] != call_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid call token"
        )
    
    # Verify user
    if call_session["user_id"] != str(current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Call does not belong to this user"
        )
    
    return {
        "call_id": call_id,
        "agent_name": call_session["agent_name"],
        "created_at": call_session["created_at"],
        "expires_at": call_session["expires_at"],
        "conversation_turns": len(call_session["conversation_history"]) // 2
    }

