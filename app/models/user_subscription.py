from sqlalchemy import Column, String, Integer, Float, Date, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
from .base import Base, TimestampMixin

class SubscriptionStatus(str, enum.Enum):
    """Subscription status enum"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    CANCELED = "canceled"
    LIMIT_REACHED = "limit_reached"

class UserSubscription(Base, TimestampMixin):
    """Aggregates total token and dollar usage per billing cycle"""
    __tablename__ = "user_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    supabase_user_id = Column(String, nullable=False, index=True)  # References user in Supabase
    subscription_plan = Column(String(100), nullable=False)  # Active plan name (Free, Pro, Enterprise)
    tokens_consumed = Column(Integer, default=0, nullable=False)  # Tokens consumed in cycle
    dollar_spent = Column(Float, default=0.0, nullable=False)  # Dollar cost accumulated in cycle
    status = Column(SQLEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)
    billing_period = Column(String(20), nullable=False)  # Format: YYYY-MM
    start_date = Column(Date, nullable=False)  # Billing cycle start
    
    # Stripe-related fields
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)

