from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File as FastAPIFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.exceptions import handle_database_errors, NotFoundError, ValidationError
from app.schemas.auth import TokenData
from app.crud.file_version import file_version_crud
from app.crud.file import file_crud
from app.crud.category import category_crud
from app.schemas.file_version import (
    FileVersionCreate, 
    FileVersionUpdate, 
    FileVersionResponse, 
    FileVersionListResponse
)
from app.services.blob_storage_service import blob_storage_service
from typing import Optional
import uuid
import os
from uuid import UUID

router = APIRouter()

@router.post("/upload/{file_id}", response_model=FileVersionResponse)
@handle_database_errors
async def upload_file_version(
    file_id: UUID,
    file: UploadFile = FastAPIFile(...),
    change_description: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a new version of a file
    
    Works for both conversation files and job files.
    Blob paths follow the same pattern as the main upload endpoint.
    """
    # Get the file and verify it belongs to user
    file_obj = await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    # Validate category exists and is not deleted (if category_id is present)
    if file_obj.category_id:
        await category_crud.get(db, id=file_obj.category_id)
    
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    
    # Create blob path based on file type (consistent with main upload endpoint)
    if file_obj.job_id:
        # Job files: user_id/category_id/job_id/versions/filename
        blob_path = f"uploads/{current_user.user_id}/{file_obj.category_id}/{file_obj.job_id}/versions/{unique_filename}"
    else:
        # Conversation files: user_id/category_id/versions/filename
        blob_path = f"uploads/{current_user.user_id}/{file_obj.category_id}/versions/{unique_filename}"
    
    file_content = await file.read()
    file_size = len(file_content)
    
    upload_success = await blob_storage_service.upload_file(
        blob_path=blob_path,
        content=file_content,
        content_type=file.content_type or "application/octet-stream"
    )
    
    if not upload_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage"
        )
    
    return await file_version_crud.create_version(
        db=db,
        file_id=file_id,
        blob_path=blob_path,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        change_description=change_description
    )

@router.get("/file/{file_id}", response_model=FileVersionListResponse)
@handle_database_errors
async def get_file_versions(
    file_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get versions for a specific file (works for both conversation and job files)"""
    await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    versions, total = await file_version_crud.get_by_field(
        db, field="file_id", value=file_id, skip=skip, limit=limit
    )
    
    return FileVersionListResponse(
        versions=versions,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{version_id}", response_model=FileVersionResponse)
@handle_database_errors
async def get_file_version(
    version_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific file version (works for both conversation and job files)"""
    return await file_version_crud.get_by_user_id(
        db, id=version_id, user_id=current_user.user_id
    )

@router.get("/file/{file_id}/current", response_model=FileVersionResponse)
@handle_database_errors
async def get_current_file_version(
    file_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the current version of a file (works for both conversation and job files)"""
    await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    return await file_version_crud.get_current_version(db, file_id=file_id)

@router.get("/file/{file_id}/version/{version_number}", response_model=FileVersionResponse)
@handle_database_errors
async def get_file_version_by_number(
    file_id: UUID,
    version_number: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific version number of a file (works for both conversation and job files)"""
    await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    return await file_version_crud.get_version_by_number(
        db, file_id=file_id, version_number=version_number
    )

@router.put("/{version_id}", response_model=FileVersionResponse)
@handle_database_errors
async def update_file_version(
    version_id: UUID,
    version_update: FileVersionUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a file version (works for both conversation and job files)"""
    version = await file_version_crud.get_by_user_id(
        db, id=version_id, user_id=current_user.user_id
    )
    
    return await file_version_crud.update(
        db, db_obj=version, obj_in=version_update
    )

@router.delete("/{version_id}")
@handle_database_errors
async def delete_file_version(
    version_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a file version (works for both conversation and job files)"""
    version = await file_version_crud.get_by_user_id(
        db, id=version_id, user_id=current_user.user_id
    )
    
    if version.is_current:
        raise ValidationError("Cannot delete the current version of a file")
    
    success = await file_version_crud.soft_delete_by_user_id(
        db, id=version_id, user_id=current_user.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file version"
        )
    
    return {"success": True, "message": "File version deleted successfully"} 