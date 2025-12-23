from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Optional, Dict, Any
from uuid import UUID

from app.schemas.person import (
    PersonCreate,
    PersonUpdate,
    PersonResponse,
    PersonDetailsResponse,
    PersonWithDetailsResponse,
    PersonDetailsData
)
from app.core.auth import get_current_user
from app.schemas.auth import TokenData
from app.services.supabase_service import supabase_service

router = APIRouter()


@router.post(
    "",
    response_model=PersonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new person",
    tags=["Persons"]
)
async def create_person(
    person: PersonCreate,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a new person for the current user using Supabase"""
    user_id = str(current_user.user_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Use Supabase client directly
        response = supabase_service.supabase.table('persons').insert({
            'user_id': user_id,
            'name': person.name,
            'generation': person.generation
        }).execute()
        
        if response.data and len(response.data) > 0:
            row = response.data[0]
            from datetime import datetime
            return PersonResponse(
                id=UUID(row['id']),
                user_id=UUID(row['user_id']),
                name=row['name'],
                generation=row.get('generation'),
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
            )
        raise HTTPException(status_code=500, detail="Failed to create person")
    except Exception as e:
        print(f"Error creating person: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create person: {str(e)}")


@router.get(
    "",
    response_model=List[PersonResponse],
    summary="Get all persons for current user",
    tags=["Persons"]
)
async def get_persons(
    skip: int = 0,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user)
):
    """Get all persons belonging to the current user using Supabase"""
    user_id = str(current_user.user_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Use Supabase client directly (faster and doesn't require SQLAlchemy)
        response = supabase_service.supabase.table('persons').select('*').eq('user_id', user_id).order('created_at', desc=True).limit(limit).offset(skip).execute()
        
        persons = []
        for row in response.data:
            from datetime import datetime
            persons.append(PersonResponse(
                id=UUID(row['id']),
                user_id=UUID(row['user_id']),
                name=row['name'],
                generation=row.get('generation'),
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
            ))
        return persons
    except Exception as e:
        print(f"Error fetching persons from Supabase: {e}")
        # Return empty list on error instead of failing
        return []


@router.get(
    "/{person_id}",
    response_model=PersonWithDetailsResponse,
    summary="Get a person by ID with details",
    tags=["Persons"]
)
async def get_person(
    person_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific person with their details using Supabase"""
    user_id = str(current_user.user_id)
    person_id_str = str(person_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Get person
        person_response = supabase_service.supabase.table('persons').select('*').eq('id', person_id_str).eq('user_id', user_id).execute()
        
        if not person_response.data or len(person_response.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found"
            )
        
        person_row = person_response.data[0]
        from datetime import datetime
        
        person = PersonResponse(
            id=UUID(person_row['id']),
            user_id=UUID(person_row['user_id']),
            name=person_row['name'],
            generation=person_row.get('generation'),
            created_at=datetime.fromisoformat(person_row['created_at'].replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(person_row['updated_at'].replace('Z', '+00:00'))
        )
        
        # Get person details if they exist
        details_response = supabase_service.supabase.table('person_details').select('*').eq('person_id', person_id_str).execute()
        
        response = PersonWithDetailsResponse.model_validate(person)
        if details_response.data and len(details_response.data) > 0:
            details_row = details_response.data[0]
            response.details = PersonDetailsResponse(
                id=UUID(details_row['id']),
                person_id=UUID(details_row['person_id']),
                data=details_row['data'],
                created_at=datetime.fromisoformat(details_row['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(details_row['updated_at'].replace('Z', '+00:00'))
            )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching person: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch person: {str(e)}")


@router.put(
    "/{person_id}",
    response_model=PersonResponse,
    summary="Update a person",
    tags=["Persons"]
)
async def update_person(
    person_id: UUID,
    person_update: PersonUpdate,
    current_user: TokenData = Depends(get_current_user)
):
    """Update a person's information using Supabase"""
    user_id = str(current_user.user_id)
    person_id_str = str(person_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Verify person exists and belongs to user
        person_check = supabase_service.supabase.table('persons').select('*').eq('id', person_id_str).eq('user_id', user_id).execute()
        
        if not person_check.data or len(person_check.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found"
            )
        
        # Update person
        update_data = {}
        if person_update.name is not None:
            update_data['name'] = person_update.name
        if person_update.generation is not None:
            update_data['generation'] = person_update.generation
        
        from datetime import datetime
        update_data['updated_at'] = datetime.utcnow().isoformat() + 'Z'
        
        response = supabase_service.supabase.table('persons').update(update_data).eq('id', person_id_str).execute()
        
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return PersonResponse(
                id=UUID(row['id']),
                user_id=UUID(row['user_id']),
                name=row['name'],
                generation=row.get('generation'),
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
            )
        raise HTTPException(status_code=500, detail="Failed to update person")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating person: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update person: {str(e)}")


@router.delete(
    "/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a person",
    tags=["Persons"]
)
async def delete_person(
    person_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete a person and their details using Supabase"""
    user_id = str(current_user.user_id)
    person_id_str = str(person_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    # Verify person exists and belongs to user
    person_check = supabase_service.supabase.table('persons').select('id').eq('id', person_id_str).eq('user_id', user_id).execute()
    
    if not person_check.data or len(person_check.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    # Delete person (details will be deleted automatically via CASCADE)
    supabase_service.supabase.table('persons').delete().eq('id', person_id_str).execute()
    return None


# Person Details endpoints
@router.put(
    "/{person_id}/details",
    response_model=PersonDetailsResponse,
    summary="Create or update person details",
    tags=["Persons"]
)
async def upsert_person_details(
    person_id: UUID,
    details_data: PersonDetailsData,
    current_user: TokenData = Depends(get_current_user)
):
    """Create or update person details (residences, work history, etc.) as JSONB using Supabase"""
    user_id = str(current_user.user_id)
    person_id_str = str(person_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    try:
        # Verify person exists and belongs to user
        person_check = supabase_service.supabase.table('persons').select('id').eq('id', person_id_str).eq('user_id', user_id).execute()
        
        if not person_check.data or len(person_check.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found"
            )
        
        # Convert Pydantic model to dict for JSONB storage
        # This ensures workHistory, personalInfo, and dailyRoutine are properly structured as JSONB
        jsonb_data = details_data.model_dump()
        
        # Check if details exist
        details_check = supabase_service.supabase.table('person_details').select('id').eq('person_id', person_id_str).execute()
        
        from datetime import datetime
        
        if details_check.data and len(details_check.data) > 0:
            # Update existing - store as JSONB
            response = supabase_service.supabase.table('person_details').update({
                'data': jsonb_data,  # This is stored as JSONB in PostgreSQL
                'updated_at': datetime.utcnow().isoformat() + 'Z'
            }).eq('person_id', person_id_str).execute()
        else:
            # Create new - store as JSONB
            response = supabase_service.supabase.table('person_details').insert({
                'person_id': person_id_str,
                'data': jsonb_data  # This is stored as JSONB in PostgreSQL
            }).execute()
        
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return PersonDetailsResponse(
                id=UUID(row['id']),
                person_id=UUID(row['person_id']),
                data=row['data'],
                created_at=datetime.fromisoformat(row['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(row['updated_at'].replace('Z', '+00:00'))
            )
        raise HTTPException(status_code=500, detail="Failed to save person details")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving person details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save person details: {str(e)}")


@router.get(
    "/{person_id}/details",
    response_model=PersonDetailsResponse,
    summary="Get person details",
    tags=["Persons"]
)
async def get_person_details(
    person_id: UUID,
    current_user: TokenData = Depends(get_current_user)
):
    """Get details for a specific person using Supabase"""
    user_id = str(current_user.user_id)
    person_id_str = str(person_id)
    
    if not supabase_service.supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase service unavailable"
        )
    
    # Verify person exists and belongs to user
    person_check = supabase_service.supabase.table('persons').select('id').eq('id', person_id_str).eq('user_id', user_id).execute()
    
    if not person_check.data or len(person_check.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    # Get details
    details_response = supabase_service.supabase.table('person_details').select('*').eq('person_id', person_id_str).execute()
    
    if not details_response.data or len(details_response.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person details not found"
        )
    
    from datetime import datetime
    details_row = details_response.data[0]
    return PersonDetailsResponse(
        id=UUID(details_row['id']),
        person_id=UUID(details_row['person_id']),
        data=details_row['data'],
        created_at=datetime.fromisoformat(details_row['created_at'].replace('Z', '+00:00')),
        updated_at=datetime.fromisoformat(details_row['updated_at'].replace('Z', '+00:00'))
    )

