"""
Voice Processing Service using Coqui TTS
========================================

A complete voice processing service that handles:
- Voice file uploads and validation
- Voice cloning using Coqui TTS
- Speech generation from text
- Voice management (list, delete, validate)

Installation:
    pip install TTS==0.21.3 numpy>=1.21.0

Usage:
    from app.services.voice_service import VoiceProcessor
    
    processor = VoiceProcessor(
        upload_folder="./uploads/voices",
        tts_model="tts_models/multilingual/multi-dataset/xtts_v2"
    )
    
    result = processor.process_voice_upload(
        audio_file_path="path/to/audio.wav",
        voice_name="John",
        user_id="user123"
    )
"""

import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union, List, Any

try:
    from TTS.api import TTS
    TTS_AVAILABLE = True
    print("✅ Coqui TTS module loaded successfully")
except ImportError as e:
    TTS_AVAILABLE = False
    print("⚠️  Coqui TTS not available - voice cloning disabled")
    print(f"   Import error: {e}")
    print("   To enable: pip install TTS==0.21.3 (requires Python 3.9-3.11)")
except Exception as e:
    TTS_AVAILABLE = False
    print(f"⚠️  Coqui TTS initialization failed: {e}")

# Alternative: Use system TTS (macOS say command) for basic speech
import subprocess
import platform

MACOS_TTS_AVAILABLE = platform.system() == "Darwin"

from app.core.config import settings

# Note: TTS library is optional - install with: pip install TTS==0.21.3


class VoiceProcessor:
    """
    Voice processing class using Coqui TTS
    
    Handles voice cloning and speech generation for the media library.
    """
    
    def __init__(
        self,
        upload_folder: Optional[str] = None,
        tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        allowed_extensions: Optional[List[str]] = None,
        max_file_size: int = 16 * 1024 * 1024  # 16MB
    ):
        """
        Initialize the VoiceProcessor
        
        Args:
            upload_folder: Directory to store voice files (default: ./uploads/voices)
            tts_model: Coqui TTS model to use
            allowed_extensions: List of allowed file extensions
            max_file_size: Maximum file size in bytes
        """
        if upload_folder is None:
            upload_folder = os.getenv("VOICE_UPLOAD_FOLDER", "./uploads/voices")
        
        self.upload_folder = Path(upload_folder)
        self.tts_model = tts_model
        self.max_file_size = max_file_size
        
        # Default allowed extensions for audio files
        if allowed_extensions is None:
            self.allowed_extensions = {'wav', 'mp3', 'm4a', 'ogg', 'flac', 'aac'}
        else:
            self.allowed_extensions = set(ext.lower() for ext in allowed_extensions)
        
        # TTS initialization
        self.tts = None
        self.tts_initialized = False
        
        # Create upload directory if it doesn't exist
        self.upload_folder.mkdir(parents=True, exist_ok=True)
        
        # Set Coqui TOS agreement
        os.environ['COQUI_TOS_AGREED'] = '1'
    
    def initialize_tts(self) -> bool:
        """
        Initialize Coqui TTS with the specified model
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        if not TTS_AVAILABLE:
            print("⚠️  Coqui TTS not available - TTS package not installed")
            print("   TTS requires Python 3.9-3.11 (current version may be incompatible)")
            print("   Install with: pip install TTS==0.21.3")
            return False
            
        if self.tts_initialized:
            return True
        
        try:
            print(f"🔄 Initializing Coqui TTS with model: {self.tts_model}")
            print("   (This may take a moment on first run - model will be downloaded)")
            
            # Initialize TTS with the model
            # Note: First run will download the model (~1.5GB)
            self.tts = TTS(self.tts_model)
            self.tts_initialized = True
            print("✅ Coqui TTS initialized successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize Coqui TTS: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            self.tts = None
            self.tts_initialized = False
            return False
    
    def ensure_tts_initialized(self) -> bool:
        """Ensure TTS is initialized before use"""
        if not self.tts_initialized:
            return self.initialize_tts()
        return True
    
    def validate_audio_file(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Validate an audio file before processing
        
        Args:
            file_path: Path to the audio file
            
        Returns:
            dict: Validation result with 'valid' boolean and 'error' message if invalid
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {
                'valid': False,
                'error': f'File not found: {file_path}'
            }
        
        # Check file extension
        extension = file_path.suffix[1:].lower() if file_path.suffix else ''
        if extension not in self.allowed_extensions:
            return {
                'valid': False,
                'error': f'Invalid file type. Allowed: {", ".join(self.allowed_extensions)}'
            }
        
        # Check file size
        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            return {
                'valid': False,
                'error': f'File too large. Max size: {self.max_file_size / (1024*1024):.1f}MB'
            }
        
        if file_size == 0:
            return {
                'valid': False,
                'error': 'File is empty'
            }
        
        return {
            'valid': True,
            'file_size': file_size,
            'extension': extension
        }
    
    def process_voice_upload(
        self,
        audio_file_path: Union[str, Path],
        voice_name: str,
        user_id: Optional[str] = None,
        voice_type: str = "custom",
        test_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an uploaded voice file and create a cloned voice
        
        Args:
            audio_file_path: Path to the uploaded audio file
            voice_name: Name for the voice (e.g., "John", "Mom")
            user_id: Optional user/family ID for organization
            voice_type: Type of voice (default: "custom")
            test_text: Optional text to generate test audio
        
        Returns:
            dict: Result with 'success', 'voice_id', 'reference_path', 'test_path', etc.
        """
        audio_file_path = Path(audio_file_path)
        
        # Validate file
        validation = self.validate_audio_file(audio_file_path)
        if not validation['valid']:
            return {
                'success': False,
                'error': validation['error']
            }
        
        # Initialize TTS if needed
        if not self.ensure_tts_initialized():
            # Fallback: Just save the reference audio without voice cloning
            try:
                timestamp = int(datetime.utcnow().timestamp())
                if user_id:
                    voice_id = f"local_{user_id}_{voice_name}_{timestamp}"
                else:
                    voice_id = f"local_{voice_name}_{timestamp}"
                
                voice_dir = self.upload_folder / voice_id
                voice_dir.mkdir(parents=True, exist_ok=True)
                
                reference_path = voice_dir / 'reference.wav'
                shutil.copy2(audio_file_path, reference_path)
                
                return {
                    'success': True,
                    'voice_id': voice_id,
                    'voice_name': voice_name,
                    'voice_type': voice_type,
                    'reference_path': str(reference_path),
                    'test_path': None,
                    'voice_dir': str(voice_dir),
                    'message': f"Voice '{voice_name}' saved (TTS not available for cloning - using reference audio only)",
                    'tts_available': False
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Failed to save voice: {str(e)}',
                    'message': 'TTS not available and fallback failed'
                }
        
        try:
            # Generate unique voice ID
            timestamp = int(datetime.utcnow().timestamp())
            if user_id:
                voice_id = f"local_{user_id}_{voice_name}_{timestamp}"
            else:
                voice_id = f"local_{voice_name}_{timestamp}"
            
            # Create voice directory
            voice_dir = self.upload_folder / voice_id
            voice_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy reference audio to voice directory
            reference_path = voice_dir / 'reference.wav'
            shutil.copy2(audio_file_path, reference_path)
            
            # Generate test audio
            if test_text is None:
                test_text = f"Hello, this is {voice_name}. I'm ready to help."
            
            test_output_path = voice_dir / 'test.wav'
            
            self.tts.tts_to_file(
                text=test_text,
                speaker_wav=str(reference_path),
                language="en",
                file_path=str(test_output_path)
            )
            
            return {
                'success': True,
                'voice_id': voice_id,
                'voice_name': voice_name,
                'voice_type': voice_type,
                'reference_path': str(reference_path),
                'test_path': str(test_output_path),
                'voice_dir': str(voice_dir),
                'message': f"Voice '{voice_name}' created successfully using Coqui TTS"
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to create voice "{voice_name}"'
            }
    
    def generate_speech(
        self,
        text: str,
        voice_id: str,
        output_path: Optional[Union[str, Path]] = None,
        language: str = "en",
        return_audio_data: bool = False
    ) -> Dict[str, Any]:
        """
        Generate speech from text using a cloned voice
        
        Args:
            text: Text to convert to speech
            voice_id: Voice ID to use (from process_voice_upload)
            output_path: Optional path to save audio file
            language: Language code (default: "en")
            return_audio_data: If True, return audio data instead of file path
        
        Returns:
            dict: Result with 'success', 'file_path' or 'audio_data', etc.
        """
        if not text or not text.strip():
            return {
                'success': False,
                'error': 'Text is required'
            }
        
        if not self.ensure_tts_initialized():
            # Fallback to macOS TTS if available
            if MACOS_TTS_AVAILABLE:
                try:
                    voice_dir = self.upload_folder / voice_id
                    if not voice_dir.exists():
                        return {
                            'success': False,
                            'error': f'Voice {voice_id} not found'
                        }
                    
                    temp_dir = self.upload_folder / 'temp'
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    
                    timestamp = int(datetime.utcnow().timestamp())
                    aiff_path = temp_dir / f"generated_{voice_id}_{timestamp}.aiff"
                    wav_path = temp_dir / f"generated_{voice_id}_{timestamp}.wav"
                    
                    # Use macOS say command to generate AIFF
                    subprocess.run([
                        'say', '-o', str(aiff_path), text
                    ], check=True)
                    
                    # Convert AIFF to WAV using afconvert (macOS built-in)
                    subprocess.run([
                        'afconvert', '-f', 'WAVE', '-d', 'LEI16',
                        str(aiff_path), str(wav_path)
                    ], check=True)
                    
                    # Remove the AIFF file
                    if aiff_path.exists():
                        aiff_path.unlink()
                    
                    return {
                        'success': True,
                        'file_path': str(wav_path),
                        'message': 'Generated using macOS TTS (Coqui TTS not available)',
                        'tts_type': 'macos'
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'macOS TTS failed: {str(e)}',
                        'message': 'Fallback TTS failed'
                    }
            
            return {
                'success': False,
                'error': 'Coqui TTS not available and no fallback available',
                'message': 'TTS system requires Python 3.9-3.11 or macOS'
            }
        
        try:
            # Get reference audio path
            voice_dir = self.upload_folder / voice_id
            reference_path = voice_dir / 'reference.wav'
            
            if not reference_path.exists():
                return {
                    'success': False,
                    'error': 'Reference audio not found',
                    'message': f'Voice {voice_id} reference audio missing'
                }
            
            # Generate speech
            if output_path:
                # Save to file
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                self.tts.tts_to_file(
                    text=text,
                    speaker_wav=str(reference_path),
                    language=language,
                    file_path=str(output_path)
                )
                
                return {
                    'success': True,
                    'file_path': str(output_path),
                    'message': 'Audio generated and saved successfully'
                }
            elif return_audio_data:
                # Return audio data
                audio_data = self.tts.tts(
                    text=text,
                    speaker_wav=str(reference_path),
                    language=language
                )
                
                return {
                    'success': True,
                    'audio_data': audio_data,
                    'message': 'Audio generated successfully'
                }
            else:
                # Generate to temporary file
                temp_dir = self.upload_folder / 'temp'
                temp_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = int(datetime.utcnow().timestamp())
                temp_path = temp_dir / f"generated_{voice_id}_{timestamp}.wav"
                
                self.tts.tts_to_file(
                    text=text,
                    speaker_wav=str(reference_path),
                    language=language,
                    file_path=str(temp_path)
                )
                
                return {
                    'success': True,
                    'file_path': str(temp_path),
                    'message': 'Audio generated successfully'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to generate speech'
            }
    
    def list_voices(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List all available voices
        
        Args:
            user_id: Optional filter by user ID
        
        Returns:
            dict: List of voices with their details
        """
        try:
            voices = []
            
            if not self.upload_folder.exists():
                return {
                    'success': True,
                    'voices': []
                }
            
            for voice_folder in self.upload_folder.iterdir():
                if not voice_folder.is_dir():
                    continue
                
                voice_id = voice_folder.name
                
                # Filter by user_id if provided
                if user_id and not voice_id.startswith(f'local_{user_id}_'):
                    continue
                
                reference_path = voice_folder / 'reference.wav'
                test_path = voice_folder / 'test.wav'
                
                if reference_path.exists():
                    # Extract voice name from folder name
                    parts = voice_id.split('_')
                    if len(parts) >= 3:
                        voice_name = parts[-2]  # Usually the name is second to last
                    else:
                        voice_name = voice_id
                    
                    voices.append({
                        'voice_id': voice_id,
                        'voice_name': voice_name,
                        'reference_path': str(reference_path),
                        'test_path': str(test_path) if test_path.exists() else None,
                        'created_at': datetime.fromtimestamp(voice_folder.stat().st_ctime).isoformat()
                    })
            
            return {
                'success': True,
                'voices': voices
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to list voices'
            }
    
    def delete_voice(self, voice_id: str) -> Dict[str, Any]:
        """
        Delete a voice and all its files
        
        Args:
            voice_id: Voice ID to delete
        
        Returns:
            dict: Deletion result
        """
        try:
            voice_dir = self.upload_folder / voice_id
            
            if voice_dir.exists() and voice_dir.is_dir():
                shutil.rmtree(voice_dir)
                return {
                    'success': True,
                    'message': f'Voice {voice_id} deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Voice {voice_id} not found'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to delete voice {voice_id}'
            }
    
    def get_voice_info(self, voice_id: str) -> Dict[str, Any]:
        """
        Get information about a specific voice
        
        Args:
            voice_id: Voice ID to query
        
        Returns:
            dict: Voice information
        """
        try:
            voice_dir = self.upload_folder / voice_id
            
            if not voice_dir.exists():
                return {
                    'success': False,
                    'error': f'Voice {voice_id} not found'
                }
            
            reference_path = voice_dir / 'reference.wav'
            test_path = voice_dir / 'test.wav'
            
            info = {
                'voice_id': voice_id,
                'voice_dir': str(voice_dir),
                'reference_exists': reference_path.exists(),
                'test_exists': test_path.exists(),
            }
            
            if reference_path.exists():
                info['reference_size'] = reference_path.stat().st_size
                info['reference_created'] = datetime.fromtimestamp(reference_path.stat().st_ctime).isoformat()
            
            if test_path.exists():
                info['test_size'] = test_path.stat().st_size
                info['test_created'] = datetime.fromtimestamp(test_path.stat().st_ctime).isoformat()
            
            return {
                'success': True,
                'voice_info': info
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to get voice info'
            }


# Global instance
_voice_processor: Optional[VoiceProcessor] = None


def get_voice_processor() -> VoiceProcessor:
    """Get or create the global VoiceProcessor instance"""
    global _voice_processor
    if _voice_processor is None:
        _voice_processor = VoiceProcessor()
    return _voice_processor

