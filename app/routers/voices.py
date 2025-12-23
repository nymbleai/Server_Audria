"""
Voice Processing Router
======================

FastAPI endpoints for voice cloning and speech generation.
Integrates with the media library for voice file management.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse

from app.schemas.voice import (
    VoiceUploadRequest,
    VoiceResponse,
    VoiceListResponse,
    VoiceInfo,
    GenerateSpeechRequest,
    GenerateSpeechResponse,
    VoiceDeleteResponse
)
from app.core.auth import get_current_user
from app.schemas.auth import TokenData
from app.services.voice_service import get_voice_processor

router = APIRouter()


@router.post(
    "/upload",
    response_model=VoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a voice file",
    tags=["Voices"]
)
async def upload_voice(
    audio_file: UploadFile = File(..., description="Audio file (WAV, MP3, M4A, etc.)"),
    voice_name: str = Form(..., description="Name for the voice"),
    voice_type: str = Form(default="custom", description="Type of voice"),
    user_id: Optional[str] = Form(None, description="User ID"),
    test_text: Optional[str] = Form(None, description="Optional test text"),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Upload and process a voice file for cloning.
    
    The uploaded audio file will be processed using Coqui TTS to create a cloned voice.
    A test audio file will be generated automatically.
    
    **Supported formats**: WAV, MP3, M4A, OGG, FLAC, AAC
    **Max file size**: 16MB
    **Recommended**: 10-30 seconds of clear, natural speech
    """
    processor = get_voice_processor()
    
    # Use current user's ID if not provided
    if not user_id:
        user_id = str(current_user.user_id)
    
    # Save uploaded file temporarily
    temp_dir = Path(tempfile.gettempdir())
    temp_file_path = temp_dir / f"voice_upload_{os.urandom(8).hex()}_{audio_file.filename}"
    
    try:
        # Save file
        with open(temp_file_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        # Process voice
        result = processor.process_voice_upload(
            audio_file_path=temp_file_path,
            voice_name=voice_name,
            user_id=user_id,
            voice_type=voice_type,
            test_text=test_text
        )
        
        return VoiceResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process voice: {str(e)}"
        )
    finally:
        # Clean up temp file
        if temp_file_path.exists():
            temp_file_path.unlink()


@router.post(
    "/generate",
    response_model=GenerateSpeechResponse,
    summary="Generate speech from text",
    tags=["Voices"]
)
async def generate_speech(
    request: GenerateSpeechRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Generate speech from text using a cloned voice.
    
    The generated audio will be saved to a temporary file and returned.
    """
    processor = get_voice_processor()
    
    # Verify voice belongs to user
    user_id = str(current_user.user_id)
    if not request.voice_id.startswith(f'local_{user_id}_'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice not found or access denied"
        )
    
    # Generate speech
    result = processor.generate_speech(
        text=request.text,
        voice_id=request.voice_id,
        language=request.language,
        return_audio_data=request.return_audio_data
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error', 'Failed to generate speech')
        )
    
    return GenerateSpeechResponse(**result)


@router.get(
    "/generate/{voice_id}",
    summary="Generate speech and return audio file",
    tags=["Voices"]
)
async def generate_speech_file(
    voice_id: str,
    text: str,
    language: str = "en",
    current_user: TokenData = Depends(get_current_user)
):
    """
    Generate speech from text and return the audio file directly.
    
    This endpoint returns the generated audio file as a downloadable WAV file.
    """
    processor = get_voice_processor()
    
    # Verify voice belongs to user
    user_id = str(current_user.user_id)
    if not voice_id.startswith(f'local_{user_id}_'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice not found or access denied"
        )
    
    # Generate speech
    result = processor.generate_speech(
        text=text,
        voice_id=voice_id,
        language=language,
        return_audio_data=False
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error', 'Failed to generate speech')
        )
    
    file_path = Path(result['file_path'])
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Generated audio file not found"
        )
    
    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=f"speech_{voice_id}.wav"
    )


@router.get(
    "",
    response_model=VoiceListResponse,
    summary="List all voices",
    tags=["Voices"]
)
async def list_voices(
    current_user: TokenData = Depends(get_current_user)
):
    """
    List all voices for the current user.
    
    Returns a list of all cloned voices that belong to the authenticated user.
    """
    processor = get_voice_processor()
    user_id = str(current_user.user_id)
    
    result = processor.list_voices(user_id=user_id)
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get('error', 'Failed to list voices')
        )
    
    # Convert to VoiceInfo objects
    voices = [
        VoiceInfo(
            voice_id=voice['voice_id'],
            voice_name=voice['voice_name'],
            reference_path=voice.get('reference_path'),
            test_path=voice.get('test_path'),
            created_at=voice.get('created_at')
        )
        for voice in result['voices']
    ]
    
    return VoiceListResponse(success=True, voices=voices)


@router.get(
    "/{voice_id}",
    summary="Get voice information",
    tags=["Voices"]
)
async def get_voice_info(
    voice_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Get detailed information about a specific voice.
    """
    processor = get_voice_processor()
    
    # Verify voice belongs to user
    user_id = str(current_user.user_id)
    if not voice_id.startswith(f'local_{user_id}_'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice not found or access denied"
        )
    
    result = processor.get_voice_info(voice_id)
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.get('error', 'Voice not found')
        )
    
    return result


@router.delete(
    "/{voice_id}",
    response_model=VoiceDeleteResponse,
    summary="Delete a voice",
    tags=["Voices"]
)
async def delete_voice(
    voice_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Delete a voice and all its associated files.
    
    This action cannot be undone.
    """
    processor = get_voice_processor()
    
    # Verify voice belongs to user
    user_id = str(current_user.user_id)
    if not voice_id.startswith(f'local_{user_id}_'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voice not found or access denied"
        )
    
    result = processor.delete_voice(voice_id)
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error', 'Failed to delete voice')
        )
    
    return VoiceDeleteResponse(**result)

