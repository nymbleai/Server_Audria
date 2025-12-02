from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func
from sqlalchemy.orm import selectinload
from .base import CRUDBase
from app.models.file_version import FileVersion
from app.models.file import File
from app.schemas.file_version import FileVersionCreate, FileVersionUpdate
from app.core.exceptions import NotFoundError
from uuid import UUID

class CRUDFileVersion(CRUDBase[FileVersion, FileVersionCreate, FileVersionUpdate]):
    async def get_current_version(
        self, db: AsyncSession, *, file_id: UUID, raise_if_not_found: bool = True
    ) -> Optional[FileVersion]:
        """Get the current version of a file"""
        versions, _ = await self.get_by_fields(
            db, filters={"file_id": file_id, "is_current": True}, limit=1
        )
        version = versions[0] if versions else None
        
        if raise_if_not_found and version is None:
            raise NotFoundError("Current version")
        
        return version

    async def create_version(
        self, db: AsyncSession, *, file_id: UUID, blob_path: str, file_size: int, 
        mime_type: str, change_description: Optional[str] = None
    ) -> FileVersion:
        """Create a new file version"""
        count = await self.count(db, filters={"file_id": file_id})
        next_version = count
        
        await self.update_by_field(
            db, field="file_id", value=file_id, obj_in={"is_current": False}
        )
        
        version_data = FileVersionCreate(
            file_id=file_id,
            version_number=next_version,
            blob_path=blob_path,
            file_size=file_size,
            mime_type=mime_type,
            change_description=change_description
        )
        
        new_version = await self.create_with_extra(
            db, obj_in=version_data, extra_data={"is_current": True}
        )

        # Also update the parent File.updated_at to reflect latest modification
        await db.execute(
            update(File)
            .where(and_(File.id == file_id, File.is_deleted == False))
            .values(updated_at=func.now())
        )
        await db.commit()

        return new_version

    async def get_version_by_number(
        self, db: AsyncSession, *, file_id: UUID, version_number: int, raise_if_not_found: bool = True
    ) -> Optional[FileVersion]:
        """Get a specific version of a file"""
        versions, _ = await self.get_by_fields(
            db, 
            filters={"file_id": file_id, "version_number": version_number}, 
            limit=1
        )
        version = versions[0] if versions else None
        
        if raise_if_not_found and version is None:
            raise NotFoundError(f"Version {version_number}")
        
        return version

    async def soft_delete_by_file_id(self, db: AsyncSession, *, file_id: UUID) -> bool:
        """Soft delete all versions of a file"""
        updated_items = await self.update_by_field(
            db, field="file_id", value=file_id, obj_in={"is_deleted": True}
        )
        return len(updated_items) > 0

    async def soft_delete_by_user_id(self, db: AsyncSession, *, id: UUID, user_id: str, raise_if_not_found: bool = True) -> bool:
        """Soft delete a file version by ID, ensuring it belongs to the specified user"""
        file_ids, _ = await self.get_by_fields(
            db, 
            filters={"id": id, "is_deleted": False},
            limit=1
        )
        
        if not file_ids:
            if raise_if_not_found:
                raise NotFoundError(f"{self.model.__name__}")
            return False
        
        version = file_ids[0]
        
        from .file import file_crud
        file_obj = await file_crud.get_by_user_id(
            db, id=version.file_id, user_id=user_id, raise_if_not_found=False
        )
        
        if not file_obj:
            if raise_if_not_found:
                raise NotFoundError(f"{self.model.__name__}")
            return False
        
        return await self.soft_delete(db, id=id, raise_if_not_found=raise_if_not_found)

    async def get_by_user_id(self, db: AsyncSession, id: UUID, user_id: str, *, raise_if_not_found: bool = True) -> Optional[FileVersion]:
        """Get a file version by ID, ensuring it belongs to the specified user"""
        result = await db.execute(
            select(FileVersion)
            .join(File, FileVersion.file_id == File.id)
            .where(
                and_(
                    FileVersion.id == id,
                    File.user_id == user_id,
                    FileVersion.is_deleted == False,
                    File.is_deleted == False
                )
            )
        )
        obj = result.scalar_one_or_none()
        
        if raise_if_not_found and obj is None:
            raise NotFoundError(f"{self.model.__name__}")
        
        return obj

file_version_crud = CRUDFileVersion(FileVersion) 