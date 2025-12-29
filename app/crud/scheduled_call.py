from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime, date, time as time_type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.models.scheduled_call import ScheduledCall
from app.crud.base import CRUDBase
from app.schemas.scheduled_call import ScheduledCallCreate, ScheduledCallUpdate
import json


class CRUDScheduledCall(CRUDBase[ScheduledCall, ScheduledCallCreate, ScheduledCallUpdate]):
    """CRUD operations for ScheduledCall model"""
    
    async def get_by_user(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> Tuple[List[ScheduledCall], int]:
        """Get all scheduled calls for a specific user"""
        filters = {"user_id": user_id}
        if is_active is not None:
            filters["is_active"] = is_active
        
        return await self.get_multi(
            db,
            skip=skip,
            limit=limit,
            filters=filters,
            order_by="created_at",
            order_desc=True
        )
    
    async def get_by_person_id(
        self,
        db: AsyncSession,
        *,
        person_id: UUID,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[ScheduledCall], int]:
        """Get all scheduled calls for a specific person"""
        return await self.get_multi(
            db,
            skip=skip,
            limit=limit,
            filters={"person_id": person_id, "user_id": user_id},
            order_by="created_at",
            order_desc=True
        )
    
    async def get_calls_for_date_range(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[ScheduledCall]:
        """Get all calls (single and recurring) that occur within a date range"""
        # Get single calls in date range
        single_calls_query = select(ScheduledCall).where(
            and_(
                ScheduledCall.user_id == user_id,
                ScheduledCall.call_type == "single",
                ScheduledCall.scheduled_datetime >= start_date,
                ScheduledCall.scheduled_datetime <= end_date,
                ScheduledCall.is_deleted == False,
                ScheduledCall.is_active == True
            )
        )
        
        # Get recurring calls that might have instances in date range
        recurring_calls_query = select(ScheduledCall).where(
            and_(
                ScheduledCall.user_id == user_id,
                ScheduledCall.call_type == "recurring",
                ScheduledCall.is_deleted == False,
                ScheduledCall.is_active == True
            )
        )
        
        single_result = await db.execute(single_calls_query)
        recurring_result = await db.execute(recurring_calls_query)
        
        single_calls = list(single_result.scalars().all())
        recurring_calls = list(recurring_result.scalars().all())
        
        # Filter recurring calls by checking if their pattern overlaps with date range
        # This is a simplified check - in production, you'd want to parse the recurrence_pattern
        # and check if any instances fall within the range
        valid_recurring = []
        for call in recurring_calls:
            if call.recurrence_pattern:
                pattern = call.recurrence_pattern
                pattern_start = datetime.fromisoformat(pattern.get("start_date", "").replace("Z", "+00:00"))
                pattern_end = datetime.fromisoformat(pattern.get("end_date", "").replace("Z", "+00:00"))
                
                # Check if pattern overlaps with requested range
                if pattern_start <= end_date and pattern_end >= start_date:
                    valid_recurring.append(call)
        
        return single_calls + valid_recurring
    
    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: ScheduledCallCreate,
        user_id: UUID
    ) -> ScheduledCall:
        """Create a new scheduled call"""
        obj_in_data = obj_in.model_dump(exclude_unset=True)
        
        # Convert scheduled_time string to Time object if provided
        if "scheduled_time" in obj_in_data and obj_in_data["scheduled_time"]:
            time_str = obj_in_data["scheduled_time"]
            if isinstance(time_str, str):
                hour, minute = map(int, time_str.split(":"))
                obj_in_data["scheduled_time"] = time_type(hour, minute)
        
        # Convert recurrence_pattern to dict if it's a Pydantic model
        if "recurrence_pattern" in obj_in_data and obj_in_data["recurrence_pattern"]:
            if hasattr(obj_in_data["recurrence_pattern"], "model_dump"):
                obj_in_data["recurrence_pattern"] = obj_in_data["recurrence_pattern"].model_dump()
        
        # Convert memories list to JSONB-compatible format
        if "memories" in obj_in_data and obj_in_data["memories"]:
            obj_in_data["memories"] = obj_in_data["memories"]
        
        # Add user_id
        obj_in_data["user_id"] = user_id
        
        # Set status based on call_type
        if obj_in_data.get("call_type") == "immediate":
            obj_in_data["status"] = "immediate"
            obj_in_data["initiated_at"] = datetime.utcnow()
        
        db_obj = ScheduledCall(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ScheduledCall,
        obj_in: ScheduledCallUpdate,
        user_id: UUID
    ) -> ScheduledCall:
        """Update a scheduled call (ensuring it belongs to user)"""
        if db_obj.user_id != user_id:
            raise ValueError("Scheduled call does not belong to user")
        
        update_data = obj_in.model_dump(exclude_unset=True)
        
        # Convert scheduled_time string to Time object if provided
        if "scheduled_time" in update_data and update_data["scheduled_time"]:
            time_str = update_data["scheduled_time"]
            if isinstance(time_str, str):
                hour, minute = map(int, time_str.split(":"))
                update_data["scheduled_time"] = time_type(hour, minute)
        
        # Convert recurrence_pattern to dict if it's a Pydantic model
        if "recurrence_pattern" in update_data and update_data["recurrence_pattern"]:
            if hasattr(update_data["recurrence_pattern"], "model_dump"):
                update_data["recurrence_pattern"] = update_data["recurrence_pattern"].model_dump()
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


# Create instance
scheduled_call_crud = CRUDScheduledCall(ScheduledCall)

