from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class SubscriptionPlan(str, Enum):
    FREE = "free"
    PREMIUM = "premium"

class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    UNPAID = "unpaid"

class CreateCheckoutRequest(BaseModel):
    plan: SubscriptionPlan
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class CheckoutResponse(BaseModel):
    success: bool
    checkout_url: Optional[str] = None
    session_id: Optional[str] = None
    error: Optional[str] = None

class SubscriptionInfo(BaseModel):
    id: str
    customer_id: str
    status: SubscriptionStatus
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    plan_name: Optional[str] = None
    plan_amount: Optional[int] = None

class CustomerResponse(BaseModel):
    success: bool
    customer_id: Optional[str] = None
    subscriptions: Optional[List[SubscriptionInfo]] = None
    error: Optional[str] = None

class BillingPortalRequest(BaseModel):
    return_url: Optional[str] = None

class BillingPortalResponse(BaseModel):
    success: bool
    portal_url: Optional[str] = None
    error: Optional[str] = None

class WebhookEvent(BaseModel):
    id: str
    type: str
    data: Dict[str, Any]
    created: int 