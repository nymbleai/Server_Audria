"""
Voice Chat Service
==================

Orchestrates the voice chat flow:
1. Agent speaks using TTS (text-to-speech)
2. User speaks, converted to text using STT (speech-to-text)
3. Text sent to OpenAI for response
4. Response converted back to TTS
5. Loop continues
"""

import logging
import time
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import tempfile
import os

from app.services.voice_service import get_voice_processor
from app.services.stt_service import get_stt_service
from app.core.config import settings
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class VoiceChatService:
    """
    Service for managing voice chat conversations
    """
    
    def __init__(self):
        self.voice_processor = get_voice_processor()
        self.stt_service = get_stt_service()
        self.openai_client = None
        
        if settings.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        else:
            logger.warning("OpenAI API key not configured - voice chat will not work")
    
    def _find_cloned_voice(self, user_id: str, voice_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Find a cloned voice from the Media Library for this user
        
        Args:
            user_id: User ID to search for
            voice_name: Optional specific voice name to find
        
        Returns:
            Voice info dict with voice_id and reference_path, or None if not found
        """
        try:
            if not self.voice_processor:
                return None
            
            # List all voices for this user
            voices_result = self.voice_processor.list_voices(user_id=user_id)
            
            if not voices_result.get("success") or not voices_result.get("voices"):
                return None
            
            voices = voices_result["voices"]
            
            if not voices:
                return None
            
            # If a specific voice name is requested, try to find it
            if voice_name:
                voice_name_lower = voice_name.lower()
                for voice in voices:
                    if voice.get("voice_name", "").lower() == voice_name_lower:
                        return voice
            
            # Return the most recent voice (first in list, usually sorted by creation time)
            return voices[0]
        
        except Exception as e:
            logger.error(f"Error finding cloned voice: {e}")
            return None
    
    async def generate_agent_speech(
        self,
        text: str,
        agent_name: str,
        user_id: str,
        voice_id: Optional[str] = None
    ) -> Optional[Path]:
        """
        Generate speech from text using the user's cloned voice from Media Library
        
        Priority:
        1. Uses specified voice_id if provided
        2. Uses any cloned voice from Media Library (with Coqui TTS if available)
        3. Falls back to OpenAI TTS API if no cloned voice found
        
        Args:
            text: Text to convert to speech
            agent_name: Name of the agent (for fallback voice selection)
            user_id: User ID for voice lookup
            voice_id: Optional specific voice ID from Media Library
        
        Returns:
            Path to generated audio file, or None if failed
        """
        try:
            # Step 1: Use specified voice_id or find cloned voice from Media Library
            if voice_id:
                logger.info(f"Using specified voice_id: {voice_id}")
                cloned_voice = {"voice_id": voice_id, "voice_name": "Custom"}
            else:
                cloned_voice = self._find_cloned_voice(user_id)
            
            if cloned_voice:
                voice_id = cloned_voice.get("voice_id")
                voice_name = cloned_voice.get("voice_name", "Unknown")
                logger.info(f"Found cloned voice: {voice_name} (ID: {voice_id})")
                
                # Try to generate speech using the cloned voice
                if voice_id and self.voice_processor:
                    result = self.voice_processor.generate_speech(
                        text=text,
                        voice_id=voice_id,
                        language="en"
                    )
                    
                    if result and result.get("success"):
                        audio_path = result.get("file_path")
                        if audio_path and Path(audio_path).exists():
                            logger.info(f"Generated speech using cloned voice: {voice_name}")
                            return Path(audio_path)
                        
                    logger.warning(f"Failed to generate speech with cloned voice: {result.get('error', 'Unknown error')}")
            else:
                logger.info(f"No cloned voice found for user {user_id}, using fallback TTS")
            
            # Step 2: Fallback to OpenAI TTS API
            if self.openai_client:
                logger.info("Using OpenAI TTS API for speech generation...")
                
                # Choose a voice based on agent name
                voice_map = {
                    "audria": "nova",
                    "scott": "onyx",
                    "lynn": "shimmer",
                    "paul": "echo",
                    "rosemary": "fable",
                    "barbara": "alloy"
                }
                voice = voice_map.get(agent_name.lower(), "nova")
                
                try:
                    response = await self.openai_client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=text
                    )
                    
                    # Save to temp file
                    output_dir = Path(settings.voice_upload_folder) / "temp"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    import uuid
                    output_path = output_dir / f"openai_tts_{uuid.uuid4().hex}.mp3"
                    
                    # Write the audio content to file
                    audio_content = response.content
                    with open(output_path, "wb") as f:
                        f.write(audio_content)
                    
                    return output_path
                    
                except Exception as e:
                    logger.error(f"OpenAI TTS API error: {e}")
                    return None
            
            logger.error("No TTS service available")
            return None
        
        except Exception as e:
            logger.error(f"Error generating agent speech: {e}")
            return None
    
    async def transcribe_user_speech(
        self,
        audio_path: Union[str, Path, bytes],
        language: Optional[str] = "en"
    ) -> Optional[str]:
        """
        Transcribe user's speech to text using OpenAI Whisper API (cloud)
        
        Args:
            audio_path: Path to audio file or audio bytes
            language: Language code (default: "en")
        
        Returns:
            Transcribed text, or None if failed
        """
        try:
            # First try local STT service if available
            if self.stt_service and self.stt_service.is_available():
                if isinstance(audio_path, bytes):
                    result = self.stt_service.transcribe_bytes(
                        audio_path,
                        language=language
                    )
                else:
                    result = self.stt_service.transcribe(
                        audio_path,
                        language=language
                    )
                
                if result and result.get("text"):
                    return result.get("text")
            
            # Fallback to OpenAI Whisper API
            if self.openai_client:
                logger.info("Using OpenAI Whisper API for transcription...")
                
                # If we have bytes, save to temp file
                if isinstance(audio_path, bytes):
                    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                        tmp.write(audio_path)
                        tmp_path = tmp.name
                else:
                    tmp_path = str(audio_path)
                
                try:
                    with open(tmp_path, "rb") as audio_file:
                        transcript = await self.openai_client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_file,
                            language=language
                        )
                    
                    if isinstance(audio_path, bytes):
                        os.unlink(tmp_path)  # Clean up temp file
                    
                    return transcript.text
                except Exception as e:
                    logger.error(f"OpenAI Whisper API error: {e}")
                    if isinstance(audio_path, bytes) and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                    return None
            
            logger.error("No STT service available")
            return None
        
        except Exception as e:
            logger.error(f"Error transcribing user speech: {e}")
            return None
    
    async def get_ai_response(
        self,
        user_text: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        leading_topics: Optional[str] = None,
        leading_reminders: Optional[str] = None,
        memories: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Get AI response from OpenAI
        
        Args:
            user_text: User's transcribed text
            conversation_history: Previous messages in format [{"role": "user/assistant", "content": "..."}]
            system_prompt: System prompt for the conversation
            leading_topics: Topics to discuss
            leading_reminders: Reminders for the agent
            memories: List of memories to reference
        
        Returns:
            AI response text, or None if failed
        """
        if not self.openai_client:
            logger.error("OpenAI client not initialized")
            return None
        
        try:
            # Build messages
            messages = []
            
            # System prompt
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            else:
                # Default system prompt
                messages.append({
                    "role": "system",
                    "content": "You are a friendly and empathetic voice assistant having a natural conversation. Keep responses concise and conversational, suitable for voice interaction."
                })
            
            # Add context from scheduled call
            if leading_topics or leading_reminders or memories:
                context_parts = []
                if leading_topics:
                    context_parts.append(f"Topics to discuss: {leading_topics}")
                if leading_reminders:
                    context_parts.append(f"Reminders: {leading_reminders}")
                if memories:
                    context_parts.append(f"Relevant memories: {', '.join(memories)}")
                
                if context_parts:
                    context_message = "Context for this conversation:\n" + "\n".join(context_parts)
                    messages.append({"role": "system", "content": context_message})
            
            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current user message
            messages.append({"role": "user", "content": user_text})
            
            # Get response from OpenAI
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=200,  # Keep responses short for voice
                temperature=0.7
            )
            
            assistant_message = response.choices[0].message.content
            return assistant_message
        
        except Exception as e:
            logger.error(f"Error getting AI response: {e}")
            return None
    
    async def process_voice_chat_turn(
        self,
        user_audio: Union[str, Path, bytes],
        agent_name: str,
        user_id: str,
        voice_id: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        leading_topics: Optional[str] = None,
        leading_reminders: Optional[str] = None,
        memories: Optional[List[str]] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Process one turn of voice chat:
        1. Transcribe user audio
        2. Get AI response
        3. Generate agent speech using cloned voice from Media Library
        
        Args:
            user_audio: User's audio input
            agent_name: Name of the agent
            user_id: User ID
            voice_id: Optional specific cloned voice ID from Media Library
            conversation_history: Previous conversation messages
            system_prompt: System prompt
            leading_topics: Topics to discuss
            leading_reminders: Reminders
            memories: List of memories
            language: Language code
        
        Returns:
            dict with:
                - user_text: Transcribed user text
                - agent_text: AI response text
                - agent_audio_path: Path to generated audio file
                - success: Whether the turn was successful
        """
        result = {
            "success": False,
            "user_text": None,
            "agent_text": None,
            "agent_audio_path": None,
            "error": None,
            "timings": {
                "stt_seconds": None,
                "openai_seconds": None,
                "tts_seconds": None,
                "total_seconds": None
            }
        }
        
        try:
            # Step 1: Transcribe user speech
            logger.info("Transcribing user speech...")
            stt_start = time.time()
            user_text = await self.transcribe_user_speech(user_audio, language=language)
            stt_duration = time.time() - stt_start
            logger.info(f"STT took {stt_duration:.2f}s")
            
            if not user_text:
                result["error"] = "Failed to transcribe user speech"
                return result
            
            result["user_text"] = user_text
            logger.info(f"User said: {user_text}")
            
            # Step 2: Get AI response
            logger.info("Getting AI response...")
            openai_start = time.time()
            agent_text = await self.get_ai_response(
                user_text=user_text,
                conversation_history=conversation_history,
                system_prompt=system_prompt,
                leading_topics=leading_topics,
                leading_reminders=leading_reminders,
                memories=memories
            )
            openai_duration = time.time() - openai_start
            logger.info(f"OpenAI took {openai_duration:.2f}s")
            
            if not agent_text:
                result["error"] = "Failed to get AI response"
                return result
            
            result["agent_text"] = agent_text
            logger.info(f"Agent will say: {agent_text}")
            
            # Step 3: Generate agent speech using cloned voice from Media Library
            logger.info("Generating agent speech...")
            tts_start = time.time()
            agent_audio_path = await self.generate_agent_speech(
                text=agent_text,
                agent_name=agent_name,
                user_id=user_id,
                voice_id=voice_id
            )
            tts_duration = time.time() - tts_start
            logger.info(f"TTS took {tts_duration:.2f}s")
            
            if not agent_audio_path:
                result["error"] = "Failed to generate agent speech"
                return result
            
            result["agent_audio_path"] = str(agent_audio_path)
            result["success"] = True
            
            # Add timing information to result
            total_duration = stt_duration + openai_duration + tts_duration
            result["timings"] = {
                "stt_seconds": round(stt_duration, 2),
                "openai_seconds": round(openai_duration, 2),
                "tts_seconds": round(tts_duration, 2),
                "total_seconds": round(total_duration, 2)
            }
            
            # Log total timing summary with detailed breakdown
            logger.info(
                f"⏱️  Voice chat turn timing summary - "
                f"STT: {stt_duration:.2f}s, "
                f"OpenAI: {openai_duration:.2f}s, "
                f"TTS: {tts_duration:.2f}s, "
                f"Total: {total_duration:.2f}s"
            )
            logger.info(
                f"📊 Timing breakdown: "
                f"STT={result['timings']['stt_seconds']}s "
                f"({result['timings']['stt_seconds']/total_duration*100:.1f}%), "
                f"OpenAI={result['timings']['openai_seconds']}s "
                f"({result['timings']['openai_seconds']/total_duration*100:.1f}%), "
                f"TTS={result['timings']['tts_seconds']}s "
                f"({result['timings']['tts_seconds']/total_duration*100:.1f}%)"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Error processing voice chat turn: {e}")
            result["error"] = str(e)
            # Calculate total time even on error if we have partial timings
            if result["timings"]["stt_seconds"] is not None or result["timings"]["openai_seconds"] is not None:
                total = sum([
                    result["timings"]["stt_seconds"] or 0,
                    result["timings"]["openai_seconds"] or 0,
                    result["timings"]["tts_seconds"] or 0
                ])
                result["timings"]["total_seconds"] = round(total, 2)
            return result


# Global voice chat service instance
_voice_chat_service: Optional[VoiceChatService] = None


def get_voice_chat_service() -> VoiceChatService:
    """
    Get or create the global voice chat service instance
    
    Returns:
        VoiceChatService instance
    """
    global _voice_chat_service
    
    if _voice_chat_service is None:
        _voice_chat_service = VoiceChatService()
    
    return _voice_chat_service

