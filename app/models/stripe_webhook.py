from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .base import Base, TimestampMixin


class StripeWebhook(Base, TimestampMixin):
    __tablename__ = "stripe_webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    # Stripe event id for idempotency
    event_id = Column(String(255), nullable=False, unique=True, index=True)

    # Core identifiers/status
    stripe_customer_id = Column(String(255), nullable=False, index=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_plan = Column(String(255), nullable=True)  # plan name or price nickname
    subscription_status = Column(String(50), nullable=True)  # active, canceled, past_due, etc

    # Audit of webhook handling
    last_webhook_update = Column(String(100), nullable=True)  # action name from webhook handler
    webhook_timestamp = Column(DateTime, nullable=True)  # when processed locally


