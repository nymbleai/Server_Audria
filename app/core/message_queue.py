"""
In-memory message queue for asynchronous message persistence.

This module provides a simple, efficient queue system for saving chat messages
to the database without blocking WebSocket responses.
"""

import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from uuid import UUID
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud.message import message_crud
from app.schemas.message import MessageCreate
from app.models.message import MessageRole

logger = logging.getLogger(__name__)

@dataclass
class QueuedMessage:
    """Represents a message waiting to be saved to the database"""
    conversation_id: UUID
    role: MessageRole
    content: str
    user_id: UUID
    model_used: Optional[str] = None
    created_at: Optional[datetime] = None
    retry_count: int = 0

class MessageQueue:
    """
    In-memory queue for message persistence.
    
    Provides fast, non-blocking message queuing with background processing
    and automatic retry logic for failed database writes.
    """
    
    def __init__(self, max_retries: int = 3, batch_size: int = 10):
        self.queue: asyncio.Queue[QueuedMessage] = asyncio.Queue()
        self.max_retries = max_retries
        self.batch_size = batch_size
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        
        # Stats for monitoring
        self.stats = {
            "messages_queued": 0,
            "messages_saved": 0,
            "messages_failed": 0,
            "queue_size": 0
        }
    
    async def start(self):
        """Start the background worker"""
        if not self.is_running:
            self.is_running = True
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("🚀 Message queue worker started")
    
    async def stop(self):
        """Stop the background worker and process remaining messages"""
        if self.is_running:
            self.is_running = False
            if self.worker_task:
                await self.worker_task
            
            # Process any remaining messages
            await self._process_remaining_messages()
            logger.info("🛑 Message queue worker stopped")
    
    async def add_message(
        self, 
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        user_id: UUID,
        model_used: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> None:
        """
        Add a message to the queue for async persistence.
        
        This method is non-blocking and returns immediately.
        """
        message = QueuedMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            user_id=user_id,
            model_used=model_used,
            created_at=created_at or datetime.utcnow()
        )
        
        await self.queue.put(message)
        self.stats["messages_queued"] += 1
        self.stats["queue_size"] = self.queue.qsize()
        
        logger.debug(f"📝 Queued {role.value} message for conversation {conversation_id}")
    
    async def _worker(self):
        """Background worker that processes queued messages"""
        logger.info("🔄 Message queue worker started processing")
        
        while self.is_running:
            try:
                # Get message from queue (wait up to 1 second)
                try:
                    message = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # Process the message
                await self._process_message(message)
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"❌ Error in message queue worker: {str(e)}")
                await asyncio.sleep(1)  # Prevent tight error loop
    
    async def _process_message(self, message: QueuedMessage):
        """Process a single message and save to database"""
        try:
            async for db in get_db():
                # Create message in database with preserved created_at for ordering
                message_create = MessageCreate(
                    conversation_id=message.conversation_id,
                    role=message.role,
                    content=message.content,
                    model_used=message.model_used
                )
                saved_message = await message_crud.create_with_extra(
                    db,
                    obj_in=message_create,
                    extra_data={"created_at": message.created_at}
                )
                self.stats["messages_saved"] += 1
                self.stats["queue_size"] = self.queue.qsize()
                
                logger.debug(f"💾 Saved {message.role.value} message {saved_message.id}")
                return
                
        except Exception as e:
            logger.error(f"❌ Failed to save message: {str(e)}")
            
            # Retry logic
            if message.retry_count < self.max_retries:
                message.retry_count += 1
                await self.queue.put(message)  # Re-queue for retry
                logger.info(f"🔄 Retrying message (attempt {message.retry_count})")
            else:
                self.stats["messages_failed"] += 1
                logger.error(f"💀 Message failed after {self.max_retries} retries")
    
    async def _process_remaining_messages(self):
        """Process any remaining messages when shutting down"""
        remaining_count = self.queue.qsize()
        if remaining_count > 0:
            logger.info(f"🧹 Processing {remaining_count} remaining messages...")
            
            while not self.queue.empty():
                try:
                    message = self.queue.get_nowait()
                    await self._process_message(message)
                    self.queue.task_done()
                except asyncio.QueueEmpty:
                    break
                except Exception as e:
                    logger.error(f"❌ Error processing remaining message: {str(e)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            **self.stats,
            "queue_size": self.queue.qsize(),
            "is_running": self.is_running
        }

# Global message queue instance
message_queue = MessageQueue()

# Convenience functions
async def queue_user_message(
    conversation_id: UUID,
    content: str,
    user_id: UUID,
    *,
    created_at: Optional[datetime] = None
) -> None:
    """Queue a user message for persistence"""
    await message_queue.add_message(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content=content,
        user_id=user_id,
        created_at=created_at
    )

async def queue_assistant_message(
    conversation_id: UUID, 
    content: str, 
    user_id: UUID,
    model_used: Optional[str] = "gpt-4o-mini",
    *,
    created_at: Optional[datetime] = None
) -> None:
    """Queue an assistant message for persistence"""
    await message_queue.add_message(
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content=content,
        user_id=user_id,
        model_used=model_used,
        created_at=created_at
    )

async def start_message_queue() -> None:
    """Start the global message queue"""
    await message_queue.start()

async def stop_message_queue() -> None:
    """Stop the global message queue"""
    await message_queue.stop()

def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics"""
    return message_queue.get_stats()
