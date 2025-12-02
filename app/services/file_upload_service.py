from fastapi import HTTPException, status, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.auth import TokenData
from app.crud.file import file_crud
from app.crud.conversation import conversation_crud
from app.crud.category import category_crud
from app.schemas.file import FileUploadResponse
from app.services.blob_storage_service import blob_storage_service
from app.services.file_converter_service import file_converter_service
from typing import Optional
import uuid
import os
from uuid import UUID


class FileUploadService:
    """Service for handling file upload operations"""
    
    async def upload_file_internal(
        self,
        db: AsyncSession,
        current_user: TokenData,
        file: UploadFile,
        category_id: Optional[UUID],
        description: Optional[str],
        conversation_id: Optional[UUID],
        job_id: Optional[str]
    ) -> FileUploadResponse:
        """
        Internal function to handle file upload logic shared between endpoints
        
        This function contains the common logic for uploading files to both
        conversations and jobs.
        """
        
        # Set default category_id if not provided (get "conversations" category by name)
        if category_id is None:
            try:
                # Get the "conversations" category by name
                categories, _ = await category_crud.get_by_field(db, field="name", value="conversations", limit=1)
                if categories:
                    category_id = categories[0].id
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Default 'conversations' category not found. Please provide a category_id."
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to get default category: {str(e)}"
                )
        
        # Validate category exists and is not deleted/disabled using generic method
        await category_crud.get(db, id=category_id)
        
        # If conversation_id is provided, verify it belongs to user
        if conversation_id:
            await conversation_crud.get_by_user_id(
                db, id=conversation_id, user_id=current_user.user_id
            )
        
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        
        # Create blob path based on file type
        if job_id:
            # Job files: user_id/category_id/job_id/filename
            blob_path = f"uploads/{current_user.user_id}/{category_id}/{job_id}/{unique_filename}"
        else:
            # Conversation files: user_id/category_id/filename
            blob_path = f"uploads/{current_user.user_id}/{category_id}/{unique_filename}"
        
        # Get file size
        file_content = await file.read()
        file_size = len(file_content)
        
        # Reset file position for further reading
        await file.seek(0)
        
        # Check if it's a DOCX file that needs conversion
        if not file_converter_service.is_docx_file(file):
            # Regular file upload - no conversion needed
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
            
            # Create database record for regular file
            file_obj = await file_crud.create_file(
                db=db,
                user_id=current_user.user_id,
                conversation_id=conversation_id,
                filename=unique_filename,
                original_filename=file.filename or "unknown",
                mime_type=file.content_type or "application/octet-stream",
                description=description,
                blob_path=blob_path,
                file_size=file_size,
                category_id=category_id,
                job_id=job_id
            )
            return FileUploadResponse(file=file_obj, html_content="")
        
        # DOCX file conversion path
        html_content = await file_converter_service.convert_docx_to_html(file)
        
        if not html_content:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to convert DOCX to HTML"
            )
        
        # Generate HTML blob path
        html_filename = f"{uuid.uuid4()}_v1.html"
        html_blob_path = f"uploads/{current_user.user_id}/{category_id}/html/{html_filename}"
        
        # Upload original DOCX to blob storage
        docx_upload_success = await blob_storage_service.upload_file(
            blob_path=blob_path,
            content=file_content,
            content_type=file.content_type or "application/octet-stream"
        )
        
        if not docx_upload_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload original file to storage"
            )
        
        # Upload HTML to blob storage
        html_upload_success = await blob_storage_service.upload_file(
            blob_path=html_blob_path,
            content=html_content,
            content_type="text/html"
        )
        
        if not html_upload_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload HTML to storage"
            )
        
        # Create file with original DOCX and HTML version
        file_obj = await file_crud.create_file_with_initial_html(
            db=db,
            user_id=current_user.user_id,
            conversation_id=conversation_id,
            filename=unique_filename,
            original_filename=file.filename or "unknown",
            mime_type=file.content_type or "application/octet-stream",
            description=description,
            blob_path=blob_path,
            file_size=file_size,
            category_id=category_id,
            job_id=job_id,
            html_blob_path=html_blob_path
        )
        return FileUploadResponse(file=file_obj, html_content=html_content)


# Create a singleton instance
file_upload_service = FileUploadService() 