from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID

class FileVersionBase(BaseModel):
    version_number: int
    blob_path: str
    file_size: int
    mime_type: str
    change_description: Optional[str] = None

class FileVersionCreate(FileVersionBase):
    file_id: UUID

class FileVersionUpdate(BaseModel):
    change_description: Optional[str] = None
    is_current: Optional[bool] = None

class FileVersionResponse(FileVersionBase):
    id: UUID
    file_id: UUID
    is_current: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FileVersionListResponse(BaseModel):
    versions: list[FileVersionResponse]
    total: int
    skip: int
    limit: int 