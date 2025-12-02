from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update, func as sql_func, cast, Numeric

from app.crud.base import CRUDBase
from app.models.user_subscription import UserSubscription, SubscriptionStatus
from app.schemas.billing import UserSubscriptionCreate, UserSubscriptionUpdate


class CRUDUserSubscription(CRUDBase[UserSubscription, UserSubscriptionCreate, UserSubscriptionUpdate]):
    async def get_by_user_id_and_period(
        self, 
        db: AsyncSession, 
        user_id: str, 
        billing_period: str
    ) -> Optional[UserSubscription]:
        """Get user subscription by user ID and billing period"""
        result = await db.execute(
            select(self.model).where(
                and_(
                    self.model.supabase_user_id == user_id,
                    self.model.billing_period == billing_period,
                    self.model.is_deleted == False
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_active_subscription(
        self, 
        db: AsyncSession, 
        user_id: str
    ) -> Optional[UserSubscription]:
        """Get the active subscription for a user"""
        result = await db.execute(
            select(self.model)
            .where(
                and_(
                    self.model.supabase_user_id == user_id,
                    self.model.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.LIMIT_REACHED]),
                    self.model.is_deleted == False
                )
            )
            .order_by(self.model.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def increment_usage(
        self, 
        db: AsyncSession, 
        subscription_id: str, 
        tokens: int, 
        cost: float
    ) -> Optional[UserSubscription]:
        """Increment tokens consumed and dollar spent for a subscription (rounded to 3 decimals)"""
        result = await db.execute(
            update(self.model)
            .where(self.model.id == subscription_id)
            .values(
                tokens_consumed=self.model.tokens_consumed + tokens,
                dollar_spent=sql_func.round(cast(self.model.dollar_spent + cost, Numeric), 3)
            )
            .returning(self.model)
        )
        await db.commit()
        return result.scalar_one_or_none()
    
    async def update_status(
        self, 
        db: AsyncSession, 
        subscription_id: str, 
        status: SubscriptionStatus
    ) -> bool:
        """Update subscription status"""
        result = await db.execute(
            update(self.model)
            .where(self.model.id == subscription_id)
            .values(status=status)
        )
        await db.commit()
        return result.rowcount > 0


user_subscription = CRUDUserSubscription(UserSubscription)

