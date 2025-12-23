from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.person import Person, PersonDetails
from app.crud.base import CRUDBase
from app.schemas.person import PersonCreate, PersonUpdate, PersonDetailsCreate, PersonDetailsUpdate


class CRUDPerson(CRUDBase[Person, PersonCreate, PersonUpdate]):
    """CRUD operations for Person model"""
    
    async def get_by_user_id(
        self, 
        db: AsyncSession, 
        *, 
        user_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Person]:
        """Get all persons for a specific user"""
        result = await db.execute(
            select(self.model)
            .where(self.model.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(self.model.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_by_id_and_user(
        self,
        db: AsyncSession,
        *,
        person_id: UUID,
        user_id: UUID
    ) -> Optional[Person]:
        """Get a person by ID, ensuring it belongs to the user"""
        result = await db.execute(
            select(self.model)
            .where(self.model.id == person_id)
            .where(self.model.user_id == user_id)
        )
        return result.scalar_one_or_none()


class CRUDPersonDetails(CRUDBase[PersonDetails, PersonDetailsCreate, PersonDetailsUpdate]):
    """CRUD operations for PersonDetails model"""
    
    async def get_by_person_id(
        self,
        db: AsyncSession,
        *,
        person_id: UUID
    ) -> Optional[PersonDetails]:
        """Get person details by person_id"""
        result = await db.execute(
            select(self.model)
            .where(self.model.person_id == person_id)
        )
        return result.scalar_one_or_none()
    
    async def upsert_by_person_id(
        self,
        db: AsyncSession,
        *,
        person_id: UUID,
        data: dict
    ) -> PersonDetails:
        """Create or update person details for a person"""
        existing = await self.get_by_person_id(db, person_id=person_id)
        
        if existing:
            # Update existing
            existing.data = data
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            # Create new
            obj_in = PersonDetailsCreate(person_id=person_id, data=data)
            return await self.create(db, obj_in=obj_in)


# Create instances
person_crud = CRUDPerson(Person)
person_details_crud = CRUDPersonDetails(PersonDetails)

