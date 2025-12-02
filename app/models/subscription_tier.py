from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .base import Base, TimestampMixin

class SubscriptionTier(Base, TimestampMixin):
    """Reference table for subscription plan definitions"""
    __tablename__ = "subscription_tiers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    plan_name = Column(String(100), nullable=False, unique=True, index=True)  # Free, Pro, Enterprise
    token_limit = Column(Integer, nullable=False)  # Tokens allowed per billing cycle
    billing_cycle = Column(String(50), nullable=False)  # Monthly, Annual
    stripe_price_id = Column(String(255), nullable=True)  # Corresponding Stripe pricing ID
    description = Column(Text, nullable=True)  # Human-readable summary of plan features

