from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, time, date


class RecurrencePattern(BaseModel):
    """Recurrence pattern for recurring calls"""
    days_of_week: List[str] = Field(..., description="Days of week: Monday, Tuesday, etc.")
    start_date: str = Field(..., description="Start date in ISO format")
    end_date: str = Field(..., description="End date in ISO format")


class ScheduledCallBase(BaseModel):
    """Base schema for scheduled calls"""
    agent_name: str = Field(..., description="Name of the agent (e.g., 'Audria', 'Scott')")
    call_type: str = Field(..., description="Type of call: 'single', 'recurring', or 'immediate'")
    person_id: Optional[UUID] = Field(None, description="ID of the person (e.g., Bianca)")
    leading_reminders: Optional[str] = Field(None, description="Leading reminders text")
    leading_topics: Optional[str] = Field(None, description="Leading topics/questions")
    memories: Optional[List[str]] = Field(None, description="List of memory names")


class ScheduledCallCreate(ScheduledCallBase):
    """Schema for creating a scheduled call"""
    # For single calls
    scheduled_datetime: Optional[datetime] = Field(None, description="Date and time for single call")
    
    # For recurring calls
    scheduled_time: Optional[str] = Field(None, description="Time of day (e.g., '09:00')")
    recurrence_pattern: Optional[RecurrencePattern] = Field(None, description="Recurrence pattern for recurring calls")


class ScheduledCallUpdate(BaseModel):
    """Schema for updating a scheduled call"""
    agent_name: Optional[str] = None
    call_type: Optional[str] = None
    scheduled_datetime: Optional[datetime] = None
    scheduled_time: Optional[str] = None
    recurrence_pattern: Optional[RecurrencePattern] = None
    leading_reminders: Optional[str] = None
    leading_topics: Optional[str] = None
    memories: Optional[List[str]] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None


class ScheduledCallResponse(ScheduledCallBase):
    """Schema for scheduled call response"""
    id: UUID
    user_id: UUID
    scheduled_datetime: Optional[datetime] = None
    scheduled_time: Optional[str] = None
    recurrence_pattern: Optional[Dict[str, Any]] = None
    status: str
    is_active: bool
    initiated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ScheduledCallInstance(BaseModel):
    """Represents a single instance of a scheduled call (for calendar views)"""
    id: UUID
    scheduled_call_id: UUID
    agent_name: str
    call_datetime: datetime
    call_type: str
    leading_topics: Optional[str] = None
    memories: Optional[List[str]] = None
    status: str

