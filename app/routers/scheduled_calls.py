from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from app.schemas.scheduled_call import (
    ScheduledCallCreate,
    ScheduledCallUpdate,
    ScheduledCallResponse
)
from app.core.auth import get_current_user
from app.schemas.auth import TokenData
from app.services.supabase_service import supabase_service

security = HTTPBearer()

router = APIRouter()


def _convert_row_to_response(row: dict) -> ScheduledCallResponse:
    """Convert Supabase row to ScheduledCallResponse"""
    from datetime import datetime as dt
    
    # Parse scheduled_time if it exists
    scheduled_time_str = None
    if row.get('scheduled_time'):
        if isinstance(row['scheduled_time'], str):
            scheduled_time_str = row['scheduled_time']
        else:
            # If it's a time object, convert to string
            scheduled_time_str = str(row['scheduled_time'])
    
    # Parse scheduled_datetime if it exists
    scheduled_datetime = None
    if row.get('scheduled_datetime'):
        if isinstance(row['scheduled_datetime'], str):
            scheduled_datetime = dt.fromisoformat(row['scheduled_datetime'].replace('Z', '+00:00'))
        else:
            scheduled_datetime = row['scheduled_datetime']
    
    # Parse other datetime fields
    created_at = dt.fromisoformat(row['created_at'].replace('Z', '+00:00')) if isinstance(row['created_at'], str) else row['created_at']
    updated_at = dt.fromisoformat(row['updated_at'].replace('Z', '+00:00')) if isinstance(row['updated_at'], str) else row['updated_at']
    initiated_at = None
    if row.get('initiated_at'):
        if isinstance(row['initiated_at'], str):
            initiated_at = dt.fromisoformat(row['initiated_at'].replace('Z', '+00:00'))
        else:
            initiated_at = row['initiated_at']
    
    return ScheduledCallResponse(
        id=UUID(row['id']),
        user_id=UUID(row['user_id']),
        person_id=UUID(row['person_id']) if row.get('person_id') else None,
        agent_name=row['agent_name'],
        call_type=row['call_type'],
        scheduled_datetime=scheduled_datetime,
        scheduled_time=scheduled_time_str,
        recurrence_pattern=row.get('recurrence_pattern'),
        leading_reminders=row.get('leading_reminders'),
        leading_topics=row.get('leading_topics'),
        memories=row.get('memories'),
        status=row.get('status', 'scheduled'),
        is_active=row.get('is_active', True),
        initiated_at=initiated_at,
        created_at=created_at,
        updated_at=updated_at
    )


@router.post(
    "",
    response_model=ScheduledCallResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new scheduled call",
    tags=["Scheduled Calls"]
)
async def create_scheduled_call(
    call: ScheduledCallCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a new scheduled call (single, recurring, or immediate) using Supabase"""
    user_id = str(current_user.user_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Validate call type requirements
        if call.call_type == 'single':
            if not call.scheduled_datetime:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Single calls must have a scheduled_datetime"
                )
            # Immediate calls shouldn't have date/time fields
            if call.scheduled_time or call.recurrence_pattern:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Single calls cannot have scheduled_time or recurrence_pattern"
                )
        
        elif call.call_type == 'recurring':
            if not call.scheduled_time:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Recurring calls must have a scheduled_time"
                )
            if not call.recurrence_pattern:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Recurring calls must have a recurrence_pattern"
                )
            # Recurring calls shouldn't have scheduled_datetime
            if call.scheduled_datetime:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Recurring calls cannot have scheduled_datetime"
                )
        
        elif call.call_type == 'immediate':
            # Immediate calls shouldn't have date/time fields
            if call.scheduled_datetime or call.scheduled_time or call.recurrence_pattern:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Immediate calls cannot have scheduled_datetime, scheduled_time, or recurrence_pattern"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid call_type: {call.call_type}. Must be 'single', 'recurring', or 'immediate'"
            )
        
        # Prepare data for insertion
        insert_data = {
            'user_id': user_id,
            'agent_name': call.agent_name,
            'call_type': call.call_type,
            'leading_reminders': call.leading_reminders,
            'leading_topics': call.leading_topics,
            'memories': call.memories,
            'status': 'scheduled',
            'is_active': True
        }
        
        # Add person_id if provided
        if call.person_id:
            insert_data['person_id'] = str(call.person_id)
        
        # Handle single call
        if call.call_type == 'single':
            insert_data['scheduled_datetime'] = call.scheduled_datetime.isoformat()
        
        # Handle recurring call
        if call.call_type == 'recurring':
            insert_data['scheduled_time'] = call.scheduled_time
            # Convert Pydantic model to dict
            if hasattr(call.recurrence_pattern, 'model_dump'):
                insert_data['recurrence_pattern'] = call.recurrence_pattern.model_dump()
            else:
                insert_data['recurrence_pattern'] = call.recurrence_pattern
        
        # Handle immediate call
        if call.call_type == 'immediate':
            insert_data['status'] = 'immediate'
            from datetime import datetime as dt
            insert_data['initiated_at'] = dt.utcnow().isoformat() + 'Z'
            # Mark as inactive since it's immediate (already initiated)
            insert_data['is_active'] = False
        
        # Insert into Supabase
        response = supabase_service.supabase.table('scheduled_calls').insert(insert_data).execute()
        
        if response.data and len(response.data) > 0:
            return _convert_row_to_response(response.data[0])
        
        raise HTTPException(status_code=500, detail="Failed to create scheduled call")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating scheduled call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create scheduled call: {str(e)}")


@router.get(
    "",
    response_model=List[ScheduledCallResponse],
    summary="Get all scheduled calls for current user",
    tags=["Scheduled Calls"]
)
async def get_scheduled_calls(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    current_user: TokenData = Depends(get_current_user)
):
    """Get all scheduled calls for the current user using Supabase"""
    user_id = str(current_user.user_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        query = supabase_service.supabase.table('scheduled_calls').select('*').eq('user_id', user_id).eq('is_deleted', False)
        
        if is_active is not None:
            query = query.eq('is_active', is_active)
        
        response = query.order('created_at', desc=True).limit(limit).offset(skip).execute()
        
        calls = []
        for row in response.data:
            calls.append(_convert_row_to_response(row))
        
        return calls
    except Exception as e:
        print(f"Error fetching scheduled calls: {e}")
        return []


@router.get(
    "/range",
    response_model=List[ScheduledCallResponse],
    summary="Get scheduled calls for a date range",
    tags=["Scheduled Calls"]
)
async def get_calls_for_date_range(
    start_date: datetime = Query(..., description="Start date for range"),
    end_date: datetime = Query(..., description="End date for range"),
    current_user: TokenData = Depends(get_current_user)
):
    """Get all scheduled calls (single and recurring instances) within a date range using Supabase"""
    user_id = str(current_user.user_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Use the same approach as persons router - direct query with service key
        # Simplified query - fetch all calls for user first, then filter in Python
        try:
            # Simple query - just get all active calls for this user
            # We'll filter by date in Python code
            result = supabase_service.supabase.table('scheduled_calls')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('is_deleted', False)\
                .eq('is_active', True)\
                .limit(200)\
                .execute()
            print(f"✅ Fetched {len(result.data) if result.data else 0} scheduled calls from Supabase")
            all_calls_response = result
        except Exception as e:
            print(f"❌ Error fetching scheduled calls: {e}")
            import traceback
            traceback.print_exc()
            return []
        
        if not hasattr(all_calls_response, 'data') or not all_calls_response.data:
            return []
        
        # Filter calls in Python code
        calls = []
        for row in all_calls_response.data:
            try:
                call_type = row.get('call_type')
                
                # Handle single calls
                if call_type == 'single':
                    scheduled_datetime_str = row.get('scheduled_datetime')
                    if scheduled_datetime_str:
                        try:
                            scheduled_dt = datetime.fromisoformat(scheduled_datetime_str.replace('Z', '+00:00'))
                            # Check if within date range
                            if start_date <= scheduled_dt <= end_date:
                                calls.append(_convert_row_to_response(row))
                        except Exception as e:
                            print(f"Error parsing scheduled_datetime: {e}")
                            continue
                
                # Handle recurring calls
                elif call_type == 'recurring':
                    recurrence_pattern = row.get('recurrence_pattern')
                    if recurrence_pattern:
                        pattern_start_str = recurrence_pattern.get('start_date', '')
                        pattern_end_str = recurrence_pattern.get('end_date', '')
                        
                        if pattern_start_str and pattern_end_str:
                            try:
                                pattern_start = datetime.fromisoformat(pattern_start_str.replace('Z', '+00:00'))
                                pattern_end = datetime.fromisoformat(pattern_end_str.replace('Z', '+00:00'))
                                
                                # Check if pattern overlaps with requested range
                                if pattern_start <= end_date and pattern_end >= start_date:
                                    calls.append(_convert_row_to_response(row))
                            except Exception as e:
                                print(f"Error parsing recurrence pattern dates: {e}")
                                continue
            except Exception as e:
                print(f"Error processing call row: {e}")
                continue
        
        return calls
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching calls for date range: {e}")
        import traceback
        traceback.print_exc()
        # Return empty array instead of raising error to prevent UI blocking
        return []


@router.get(
    "/{call_id}",
    response_model=ScheduledCallResponse,
    summary="Get a specific scheduled call",
    tags=["Scheduled Calls"]
)
async def get_scheduled_call(
    call_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific scheduled call by ID using Supabase"""
    user_id = str(current_user.user_id)
    call_id_str = str(call_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        response = supabase_service.supabase.table('scheduled_calls').select('*').eq('id', call_id_str).eq('user_id', user_id).eq('is_deleted', False).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduled call not found"
            )
        
        return _convert_row_to_response(response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching scheduled call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduled call: {str(e)}")


@router.put(
    "/{call_id}",
    response_model=ScheduledCallResponse,
    summary="Update a scheduled call",
    tags=["Scheduled Calls"]
)
async def update_scheduled_call(
    call_id: UUID,
    call_update: ScheduledCallUpdate,
    current_user: TokenData = Depends(get_current_user)
):
    """Update a scheduled call using Supabase"""
    user_id = str(current_user.user_id)
    call_id_str = str(call_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Verify call exists and belongs to user
        check_response = supabase_service.supabase.table('scheduled_calls').select('id').eq('id', call_id_str).eq('user_id', user_id).eq('is_deleted', False).execute()
        
        if not check_response.data or len(check_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduled call not found"
            )
        
        # Prepare update data
        update_data = {}
        update_fields = call_update.model_dump(exclude_unset=True)
        
        for field, value in update_fields.items():
            if field == 'scheduled_datetime' and value:
                update_data['scheduled_datetime'] = value.isoformat() if isinstance(value, datetime) else value
            elif field == 'scheduled_time' and value:
                update_data['scheduled_time'] = value
            elif field == 'recurrence_pattern' and value:
                if hasattr(value, 'model_dump'):
                    update_data['recurrence_pattern'] = value.model_dump()
                else:
                    update_data['recurrence_pattern'] = value
            elif field == 'person_id' and value:
                update_data['person_id'] = str(value)
            elif value is not None:
                update_data[field] = value
        
        from datetime import datetime as dt
        update_data['updated_at'] = dt.utcnow().isoformat() + 'Z'
        
        # Update in Supabase
        response = supabase_service.supabase.table('scheduled_calls').update(update_data).eq('id', call_id_str).execute()
        
        if response.data and len(response.data) > 0:
            return _convert_row_to_response(response.data[0])
        
        raise HTTPException(status_code=500, detail="Failed to update scheduled call")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating scheduled call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update scheduled call: {str(e)}")


@router.delete(
    "/{call_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a scheduled call",
    tags=["Scheduled Calls"]
)
async def delete_scheduled_call(
    call_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Soft delete a scheduled call using Supabase"""
    user_id = str(current_user.user_id)
    call_id_str = str(call_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Verify call exists and belongs to user
        check_response = supabase_service.supabase.table('scheduled_calls').select('id').eq('id', call_id_str).eq('user_id', user_id).eq('is_deleted', False).execute()
        
        if not check_response.data or len(check_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scheduled call not found"
            )
        
        # Soft delete
        from datetime import datetime as dt
        supabase_service.supabase.table('scheduled_calls').update({
            'is_deleted': True,
            'updated_at': dt.utcnow().isoformat() + 'Z'
        }).eq('id', call_id_str).execute()
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting scheduled call: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete scheduled call: {str(e)}")


@router.get(
    "/person/{person_id}",
    response_model=List[ScheduledCallResponse],
    summary="Get scheduled calls for a specific person",
    tags=["Scheduled Calls"]
)
async def get_calls_for_person(
    person_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: TokenData = Depends(get_current_user)
):
    """Get all scheduled calls for a specific person using Supabase"""
    user_id = str(current_user.user_id)
    person_id_str = str(person_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        response = supabase_service.supabase.table('scheduled_calls').select('*').eq('user_id', user_id).eq('person_id', person_id_str).eq('is_deleted', False).order('created_at', desc=True).limit(limit).offset(skip).execute()
        
        calls = []
        for row in response.data:
            calls.append(_convert_row_to_response(row))
        
        return calls
    except Exception as e:
        print(f"Error fetching calls for person: {e}")
        return []
