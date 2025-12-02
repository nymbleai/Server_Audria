from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.crud.base import CRUDBase
from app.models.subscription_tier import SubscriptionTier
from app.schemas.billing import SubscriptionTierCreate, SubscriptionTierUpdate


class CRUDSubscriptionTier(CRUDBase[SubscriptionTier, SubscriptionTierCreate, SubscriptionTierUpdate]):
    async def get_by_plan_name(self, db: AsyncSession, plan_name: str) -> Optional[SubscriptionTier]:
        """Get subscription tier by plan name"""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.plan_name == plan_name,
                    self.model.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_by_stripe_price_id(self, db: AsyncSession, stripe_price_id: str) -> Optional[SubscriptionTier]:
        """Get subscription tier by Stripe price ID"""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.stripe_price_id == stripe_price_id,
                    self.model.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()


subscription_tier = CRUDSubscriptionTier(SubscriptionTier)

