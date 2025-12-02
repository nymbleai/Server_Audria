from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from .file_version import FileVersionResponse

class FileBase(BaseModel):
    filename: str
    original_filename: str
    mime_type: str
    description: Optional[str] = None
    blob_path: Optional[str] = None
    file_size: Optional[int] = None
    category_id: Optional[UUID] = None
    job_id: Optional[str] = None

class FileCreate(FileBase):
    conversation_id: Optional[UUID] = None

class FileUpdate(BaseModel):
    filename: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[UUID] = None
    job_id: Optional[str] = None

class FileResponse(FileBase):
    id: UUID
    user_id: str
    conversation_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FileWithVersions(FileResponse):
    versions: List[FileVersionResponse] = []

class FileListResponse(BaseModel):
    files: List[FileResponse]
    total: int
    skip: int
    limit: int

class FileUploadResponse(BaseModel):
    file: FileResponse
    html_content: str = ""  

class FileContentResponse(BaseModel):
    content: str
    content_type: str
    encoding: Optional[str] = None  # "base64" for binary files, None for text files 