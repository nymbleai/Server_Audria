from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.core.database import get_db
from app.core.auth import get_current_user
from app.crud.category import category_crud
from app.schemas.category import Category, CategoryCreate, CategoryUpdate
from app.schemas.auth import TokenData

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=List[Category])
async def get_categories(
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False
):
    """Get all categories"""
    categories, _ = await category_crud.get_multi(db, skip=skip, limit=limit, include_deleted=include_inactive)
    return categories

@router.get("/{category_id}", response_model=Category)
async def get_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Get a specific category by ID"""
    category = await category_crud.get(db, id=category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    return category

@router.post("/", response_model=Category)
async def create_category(
    category_in: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Create a new category"""
    # Use base CRUD get_by_field method instead of get_by_name
    existing_categories, _ = await category_crud.get_by_field(db, field="name", value=category_in.name, limit=1)
    existing_category = existing_categories[0] if existing_categories else None
    
    if existing_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )
    
    category = await category_crud.create(db, obj_in=category_in)
    return category

@router.put("/{category_id}", response_model=Category)
async def update_category(
    category_id: UUID,
    category_in: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Update a category"""
    category = await category_crud.get(db, id=category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    if category_in.name and category_in.name != category.name:
        # Use base CRUD get_by_field method instead of get_by_name
        existing_categories, _ = await category_crud.get_by_field(db, field="name", value=category_in.name, limit=1)
        existing_category = existing_categories[0] if existing_categories else None
        
        if existing_category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category with this name already exists"
            )
    
    category = await category_crud.update(db, db_obj=category, obj_in=category_in)
    return category

@router.delete("/{category_id}")
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """Delete a category (soft delete)"""
    category = await category_crud.get(db, id=category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    await category_crud.soft_delete(db, id=category_id)
    return {"message": "Category deleted successfully"} 