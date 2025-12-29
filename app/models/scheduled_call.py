from sqlalchemy import Column, Text, ForeignKey, DateTime, String, Boolean, Time
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
from .base import Base


class ScheduledCall(Base):
    """Model for storing scheduled calls (single, recurring, or immediate)"""
    __tablename__ = "scheduled_calls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    person_id = Column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_name = Column(String(100), nullable=False)
    call_type = Column(String(20), nullable=False)  # "single", "recurring", "immediate"
    
    # Single call - combined datetime
    scheduled_datetime = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Recurring call - pattern components
    scheduled_time = Column(Time, nullable=True)  # e.g., "09:00"
    recurrence_pattern = Column(JSONB, nullable=True)
    # Structure:
    # {
    #   "days_of_week": ["Monday", "Wednesday", "Friday"],
    #   "start_date": "2025-01-01T00:00:00Z",
    #   "end_date": "2025-12-31T23:59:59Z"
    # }
    
    # Call content (from "CALL ANCHORS" in flowchart)
    leading_reminders = Column(Text, nullable=True)
    leading_topics = Column(Text, nullable=True)
    
    # Memories - stored as JSONB array
    memories = Column(JSONB, nullable=True)  # ["memory1", "memory2"]
    
    # Status tracking
    status = Column(String(20), default="scheduled", nullable=False)  # "scheduled", "completed", "cancelled", "missed", "immediate"
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # For immediate calls
    initiated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    
    # Relationships
    person = relationship("Person", backref="scheduled_calls")

