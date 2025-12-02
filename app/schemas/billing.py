from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID
from enum import Enum

# Enums
class SubscriptionStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    CANCELED = "canceled"
    LIMIT_REACHED = "limit_reached"

class FeatureTypeEnum(str, Enum):
    INGESTION = "ingestion"
    REVISION = "revision"
    ORCHESTRATOR = "orchestrator"
    CHAT = "chat"
    PRECEDENT_SEARCH = "precedent_search"
    PRECEDENT_EMBED = "precedent_embed"

# Token Pricing Schemas
class TokenPricingBase(BaseModel):
    usd_per_1k_tokens: float = Field(..., description="Cost per 1,000 tokens")
    effective_date: datetime = Field(..., description="Date from which the rate applies")

class TokenPricingCreate(TokenPricingBase):
    pass

class TokenPricingUpdate(BaseModel):
    usd_per_1k_tokens: Optional[float] = None
    effective_date: Optional[datetime] = None

class TokenPricingResponse(TokenPricingBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Subscription Tier Schemas
class SubscriptionTierBase(BaseModel):
    plan_name: str = Field(..., description="Plan name (Free, Pro, Enterprise)")
    token_limit: int = Field(..., description="Tokens allowed per billing cycle")
    billing_cycle: str = Field(..., description="Billing cycle (Monthly, Annual)")
    stripe_price_id: Optional[str] = Field(None, description="Stripe price ID")
    description: Optional[str] = Field(None, description="Plan description")

class SubscriptionTierCreate(SubscriptionTierBase):
    pass

class SubscriptionTierUpdate(BaseModel):
    plan_name: Optional[str] = None
    token_limit: Optional[int] = None
    billing_cycle: Optional[str] = None
    stripe_price_id: Optional[str] = None
    description: Optional[str] = None

class SubscriptionTierResponse(SubscriptionTierBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# User Subscription Schemas
class UserSubscriptionBase(BaseModel):
    supabase_user_id: str
    subscription_plan: str
    tokens_consumed: int = 0
    dollar_spent: float = 0.0
    status: SubscriptionStatusEnum
    billing_period: str = Field(..., description="Format: YYYY-MM")
    start_date: date
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

class UserSubscriptionCreate(BaseModel):
    supabase_user_id: str
    subscription_plan: str
    billing_period: str
    start_date: date
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

class UserSubscriptionUpdate(BaseModel):
    subscription_plan: Optional[str] = None
    tokens_consumed: Optional[int] = None
    dollar_spent: Optional[float] = None
    status: Optional[SubscriptionStatusEnum] = None
    billing_period: Optional[str] = None
    start_date: Optional[date] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None

class UserSubscriptionResponse(UserSubscriptionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserSubscriptionWithTier(UserSubscriptionResponse):
    """User subscription with tier details"""
    tier: Optional[SubscriptionTierResponse] = None

# Usage Log Schemas
class UsageLogBase(BaseModel):
    supabase_user_id: str
    feature_used: FeatureTypeEnum
    tokens_used: int
    dollar_cost: float
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    status: Optional[str] = None
    latency_ms: Optional[int] = None
    model_used: Optional[str] = None
    project_id: Optional[str] = None
    file_id: Optional[str] = None
    request_id: Optional[str] = None
    meta_data: Optional[str] = None

class UsageLogCreate(UsageLogBase):
    pass

class UsageLogUpdate(BaseModel):
    tokens_used: Optional[int] = None
    dollar_cost: Optional[float] = None
    meta_data: Optional[str] = None

class UsageLogResponse(UsageLogBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Request/Response Schemas for API endpoints
class CheckSubscriptionRequest(BaseModel):
    feature_type: FeatureTypeEnum
    estimated_tokens: Optional[int] = Field(None, description="Estimated tokens for this request")

class CheckSubscriptionResponse(BaseModel):
    success: bool
    allowed: bool
    message: str
    subscription: Optional[UserSubscriptionResponse] = None
    tier: Optional[SubscriptionTierResponse] = None
    tokens_remaining: Optional[int] = None

class LogUsageRequest(BaseModel):
    feature_type: FeatureTypeEnum
    tokens_used: int
    request_id: Optional[str] = None
    meta_data: Optional[str] = None

class LogUsageResponse(BaseModel):
    success: bool
    message: str
    usage_log: Optional[UsageLogResponse] = None
    subscription: Optional[UserSubscriptionResponse] = None
    limit_reached: bool = False

class GetUserSubscriptionResponse(BaseModel):
    success: bool
    subscription: Optional[UserSubscriptionWithTier] = None
    message: Optional[str] = None

class GetUsageHistoryResponse(BaseModel):
    success: bool
    usage_logs: List[UsageLogResponse]
    total_count: int
    total_tokens: int
    total_cost: float

class SubscriptionStatsResponse(BaseModel):
    """Comprehensive subscription statistics"""
    subscription: UserSubscriptionWithTier
    usage_this_period: int
    dollar_spent_this_period: float
    remaining_tokens: int
    percentage_used: float
    status: SubscriptionStatusEnum
    days_remaining: Optional[int] = None

