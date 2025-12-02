from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from .base import CRUDBase
from app.models.file import File
from app.models.file_version import FileVersion
from app.schemas.file import FileCreate, FileUpdate
from app.schemas.file_version import FileVersionCreate
from uuid import UUID

class CRUDFile(CRUDBase[File, FileCreate, FileUpdate]):
    async def create_file(
        self, db: AsyncSession, *, user_id: str, conversation_id: Optional[UUID], 
        filename: str, original_filename: str, mime_type: str, 
        description: Optional[str] = None, blob_path: Optional[str] = None,
        file_size: Optional[int] = None, category_id: Optional[UUID] = None, job_id: Optional[str] = None
    ) -> File:
        """Create a new file with version 0"""
        file_data = FileCreate(
            conversation_id=conversation_id,
            filename=filename,
            original_filename=original_filename,
            mime_type=mime_type,
            description=description,
            blob_path=blob_path,
            file_size=file_size,
            category_id=category_id,
            job_id=job_id
        )
        
        file_obj = await self.create_with_extra(
            db, obj_in=file_data, extra_data={"user_id": user_id}
        )
        
        version_data = FileVersionCreate(
            file_id=file_obj.id,
            version_number=0,
            blob_path=blob_path or "",
            file_size=file_size or 0,
            mime_type=mime_type,
            change_description="Initial version"
        )
        
        from .file_version import file_version_crud
        await file_version_crud.create_with_extra(
            db, obj_in=version_data, extra_data={"is_current": True}
        )
        
        return file_obj


    async def create_file_with_initial_html(
        self, db: AsyncSession, *, user_id: str, conversation_id: Optional[UUID],
        filename: str, original_filename: str, mime_type: str,
        description: Optional[str] = None, blob_path: Optional[str] = None,
        file_size: Optional[int] = None, category_id: Optional[UUID] = None, 
        job_id: Optional[str] = None, html_blob_path: str
    ) -> File:
        """Create a new file with original DOCX and initial HTML version"""
        # Create the file record (stores original DOCX info)
        file_data = FileCreate(
            conversation_id=conversation_id,
            filename=filename,
            original_filename=original_filename,
            mime_type=mime_type,
            description=description,
            blob_path=blob_path,
            file_size=file_size,
            category_id=category_id,
            job_id=job_id
        )
        
        file_obj = await self.create_with_extra(
            db, obj_in=file_data, extra_data={"user_id": user_id}
        )
        
        # Create version 0 (original DOCX)
        version_data_0 = FileVersionCreate(
            file_id=file_obj.id,
            version_number=0,
            blob_path=blob_path or "",
            file_size=file_size or 0,
            mime_type=mime_type,
            change_description="Original DOCX file"
        )
        
        from .file_version import file_version_crud
        await file_version_crud.create_with_extra(
            db, obj_in=version_data_0, extra_data={"is_current": False}
        )
        
        # Create version 1 (HTML)
        version_data_1 = FileVersionCreate(
            file_id=file_obj.id,
            version_number=1,
            blob_path=html_blob_path,
            file_size=0,  # Will be set when HTML is actually stored
            mime_type="text/html",
            change_description="Initial HTML conversion"
        )
        
        await file_version_crud.create_with_extra(
            db, obj_in=version_data_1, extra_data={"is_current": True}
        )
        
        return file_obj

    async def soft_delete(self, db: AsyncSession, *, file_id: UUID, user_id: str, raise_if_not_found: bool = True) -> bool:
        """Soft delete a file and all its versions"""
        from .file_version import file_version_crud
        await file_version_crud.soft_delete_by_file_id(db, file_id=file_id)
        
        return await self.soft_delete_by_user_id(db, id=file_id, user_id=user_id, raise_if_not_found=raise_if_not_found)

file_crud = CRUDFile(File) 