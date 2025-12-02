from fastapi import APIRouter, HTTPException, Depends, status, Query, UploadFile, File as FastAPIFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.auth import get_current_user
from app.core.exceptions import handle_database_errors, NotFoundError
from app.schemas.auth import TokenData
from app.crud.file import file_crud
from app.crud.conversation import conversation_crud
from app.crud.category import category_crud
from app.schemas.file import (
    FileUpdate, 
    FileResponse, 
    FileWithVersions,
    FileListResponse,
    FileUploadResponse,
    FileContentResponse
)

from app.services.blob_storage_service import blob_storage_service
from app.services.file_upload_service import file_upload_service
from typing import Optional
import uuid
import os
from datetime import datetime
from uuid import UUID
import httpx

router = APIRouter()

@router.post("/upload", response_model=FileUploadResponse)
@handle_database_errors
async def upload_file(
    job_id: str = ...,
    category_id: Optional[UUID] = None,
    description: Optional[str] = None,
    file: UploadFile = FastAPIFile(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload file for job processing
    
    This endpoint is for uploading files associated with jobs.
    If category_id is not provided, it defaults to the "conversations" category.
    
    Blob path: user_id/category_id/job_id/filename
    """
    
    if not job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_id is required for this endpoint."
        )
    
    return await file_upload_service.upload_file_internal(
        db=db,
        current_user=current_user,
        file=file,
        category_id=category_id,
        description=description,
        conversation_id=None,
        job_id=job_id
    )

@router.post("/upload/{conversation_id}", response_model=FileUploadResponse)
@handle_database_errors
async def upload_conversation_file(
    conversation_id: UUID,
    category_id: Optional[UUID] = None,
    description: Optional[str] = None,
    file: UploadFile = FastAPIFile(...),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a file for a specific conversation using conversation_id in URL
    
    This endpoint takes conversation_id from the URL path.
    If category_id is not provided, it defaults to the "conversations" category.
    
    Blob path: user_id/category_id/filename
    """
    
    return await file_upload_service.upload_file_internal(
        db=db,
        current_user=current_user,
        file=file,
        category_id=category_id,
        description=description,
        conversation_id=conversation_id,
        job_id=None
    )

# ============================================================================
# FILE MANAGEMENT (Database Operations)
# ============================================================================
# All endpoints below work with database records for both conversation and job files

@router.get("/", response_model=FileListResponse)
@handle_database_errors
async def get_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    conversation_id: Optional[UUID] = None,
    job_id: Optional[str] = None,
    category_id: Optional[UUID] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get files for the current user with optional filtering
    
    Filters:
    - conversation_id: Get files for a specific conversation
    - job_id: Get files for a specific job
    - category_id: Get files in a specific category
    
    Note: conversation_id and job_id are mutually exclusive
    """
    
    # Validate that conversation_id and job_id are not both provided
    if conversation_id and job_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot filter by both conversation_id and job_id. Use one or the other."
        )
    
    # Build filters
    filters = {"user_id": current_user.user_id}
    
    if conversation_id:
        # Verify conversation belongs to user
        await conversation_crud.get_by_user_id(
            db, id=conversation_id, user_id=current_user.user_id
        )
        filters["conversation_id"] = conversation_id
    
    if job_id:
        filters["job_id"] = job_id
    
    if category_id:
        # Validate category exists and is not deleted using generic method
        await category_crud.get(db, id=category_id)
        filters["category_id"] = category_id
    
    # Get files with filters
    files, total = await file_crud.get_by_fields(
        db, filters=filters, skip=skip, limit=limit
    )
    
    return FileListResponse(
        files=files,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{file_id}", response_model=FileResponse)
@handle_database_errors
async def get_file(
    file_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific file"""
    return await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )

@router.get("/{file_id}/with-versions", response_model=FileWithVersions)
@handle_database_errors
async def get_file_with_versions(
    file_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a file with its versions"""
    return await file_crud.get_with_relations(
        db, id=file_id, relations=["versions"]
    )

@router.put("/{file_id}", response_model=FileResponse)
@handle_database_errors
async def update_file(
    file_id: UUID,
    file_update: FileUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a file"""
    file = await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    return await file_crud.update(
        db, db_obj=file, obj_in=file_update
    )

@router.delete("/{file_id}")
@handle_database_errors
async def delete_file(
    file_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a file and all its versions"""
    success = await file_crud.soft_delete(
        db, file_id=file_id, user_id=current_user.user_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )
    
    return {"success": True, "message": "File deleted successfully"}

@router.get("/{file_id}/html")
@handle_database_errors
async def get_file_html(
    file_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the HTML content of a file from blob storage"""
    file_obj = await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    # Get current version (should be HTML)
    from app.crud.file_version import file_version_crud
    current_version = await file_version_crud.get_current_version(db, file_id=file_id)
    
    if not current_version or current_version.mime_type != "text/html":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HTML content not available for this file"
        )
    
    # Download HTML content from blob storage
    html_content_bytes = await blob_storage_service.download_file(current_version.blob_path)
    
    if html_content_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HTML content not found in storage"
        )
    
    html_content = html_content_bytes.decode('utf-8')
    return {"html_content": html_content}


@router.post("/{file_id}/upload-html")
@handle_database_errors
async def upload_html_version(
    file_id: UUID,
    html_file: UploadFile = FastAPIFile(...),
    change_description: Optional[str] = None,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload edited HTML content as a new version"""
    # Verify file belongs to user
    file_obj = await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    # Check if it's an HTML file
    if not html_file.filename or not html_file.filename.lower().endswith('.html'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only HTML files are allowed for this endpoint"
        )
    
    # Generate unique filename for HTML
    html_filename = f"{uuid.uuid4()}.html"
    html_blob_path = f"uploads/{current_user.user_id}/{file_obj.conversation_id}/html/{html_filename}"
    
    # Get file content
    html_content = await html_file.read()
    file_size = len(html_content)
    
    # Upload HTML to blob storage
    upload_success = await blob_storage_service.upload_file(
        blob_path=html_blob_path,
        content=html_content,
        content_type="text/html"
    )
    
    if not upload_success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload HTML to storage"
        )
    
    # Create new version
    from app.crud.file_version import file_version_crud
    new_version = await file_version_crud.create_version(
        db=db,
        file_id=file_id,
        blob_path=html_blob_path,
        file_size=file_size,
        mime_type="text/html",
        change_description=change_description or "Updated HTML content"
    )
    
    return new_version

@router.get("/conversation/{conversation_id}/files", response_model=FileListResponse)
@handle_database_errors
async def get_conversation_files(
    conversation_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get files for a specific conversation"""
    # Verify conversation belongs to user
    await conversation_crud.get_by_user_id(
        db, id=conversation_id, user_id=current_user.user_id
    )
    
    files, total = await file_crud.get_by_fields(
        db, filters={"conversation_id": conversation_id, "user_id": current_user.user_id}
    )
    
    return FileListResponse(
        files=files,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{file_id}/download-url")
@handle_database_errors
async def get_file_download_url(
    file_id: UUID,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a temporary download URL for a file"""
    file_obj = await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    if not file_obj.blob_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found in storage"
        )
    
    # Generate temporary download URL
    download_url = await blob_storage_service.get_file_url(file_obj.blob_path)
    
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )
    
    return {"download_url": download_url}

@router.get("/{file_id}/version/{version_number}/content", response_model=FileContentResponse)
@handle_database_errors
async def get_version_content(
    file_id: UUID,
    version_number: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the content of a specific file version (works around CORS issues)"""
    # Verify file belongs to user
    await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    # Get the specific version
    from app.crud.file_version import file_version_crud
    version = await file_version_crud.get_version_by_number(
        db, file_id=file_id, version_number=version_number
    )
    
    if not version or not version.blob_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found in storage"
        )
    
    try:
        # Option 1: Try to get content directly from blob storage service first
        content_bytes = await blob_storage_service.download_file(version.blob_path)
        
        if content_bytes is not None:
            # Successfully got content directly from blob storage
            try:
                # Try to decode as UTF-8 text
                content = content_bytes.decode('utf-8')
                return {"content": content, "content_type": version.mime_type}
            except UnicodeDecodeError:
                # If it's binary content, return base64 encoded
                import base64
                content_base64 = base64.b64encode(content_bytes).decode('utf-8')
                return {
                    "content": content_base64, 
                    "content_type": version.mime_type,
                    "encoding": "base64"
                }
        
        # Option 2: Fallback to using download URL if direct access fails
        download_url = await blob_storage_service.get_file_url(version.blob_path)
        
        if not download_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to access file content"
            )
        
        # Fetch content from the download URL
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(download_url)
            response.raise_for_status()
            
            # Check if it's text content
            content_type = response.headers.get('content-type', version.mime_type or '')
            
            if any(text_type in content_type.lower() for text_type in ['text/', 'application/json', 'application/xml']):
                # Text content - return as string
                content = response.text
                return {"content": content, "content_type": content_type}
            else:
                # Binary content - return as base64
                import base64
                content_base64 = base64.b64encode(response.content).decode('utf-8')
                return {
                    "content": content_base64, 
                    "content_type": content_type,
                    "encoding": "base64"
                }
                
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch file content: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error accessing file content: {str(e)}"
        )

@router.get("/{file_id}/version/{version_number}/download-url")
@handle_database_errors
async def get_version_download_url(
    file_id: UUID,
    version_number: int,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a temporary download URL for a specific file version"""
    # Verify file belongs to user
    await file_crud.get_by_user_id(
        db, id=file_id, user_id=current_user.user_id
    )
    
    # Get the specific version
    from app.crud.file_version import file_version_crud
    version = await file_version_crud.get_version_by_number(
        db, file_id=file_id, version_number=version_number
    )
    
    if not version or not version.blob_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found in storage"
        )
    
    # Generate temporary download URL
    download_url = await blob_storage_service.get_file_url(version.blob_path)
    
    if not download_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        )
    
    return {"download_url": download_url} 