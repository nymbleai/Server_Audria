from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional

from app.crud.base import CRUDBase
from app.models.stripe_webhook import StripeWebhook
from pydantic import BaseModel


class StripeWebhookCreate(BaseModel):
    event_id: str
    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    subscription_plan: Optional[str] = None
    subscription_status: Optional[str] = None
    last_webhook_update: Optional[str] = None
    # webhook_timestamp set server-side by handler when saving


class CRUDStripeWebhook(CRUDBase[StripeWebhook, StripeWebhookCreate, BaseModel]):
    async def get_by_event_id(self, db: AsyncSession, event_id: str) -> Optional[StripeWebhook]:
        result = await db.execute(
            select(self.model).where(and_(self.model.event_id == event_id, self.model.is_deleted == False))
        )
        return result.scalar_one_or_none()


stripe_webhook_crud = CRUDStripeWebhook(StripeWebhook)


