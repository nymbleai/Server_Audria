"""
Schemas for Voice Chat
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from uuid import UUID


class InitiateCallRequest(BaseModel):
    """Request to initiate a call"""
    scheduled_call_id: Optional[UUID] = Field(None, description="ID of scheduled call (if from schedule)")
    agent_name: str = Field(..., description="Name of the agent")
    person_id: Optional[UUID] = Field(None, description="ID of the person (e.g., Bianca)")
    voice_id: Optional[str] = Field(None, description="ID of cloned voice from Media Library to use")


class InitiateCallResponse(BaseModel):
    """Response with call link/token"""
    call_id: UUID = Field(..., description="Unique call ID")
    call_token: str = Field(..., description="Temporary token for accessing the call")
    call_link: str = Field(..., description="URL to access the voice chat")
    expires_at: str = Field(..., description="ISO timestamp when the link expires")


class VoiceChatTurnRequest(BaseModel):
    """Request for one turn of voice chat"""
    call_id: UUID = Field(..., description="Call ID")
    call_token: str = Field(..., description="Call token for authentication")
    language: Optional[str] = Field("en", description="Language code")


class VoiceChatTurnResponse(BaseModel):
    """Response from one turn of voice chat"""
    success: bool
    user_text: Optional[str] = None
    agent_text: Optional[str] = None
    agent_audio_url: Optional[str] = None
    error: Optional[str] = None
    timings: Optional[Dict[str, Optional[float]]] = Field(
        None,
        description="Timing information: stt_seconds, openai_seconds, tts_seconds, total_seconds"
    )

