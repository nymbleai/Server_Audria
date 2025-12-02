from sqlalchemy import Column, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from .base import Base, TimestampMixin

class TokenPricing(Base, TimestampMixin):
    """Reference table for token pricing"""
    __tablename__ = "token_pricing"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    usd_per_1k_tokens = Column(Float, nullable=False)  # Cost per 1,000 tokens (e.g., 0.02)
    effective_date = Column(DateTime, nullable=False)  # Date from which the rate applies

