from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime

from app.crud.base import CRUDBase
from app.models.token_pricing import TokenPricing
from app.schemas.billing import TokenPricingCreate, TokenPricingUpdate


class CRUDTokenPricing(CRUDBase[TokenPricing, TokenPricingCreate, TokenPricingUpdate]):
    async def get_current_pricing(self, db: AsyncSession) -> Optional[TokenPricing]:
        """Get the current active token pricing based on effective date"""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.is_deleted == False,
                    self.model.effective_date <= datetime.utcnow()
                )
            )
            .order_by(self.model.effective_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


token_pricing = CRUDTokenPricing(TokenPricing)

