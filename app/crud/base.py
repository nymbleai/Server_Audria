from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union, Tuple
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from app.models.base import Base
from app.core.exceptions import NotFoundError
from uuid import UUID

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: Any, *, raise_if_not_found: bool = True) -> Optional[ModelType]:
        """Get a single record by ID (not soft deleted)"""
        result = await db.execute(
            select(self.model).where(
                and_(self.model.id == id, self.model.is_deleted == False)
            )
        )
        obj = result.scalar_one_or_none()
        
        if raise_if_not_found and obj is None:
            raise NotFoundError(f"{self.model.__name__}")
        
        return obj

    async def get_by_user_id(self, db: AsyncSession, id: Any, user_id: str, *, raise_if_not_found: bool = True) -> Optional[ModelType]:
        """Get a single record by ID and user_id (not soft deleted)"""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.id == id, 
                    self.model.user_id == user_id,
                    self.model.is_deleted == False
                )
            )
        )
        obj = result.scalar_one_or_none()
        
        if raise_if_not_found and obj is None:
            raise NotFoundError(f"{self.model.__name__}")
        
        return obj

    async def get_multi(
        self, 
        db: AsyncSession, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = True,
        include_deleted: bool = False
    ) -> Tuple[List[ModelType], int]:
        """Get multiple records with pagination and filtering"""
        if include_deleted:
            query = select(self.model)
        else:
            query = select(self.model).where(self.model.is_deleted == False)
        
        # Apply filters
        if filters:
            filter_conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, (list, tuple)):
                        filter_conditions.append(getattr(self.model, field).in_(value))
                    elif isinstance(value, dict):
                        # Handle range queries like {"gte": 10, "lte": 20}
                        field_obj = getattr(self.model, field)
                        for op, val in value.items():
                            if op == "gte":
                                filter_conditions.append(field_obj >= val)
                            elif op == "lte":
                                filter_conditions.append(field_obj <= val)
                            elif op == "gt":
                                filter_conditions.append(field_obj > val)
                            elif op == "lt":
                                filter_conditions.append(field_obj < val)
                            elif op == "like":
                                filter_conditions.append(field_obj.like(f"%{val}%"))
                            elif op == "ilike":
                                filter_conditions.append(field_obj.ilike(f"%{val}%"))
                    else:
                        filter_conditions.append(getattr(self.model, field) == value)
            
            if filter_conditions:
                query = query.where(and_(*filter_conditions))
        
        # Get total count for pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            order_field = getattr(self.model, order_by)
            if order_desc:
                query = query.order_by(order_field.desc())
            else:
                query = query.order_by(order_field.asc())
        else:
            # Default ordering by created_at desc
            query = query.order_by(self.model.created_at.desc())
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        return items, total

    async def get_by_field(
        self, 
        db: AsyncSession, 
        *, 
        field: str, 
        value: Any,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[ModelType], int]:
        """Get records by a specific field value with pagination (not soft deleted)"""
        if not hasattr(self.model, field):
            raise ValueError(f"Field '{field}' does not exist on model {self.model.__name__}")
        
        return await self.get_multi(
            db, 
            skip=skip, 
            limit=limit, 
            filters={field: value}
        )

    async def get_by_fields(
        self, 
        db: AsyncSession, 
        *, 
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[ModelType], int]:
        """Get records by multiple field values with pagination (not soft deleted)"""
        return await self.get_multi(
            db, 
            skip=skip, 
            limit=limit, 
            filters=filters
        )

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        """Create a new record"""
        # Use model_dump() to preserve Python types (date, datetime, etc.)
        # instead of jsonable_encoder which converts them to strings
        if hasattr(obj_in, 'model_dump'):
            obj_in_data = obj_in.model_dump(exclude_unset=True)
        elif hasattr(obj_in, 'dict'):
            obj_in_data = obj_in.dict(exclude_unset=True)
        else:
            obj_in_data = jsonable_encoder(obj_in)
        
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def create_with_extra(self, db: AsyncSession, *, obj_in: CreateSchemaType, extra_data: Dict[str, Any]) -> ModelType:
        """Create a new record with additional fields"""
        # Use model_dump() to preserve Python types (date, datetime, etc.)
        if hasattr(obj_in, 'model_dump'):
            obj_in_data = obj_in.model_dump(exclude_unset=True)
        elif hasattr(obj_in, 'dict'):
            obj_in_data = obj_in.dict(exclude_unset=True)
        else:
            obj_in_data = jsonable_encoder(obj_in)
        
        obj_in_data.update(extra_data)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def create_multi(
        self, 
        db: AsyncSession, 
        *, 
        objs_in: List[CreateSchemaType]
    ) -> List[ModelType]:
        """Create multiple records"""
        db_objs = []
        for obj_in in objs_in:
            # Use model_dump() to preserve Python types (date, datetime, etc.)
            if hasattr(obj_in, 'model_dump'):
                obj_in_data = obj_in.model_dump(exclude_unset=True)
            elif hasattr(obj_in, 'dict'):
                obj_in_data = obj_in.dict(exclude_unset=True)
            else:
                obj_in_data = jsonable_encoder(obj_in)
            
            db_obj = self.model(**obj_in_data)
            db_objs.append(db_obj)
        
        db.add_all(db_objs)
        await db.commit()
        
        # Refresh all objects
        for db_obj in db_objs:
            await db.refresh(db_obj)
        
        return db_objs

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Update a record"""
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_by_id(
        self,
        db: AsyncSession,
        *,
        id: Any,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]],
        raise_if_not_found: bool = True
    ) -> Optional[ModelType]:
        """Update a record by ID"""
        db_obj = await self.get(db, id=id, raise_if_not_found=raise_if_not_found)
        if db_obj:
            return await self.update(db, db_obj=db_obj, obj_in=obj_in)
        return None

    async def update_by_field(
        self,
        db: AsyncSession,
        *,
        field: str,
        value: Any,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> List[ModelType]:
        """Update records by field value"""
        items, _ = await self.get_by_field(db, field=field, value=value)
        updated_items = []
        for item in items:
            updated_item = await self.update(db, db_obj=item, obj_in=obj_in)
            updated_items.append(updated_item)
        return updated_items

    async def soft_delete(self, db: AsyncSession, *, id: Any, raise_if_not_found: bool = True) -> bool:
        """Soft delete a record by ID"""
        result = await db.execute(
            update(self.model).where(
                and_(
                    self.model.id == id,
                    self.model.is_deleted == False
                )
            ).values(is_deleted=True)
        )
        
        await db.commit()
        rows_affected = result.rowcount
        
        if raise_if_not_found and rows_affected == 0:
            raise NotFoundError(f"{self.model.__name__}")
        
        return rows_affected > 0

    async def soft_delete_by_user_id(self, db: AsyncSession, *, id: Any, user_id: str, raise_if_not_found: bool = True) -> bool:
        """Soft delete a record by ID and user_id"""
        result = await db.execute(
            update(self.model).where(
                and_(
                    self.model.id == id,
                    self.model.user_id == user_id,
                    self.model.is_deleted == False
                )
            ).values(is_deleted=True)
        )
        
        await db.commit()
        rows_affected = result.rowcount
        
        if raise_if_not_found and rows_affected == 0:
            raise NotFoundError(f"{self.model.__name__}")
        
        return rows_affected > 0

    async def remove(self, db: AsyncSession, *, id: Any, raise_if_not_found: bool = True) -> bool:
        """Hard delete a record by ID"""
        result = await db.execute(
            delete(self.model).where(
                and_(
                    self.model.id == id,
                    self.model.is_deleted == False
                )
            )
        )
        
        await db.commit()
        rows_affected = result.rowcount
        
        if raise_if_not_found and rows_affected == 0:
            raise NotFoundError(f"{self.model.__name__}")
        
        return rows_affected > 0

    async def remove_by_field(
        self, 
        db: AsyncSession, 
        *, 
        field: str, 
        value: Any
    ) -> int:
        """Hard delete records by field value"""
        items, _ = await self.get_by_field(db, field=field, value=value)
        deleted_count = 0
        for item in items:
            await db.delete(item)
            deleted_count += 1
        await db.commit()
        return deleted_count

    async def exists(self, db: AsyncSession, *, id: Any) -> bool:
        """Check if a record exists by ID (not soft deleted)"""
        result = await db.execute(
            select(func.count()).where(
                and_(self.model.id == id, self.model.is_deleted == False)
            )
        )
        return result.scalar() > 0

    async def exists_by_field(
        self, 
        db: AsyncSession, 
        *, 
        field: str, 
        value: Any
    ) -> bool:
        """Check if a record exists by field value (not soft deleted)"""
        if not hasattr(self.model, field):
            raise ValueError(f"Field '{field}' does not exist on model {self.model.__name__}")
        
        result = await db.execute(
            select(func.count()).where(
                and_(
                    getattr(self.model, field) == value,
                    self.model.is_deleted == False
                )
            )
        )
        return result.scalar() > 0

    async def count(
        self, 
        db: AsyncSession, 
        *, 
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Count records with optional filters (not soft deleted)"""
        query = select(func.count()).where(self.model.is_deleted == False)
        
        if filters:
            filter_conditions = []
            for field, value in filters.items():
                if hasattr(self.model, field):
                    if isinstance(value, (list, tuple)):
                        filter_conditions.append(getattr(self.model, field).in_(value))
                    else:
                        filter_conditions.append(getattr(self.model, field) == value)
            
            if filter_conditions:
                query = query.where(and_(*filter_conditions))
        
        result = await db.execute(query)
        return result.scalar()

    async def get_with_relations(
        self, 
        db: AsyncSession, 
        *, 
        id: Any, 
        relations: List[str],
        raise_if_not_found: bool = True
    ) -> Optional[ModelType]:
        """Get a record with loaded relations (not soft deleted)"""
        query = select(self.model).where(
            and_(self.model.id == id, self.model.is_deleted == False)
        )
        
        for relation in relations:
            if hasattr(self.model, relation):
                query = query.options(selectinload(getattr(self.model, relation)))
        
        result = await db.execute(query)
        obj = result.scalar_one_or_none()
        
        if raise_if_not_found and obj is None:
            raise NotFoundError(f"{self.model.__name__}")
        
        return obj 