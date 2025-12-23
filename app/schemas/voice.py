"""
Pydantic schemas for voice processing
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class VoiceUploadRequest(BaseModel):
    """Request schema for voice upload"""
    voice_name: str = Field(..., description="Name for the voice (e.g., 'John', 'Mom')")
    voice_type: str = Field(default="custom", description="Type of voice")
    user_id: Optional[str] = Field(None, description="User/family ID for organization")
    test_text: Optional[str] = Field(None, description="Optional text for test audio generation")


class VoiceResponse(BaseModel):
    """Response schema for voice creation"""
    success: bool
    voice_id: Optional[str] = None
    voice_name: Optional[str] = None
    voice_type: Optional[str] = None
    reference_path: Optional[str] = None
    test_path: Optional[str] = None
    voice_dir: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class VoiceInfo(BaseModel):
    """Voice information schema"""
    voice_id: str
    voice_name: str
    reference_path: Optional[str] = None
    test_path: Optional[str] = None
    created_at: Optional[str] = None


class VoiceListResponse(BaseModel):
    """Response schema for listing voices"""
    success: bool
    voices: List[VoiceInfo] = []
    error: Optional[str] = None
    message: Optional[str] = None


class GenerateSpeechRequest(BaseModel):
    """Request schema for speech generation"""
    text: str = Field(..., description="Text to convert to speech")
    voice_id: str = Field(..., description="Voice ID to use")
    language: str = Field(default="en", description="Language code")
    return_audio_data: bool = Field(default=False, description="Return audio data instead of file path")


class GenerateSpeechResponse(BaseModel):
    """Response schema for speech generation"""
    success: bool
    file_path: Optional[str] = None
    audio_data: Optional[bytes] = None
    message: Optional[str] = None
    error: Optional[str] = None


class VoiceDeleteResponse(BaseModel):
    """Response schema for voice deletion"""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None

