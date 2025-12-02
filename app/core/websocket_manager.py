from typing import Dict, List
from fastapi import WebSocket
import json
import asyncio
from openai import AsyncOpenAI
from app.core.config import settings
from app.schemas.chat import WebSocketMessage, EventType
from app.core.message_queue import queue_user_message, queue_assistant_message
from app.core.database import get_db
from app.crud.message import message_crud
from uuid import UUID as _UUID, uuid4
import logging
import httpx
from uuid import UUID
from datetime import datetime
import time

from app.core.prompts import SYSTEM_PROMPT_GENERAL_CHAT

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        # Track the currently running streaming task per user for cancellation
        self.user_stream_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        # Best-effort cancel any running stream for this user
        task = self.user_stream_tasks.pop(user_id, None)
        if task and not task.done():
            task.cancel()

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

    async def handle_message(self, user_id: str, message: str):
        try:
            data = json.loads(message)
            
            # Check if it's the new event-based format
            if "event_type" in data:
                await self.handle_event_message(user_id, data)
            else:
                # Backward compatibility: treat as regular chat
                await self.handle_legacy_message(user_id, data)
                
        except Exception as e:
            logger.error(f"Error processing message from user {user_id}: {str(e)}")
            await self.send_personal_message(
                json.dumps({"error": f"Error processing message: {str(e)}"}),
                user_id
            )

    async def handle_event_message(self, user_id: str, data: dict):
        """Handle new event-based message format"""
        try:
            # Validate message format
            ws_message = WebSocketMessage(**data)
            
            if ws_message.event_type == EventType.CHAT:
                await self.handle_chat_event(user_id, ws_message)
            elif ws_message.event_type == EventType.REVISION:
                await self.handle_revision_event(user_id, ws_message)
            else:
                await self.send_personal_message(
                    json.dumps({"error": f"Unsupported event type: {ws_message.event_type}"}),
                    user_id
                )
                
        except ValueError as e:
            await self.send_personal_message(
                json.dumps({"error": f"Invalid message format: {str(e)}"}),
                user_id
            )

    async def handle_chat_event(self, user_id: str, ws_message: WebSocketMessage):
        """Handle regular chat events"""
        if not self.client:
            await self.send_personal_message(
                json.dumps({"error": "OpenAI API not configured"}), 
                user_id
            )
            return

        # If a previous stream is in-flight, cancel and await it so partial
        # response (if any) is persisted BEFORE we queue the new user message.
        await self.cancel_current_stream(user_id)

        # Queue the user message for persistence (timestamp: receive time)
        if ws_message.conversation_id and ws_message.prompt:
            try:
                await queue_user_message(
                    conversation_id=UUID(ws_message.conversation_id),
                    content=ws_message.prompt,
                    user_id=UUID(user_id),
                    created_at=None  # enqueue with current time
                )
            except ValueError as e:
                logger.error(f"Invalid UUID format - user_id: {user_id}, conversation_id: {ws_message.conversation_id}")
            except Exception as e:
                logger.error(f"Failed to queue user message: {str(e)}")

        # Build OpenAI messages with conversation history when available
        messages: List[dict] = []
        try:
            # Always start with the general chat system prompt
            messages.append({"role": "system", "content": SYSTEM_PROMPT_GENERAL_CHAT})

            # Include explicit context as an additional system message
            if ws_message.context:
                messages.append({"role": "system", "content": f"Context: {ws_message.context}"})

            # If we have a conversation_id, pull prior messages (chronological order)
            if ws_message.conversation_id:
                try:
                    conv_uuid = _UUID(ws_message.conversation_id)
                    async for db in get_db():
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
                                messages.append({"role": role.value if hasattr(role, "value") else str(role), "content": content})
                        break
                except Exception as e:
                    logger.warning(f"Failed to load conversation history: {str(e)}")

            # Append the current user prompt last, unless it's already the last historical user message
            if not (len(messages) > 0 and messages[-1].get("role") == "user" and messages[-1].get("content") == ws_message.prompt):
                messages.append({"role": "user", "content": ws_message.prompt})

        except Exception as e:
            logger.error(f"Error building OpenAI messages: {str(e)}")
            # Fallback to minimal prompt
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": ws_message.prompt}
            ]

        await self._start_stream_openai_response(user_id, messages, ws_message.conversation_id)

    async def handle_revision_event(self, user_id: str, ws_message: WebSocketMessage):
        """Handle revision events asynchronously"""
        # Log the revision request
        logger.info(f"🔄 REVISION event received from user {user_id}")
        logger.info(f"   Task ID: {ws_message.task_id}")
        logger.info(f"   User instruction: {ws_message.prompt}")
        logger.info(f"   Clause: {ws_message.context}")
        logger.info(f"   Additional data: {ws_message.data}")
        
        # Validate required fields
        if not ws_message.context:
            await self.send_personal_message(
                json.dumps({
                    "type": "error", 
                    "error": "Context (clause) is required for revision requests",
                    "task_id": ws_message.task_id,
                    "event_type": "REVISION"
                }),
                user_id
            )
            return
        
        # Generate task ID if not provided
        task_id = ws_message.task_id
        if not task_id:
            import uuid
            task_id = str(uuid.uuid4())
        
        # Send immediate acknowledgment with task ID
        await self.send_personal_message(
            json.dumps({
                "type": "revision_accepted", 
                "message": "Revision request accepted and is being processed",
                "task_id": task_id,
                "event_type": "REVISION"
            }),
            user_id
        )
        
        # Process revision asynchronously
        asyncio.create_task(self._process_revision_async(user_id, ws_message, task_id))

    async def _process_revision_async(self, user_id: str, ws_message: WebSocketMessage, task_id: str):
        """Process revision request asynchronously"""
        try:
            # Prepare the revision API request
            revision_payload = {
                "clause": ws_message.context,
                "user_instruction": ws_message.prompt
            }
            
            # Add precedent if provided in data
            if ws_message.data and "precedent" in ws_message.data:
                revision_payload["precedent"] = ws_message.data["precedent"]
            
            logger.info(f"Processing revision async for task {task_id}: {revision_payload}")
            
            # Call the revision API
            revision_url = f"{settings.revision_api_url}/revision/process"
            async with httpx.AsyncClient(timeout=settings.revision_api_timeout) as client:
                response = await client.post(
                    revision_url,
                    json=revision_payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    revision_result = response.json()
                    logger.info(f"Revision API successful for task {task_id}: {revision_result}")
                    
                    # Send the revision result back to user with task ID
                    await self.send_personal_message(
                        json.dumps({
                            "type": "revision_complete",
                            "message": revision_result,
                            "task_id": task_id,
                            "event_type": "REVISION",
                            "success": True
                        }),
                        user_id
                    )
                    
                else:
                    error_msg = f"Revision API failed with status {response.status_code}: {response.text}"
                    logger.error(f"Revision failed for task {task_id}: {error_msg}")
                    
                    await self.send_personal_message(
                        json.dumps({
                            "type": "revision_error",
                            "error": f"Revision processing failed: {error_msg}",
                            "task_id": task_id,
                            "event_type": "REVISION"
                        }),
                        user_id
                    )
                    
        except httpx.TimeoutException:
            error_msg = f"Revision API request timed out for task {task_id}"
            logger.error(error_msg)
            await self.send_personal_message(
                json.dumps({
                    "type": "revision_error",
                    "error": "Revision processing timed out",
                    "task_id": task_id,
                    "event_type": "REVISION"
                }),
                user_id
            )
            
        except Exception as e:
            error_msg = f"Error processing revision for task {task_id}: {str(e)}"
            logger.error(error_msg)
            await self.send_personal_message(
                json.dumps({
                    "type": "revision_error",
                    "error": f"Revision processing failed: {str(e)}",
                    "task_id": task_id,
                    "event_type": "REVISION"
                }),
                user_id
            )

    async def handle_legacy_message(self, user_id: str, data: dict):
        """Handle old message format for backward compatibility"""
        message_text = data.get("message", "")
        conversation_id = data.get("conversation_id")  # Try to get conversation_id from legacy format
        
        if not self.client:
            await self.send_personal_message(
                json.dumps({"error": "OpenAI API not configured"}), 
                user_id
            )
            return

        # Queue the user message for persistence (if conversation_id available)
        if conversation_id and message_text:
            try:
                await queue_user_message(
                    conversation_id=UUID(conversation_id),
                    content=message_text,
                    user_id=UUID(user_id)
                )
            except ValueError as e:
                logger.error(f"Invalid UUID format in legacy message - user_id: {user_id}, conversation_id: {conversation_id}")
            except Exception as e:
                logger.error(f"Failed to queue legacy user message: {str(e)}")

        # Build OpenAI messages including history when possible
        messages: List[dict] = []
        try:
            messages.append({"role": "system", "content": SYSTEM_PROMPT_GENERAL_CHAT})

            if conversation_id:
                try:
                    conv_uuid = _UUID(conversation_id)
                    async for db in get_db():
                        history, _ = await message_crud.get_multi(
                            db,
                            filters={"conversation_id": conv_uuid},
                            limit=24,
                            order_by="created_at",
                            order_desc=True
                        )
                        for m in reversed(history):
                            role = getattr(m, "role", None)
                            content = getattr(m, "content", "")
                            if role and content:
                                messages.append({"role": role.value if hasattr(role, "value") else str(role), "content": content})
                        break
                except Exception as e:
                    logger.warning(f"Failed to load conversation history (legacy): {str(e)}")

            messages.append({"role": "user", "content": message_text})
        except Exception as e:
            logger.error(f"Error building legacy OpenAI messages: {str(e)}")
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": message_text}
            ]
        
        await self._start_stream_openai_response(user_id, messages, conversation_id)

    async def cancel_current_stream(self, user_id: str):
        """Cancel and await any currently running stream for the user.
        Ensures partial assistant content is persisted (handled inside task)."""
        task = self.user_stream_tasks.get(user_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            finally:
                # Clear reference after completion
                self.user_stream_tasks.pop(user_id, None)

    async def _start_stream_openai_response(self, user_id: str, messages: List[dict], conversation_id: str = None):
        """Cancel any in-flight stream for user and start a new one as a background task."""
        # Cancel previous stream if running
        prev = self.user_stream_tasks.get(user_id)
        if prev and not prev.done():
            prev.cancel()
            # Don't await here to avoid blocking; swallow cancellation later inside task
        # Start a new streaming task
        stream_id = str(uuid4())
        task = asyncio.create_task(self._stream_openai_response(user_id, messages, conversation_id, stream_id))
        self.user_stream_tasks[user_id] = task

    async def _stream_openai_response(self, user_id: str, messages: List[dict], conversation_id: str = None, stream_id: str | None = None):
        """Stream response from OpenAI with buffered flushes for smooth UX.
        This method runs inside an asyncio Task so it can be cancelled when a new prompt arrives."""
        # Accumulate partials so that on cancellation we can persist what we have
        full_response = ""
        # Record generation start so DB ordering stays correct
        generation_started_at = time.time()
        try:
            # Send typing indicator
            await self.send_personal_message(
                json.dumps({"type": "typing", "message": "AI is thinking...", "stream_id": stream_id}),
                user_id
            )

            # Get streaming response from OpenAI
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True,
                max_tokens=500
            )

            # Character-by-character throttled streaming (smooth human-like)
            delay = max(0, settings.stream_char_delay_ms) / 1000.0

            async for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response += content
                    for ch in content:
                        await self.send_personal_message(
                            json.dumps({"type": "stream", "content": ch, "stream_id": stream_id}),
                            user_id
                        )
                        if delay:
                            await asyncio.sleep(delay)

            # Send completion signal
            await self.send_personal_message(
                json.dumps({"type": "complete", "message": full_response, "stream_id": stream_id}),
                user_id
            )
            
            # Queue the assistant's response for persistence
            if conversation_id and full_response:
                try:
                    # Preserve created_at around generation start for correct ordering
                    await queue_assistant_message(
                        conversation_id=UUID(conversation_id),
                        content=full_response,
                        user_id=UUID(user_id),
                        model_used="gpt-4o-mini",
                        created_at=datetime.utcfromtimestamp(generation_started_at)
                    )
                except ValueError as e:
                    logger.error(f"Invalid UUID format - user_id: {user_id}, conversation_id: {conversation_id}")
                except Exception as e:
                    logger.error(f"Failed to queue assistant message: {str(e)}")

        except asyncio.CancelledError:
            # Task was cancelled due to a new prompt or disconnect; stop streaming immediately
            logger.info(f"Streaming task cancelled for user {user_id}")
            # Persist partial assistant message if any
            if conversation_id and full_response:
                try:
                    await queue_assistant_message(
                        conversation_id=UUID(conversation_id),
                        content=full_response,
                        user_id=UUID(user_id),
                        model_used="gpt-4o-mini",
                        created_at=datetime.utcfromtimestamp(generation_started_at)
                    )
                except Exception as e:
                    logger.error(f"Failed to persist partial assistant message on cancel: {str(e)}")
            # Optionally notify client; frontend already guards stale events, so keep quiet
            return
        except Exception as e:
            logger.error(f"Error streaming OpenAI response: {str(e)}")
            await self.send_personal_message(
                json.dumps({"error": f"Error getting AI response: {str(e)}"}),
                user_id
            ) 
        finally:
            # Clear completed/cancelled task reference
            current = self.user_stream_tasks.get(user_id)
            if current and current.done():
                self.user_stream_tasks.pop(user_id, None)