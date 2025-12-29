"""
Speech-to-Text Service using OpenAI Whisper
===========================================

Service for converting audio to text using OpenAI's Whisper model.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, Union
import logging

try:
    import whisper
    WHISPER_AVAILABLE = True
    print("✅ OpenAI Whisper module loaded successfully")
except ImportError as e:
    WHISPER_AVAILABLE = False
    print("⚠️  OpenAI Whisper not available - speech-to-text disabled")
    print(f"   Import error: {e}")
    print("   To enable: pip install openai-whisper")

logger = logging.getLogger(__name__)


class STTService:
    """
    Speech-to-Text service using OpenAI Whisper
    """
    
    def __init__(self, model_name: str = "base"):
        """
        Initialize the STT service
        
        Args:
            model_name: Whisper model to use (tiny, base, small, medium, large)
                       Default: "base" (good balance of speed and accuracy)
        """
        self.model_name = model_name
        self.model = None
        self.model_loaded = False
        
        if WHISPER_AVAILABLE:
            try:
                logger.info(f"Loading Whisper model: {model_name}")
                self.model = whisper.load_model(model_name)
                self.model_loaded = True
                logger.info("✅ Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                self.model_loaded = False
        else:
            logger.warning("Whisper not available - STT functionality disabled")
    
    def is_available(self) -> bool:
        """Check if the STT service is available and ready to use"""
        return WHISPER_AVAILABLE and self.model_loaded
    
    def transcribe(
        self,
        audio_path: Union[str, Path],
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> dict:
        """
        Transcribe audio file to text
        
        Args:
            audio_path: Path to audio file
            language: Language code (e.g., "en", "es", "fr"). If None, auto-detect
            task: "transcribe" or "translate"
        
        Returns:
            dict with keys:
                - text: Transcribed text
                - language: Detected language
                - segments: List of segments with timing info
        """
        if not WHISPER_AVAILABLE or not self.model_loaded:
            raise RuntimeError("Whisper is not available or model not loaded")
        
        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")
            
            logger.info(f"Transcribing audio: {audio_path}")
            
            # Transcribe with Whisper
            result = self.model.transcribe(
                str(audio_path),
                language=language,
                task=task
            )
            
            logger.info(f"Transcription completed. Language: {result.get('language', 'unknown')}")
            
            return {
                "text": result.get("text", "").strip(),
                "language": result.get("language", "unknown"),
                "segments": result.get("segments", [])
            }
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise
    
    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> dict:
        """
        Transcribe audio from bytes
        
        Args:
            audio_bytes: Audio file as bytes
            language: Language code (e.g., "en", "es", "fr"). If None, auto-detect
            task: "transcribe" or "translate"
        
        Returns:
            dict with transcribed text and metadata
        """
        if not WHISPER_AVAILABLE or not self.model_loaded:
            raise RuntimeError("Whisper is not available or model not loaded")
        
        # Save bytes to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name
        
        try:
            result = self.transcribe(tmp_path, language=language, task=task)
            return result
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# Global STT service instance
_stt_service: Optional[STTService] = None


def get_stt_service(model_name: str = "base") -> STTService:
    """
    Get or create the global STT service instance
    
    Args:
        model_name: Whisper model to use
    
    Returns:
        STTService instance
    """
    global _stt_service
    
    if _stt_service is None:
        _stt_service = STTService(model_name=model_name)
    
    return _stt_service

