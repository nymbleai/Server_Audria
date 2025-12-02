from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .base import CRUDBase
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate

class CRUDCategory(CRUDBase[Category, CategoryCreate, CategoryUpdate]):
    async def get_or_create_by_name(self, db: AsyncSession, *, name: str, description: Optional[str] = None) -> Category:
        """Get existing category by name or create new one"""
        # Use base CRUD get_by_field method instead of custom get_by_name
        categories, _ = await self.get_by_field(db, field="name", value=name, limit=1)
        category = categories[0] if categories else None
        
        if category:
            return category
        
        category_data = CategoryCreate(name=name, description=description)
        return await self.create(db, obj_in=category_data)

category_crud = CRUDCategory(Category) 