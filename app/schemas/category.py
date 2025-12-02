from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    name: Optional[str] = Field(None, min_length=1, max_length=255)

class CategoryInDBBase(CategoryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    is_deleted: bool

    class Config:
        from_attributes = True

class Category(CategoryInDBBase):
    pass

class CategoryInDB(CategoryInDBBase):
    pass 