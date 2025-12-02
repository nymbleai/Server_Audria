from typing import Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date
import calendar
from dateutil.relativedelta import relativedelta

from app.crud.token_pricing import token_pricing
from app.crud.subscription_tier import subscription_tier
from app.crud.user_subscription import user_subscription
from app.crud.usage_log import usage_log
from app.models.user_subscription import SubscriptionStatus
from app.models.usage_log import FeatureType
from app.schemas.billing import (
    UsageLogCreate,
    UserSubscriptionCreate,
    CheckSubscriptionResponse,
    LogUsageResponse,
    SubscriptionStatsResponse,
    UserSubscriptionResponse,
    SubscriptionTierResponse,
    UsageLogResponse
)


class BillingService:
    """Service for handling billing operations and usage tracking"""
    
    def __init__(self):
        pass
    
    @staticmethod
    def get_current_billing_period() -> str:
        """Get current billing period in YYYY-MM format"""
        now = datetime.utcnow()
        return now.strftime("%Y-%m")
    
    @staticmethod
    def get_billing_period_start_date(billing_period: str) -> date:
        """Get the start date of a billing period from YYYY-MM format"""
        year, month = map(int, billing_period.split("-"))
        return date(year, month, 1)
    
    @staticmethod
    def get_billing_period_end_date(billing_period: str) -> date:
        """Get the end date of a billing period from YYYY-MM format"""
        year, month = map(int, billing_period.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)
    
    async def get_or_create_user_subscription(
        self, 
        db: AsyncSession, 
        user_id: str,
        default_plan: str = "Free",
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None
    ) -> Tuple[Any, bool]:
        """
        Get or create a user subscription for the current billing period.
        Returns (subscription, created) tuple.
        """
        billing_period = self.get_current_billing_period()
        
        # Try to get existing subscription for this period
        existing = await user_subscription.get_by_user_id_and_period(
            db, user_id, billing_period
        )
        
        if existing:
            return existing, False
        
        # Check if user has a previous subscription to carry over settings
        previous_subscription = await user_subscription.get_active_subscription(db, user_id)
        
        if previous_subscription:
            plan_name = previous_subscription.subscription_plan
            stripe_customer_id = stripe_customer_id or previous_subscription.stripe_customer_id
            stripe_subscription_id = stripe_subscription_id or previous_subscription.stripe_subscription_id
        else:
            plan_name = default_plan
        
        # Create new subscription for current period
        start_date = self.get_billing_period_start_date(billing_period)
        
        new_subscription = await user_subscription.create(
            db,
            obj_in=UserSubscriptionCreate(
                supabase_user_id=user_id,
                subscription_plan=plan_name,
                billing_period=billing_period,
                start_date=start_date,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id
            )
        )
        
        return new_subscription, True
    
    async def check_subscription_limit(
        self, 
        db: AsyncSession, 
        user_id: str,
        feature_type: FeatureType,
        estimated_tokens: Optional[int] = None
    ) -> CheckSubscriptionResponse:
        """
        Check if user can make a request based on their subscription limits.
        """
        # Get or create user subscription
        subscription, created = await self.get_or_create_user_subscription(db, user_id)
        
        # Get subscription tier details
        tier = await subscription_tier.get_by_plan_name(db, subscription.subscription_plan)
        
        if not tier:
            return CheckSubscriptionResponse(
                success=False,
                allowed=False,
                message=f"Subscription tier '{subscription.subscription_plan}' not found",
                subscription=None,
                tier=None
            )
        
        # Check if subscription is active
        if subscription.status == SubscriptionStatus.EXPIRED:
            return CheckSubscriptionResponse(
                success=True,
                allowed=False,
                message="Subscription has expired",
                subscription=UserSubscriptionResponse.from_orm(subscription),
                tier=SubscriptionTierResponse.from_orm(tier),
                tokens_remaining=0
            )
        
        if subscription.status == SubscriptionStatus.CANCELED:
            return CheckSubscriptionResponse(
                success=True,
                allowed=False,
                message="Subscription has been canceled",
                subscription=UserSubscriptionResponse.from_orm(subscription),
                tier=SubscriptionTierResponse.from_orm(tier),
                tokens_remaining=0
            )
        
        if subscription.status == SubscriptionStatus.INACTIVE:
            return CheckSubscriptionResponse(
                success=True,
                allowed=False,
                message="Subscription is inactive",
                subscription=UserSubscriptionResponse.from_orm(subscription),
                tier=SubscriptionTierResponse.from_orm(tier),
                tokens_remaining=0
            )
        
        # Calculate remaining tokens
        tokens_remaining = tier.token_limit - subscription.tokens_consumed
        
        # Check if limit reached
        if subscription.status == SubscriptionStatus.LIMIT_REACHED:
            return CheckSubscriptionResponse(
                success=True,
                allowed=False,
                message="Token limit reached for this billing period",
                subscription=UserSubscriptionResponse.from_orm(subscription),
                tier=SubscriptionTierResponse.from_orm(tier),
                tokens_remaining=0
            )
        
        # Check if estimated tokens would exceed limit
        # if estimated_tokens and (subscription.tokens_consumed + estimated_tokens > tier.token_limit):
        #     return CheckSubscriptionResponse(
        #         success=True,
        #         allowed=False,
        #         message=f"Estimated token usage ({estimated_tokens}) would exceed your limit. Remaining: {tokens_remaining}",
        #         subscription=UserSubscriptionResponse.from_orm(subscription),
        #         tier=SubscriptionTierResponse.from_orm(tier),
        #         tokens_remaining=tokens_remaining
        #     )
        
        # All checks passed
        return CheckSubscriptionResponse(
            success=True,
            allowed=True,
            message="Request allowed",
            subscription=UserSubscriptionResponse.from_orm(subscription),
            tier=SubscriptionTierResponse.from_orm(tier),
            tokens_remaining=tokens_remaining
        )
    
    async def log_usage(
        self, 
        db: AsyncSession, 
        user_id: str,
        feature_type: FeatureType,
        tokens_used: int,
        request_id: Optional[str] = None,
        meta_data: Optional[str] = None,
        *,
        latency_ms: Optional[int] = None,
        model_used: Optional[str] = None,
        project_id: Optional[str] = None,
        file_id: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        status: Optional[str] = None
    ) -> LogUsageResponse:
        """
        Log token usage for a user and update their subscription.
        """
        # Get current token pricing
        pricing = await token_pricing.get_current_pricing(db)
        
        if not pricing:
            return LogUsageResponse(
                success=False,
                message="Token pricing not configured",
                usage_log=None,
                subscription=None,
                limit_reached=False
            )
        
        # Calculate cost (rounded to 3 decimal places)
        dollar_cost = round((tokens_used / 1000.0) * pricing.usd_per_1k_tokens, 3)
        
        # Create usage log entry
        usage_log_entry = await usage_log.create(
            db,
            obj_in=UsageLogCreate(
                supabase_user_id=user_id,
                feature_used=feature_type,
                tokens_used=tokens_used,
                dollar_cost=dollar_cost,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                status=status,
                latency_ms=latency_ms,
                model_used=model_used or "UNKNOWN",
                project_id=project_id,
                file_id=file_id,
                request_id=request_id,
                meta_data=meta_data
            )
        )
        
        # Get or create user subscription
        subscription, _ = await self.get_or_create_user_subscription(db, user_id)
        
        # Update subscription usage
        updated_subscription = await user_subscription.increment_usage(
            db, 
            str(subscription.id), 
            tokens_used, 
            dollar_cost
        )
        
        if not updated_subscription:
            return LogUsageResponse(
                success=False,
                message="Failed to update subscription",
                usage_log=UsageLogResponse.from_orm(usage_log_entry),
                subscription=None,
                limit_reached=False
            )
        
        # Check if limit reached
        tier = await subscription_tier.get_by_plan_name(db, updated_subscription.subscription_plan)
        limit_reached = False
        
        if tier and updated_subscription.tokens_consumed >= tier.token_limit:
            # Update status to limit_reached
            await user_subscription.update_status(
                db, 
                str(updated_subscription.id), 
                SubscriptionStatus.LIMIT_REACHED
            )
            updated_subscription.status = SubscriptionStatus.LIMIT_REACHED
            limit_reached = True
        
        return LogUsageResponse(
            success=True,
            message="Usage logged successfully",
            usage_log=UsageLogResponse.from_orm(usage_log_entry),
            subscription=UserSubscriptionResponse.from_orm(updated_subscription),
            limit_reached=limit_reached
        )
    
    async def get_subscription_stats(
        self, 
        db: AsyncSession, 
        user_id: str
    ) -> Optional[SubscriptionStatsResponse]:
        """
        Get comprehensive subscription statistics for a user.
        """
        # Get current subscription
        subscription, _ = await self.get_or_create_user_subscription(db, user_id)
        
        # Get tier details
        tier = await subscription_tier.get_by_plan_name(db, subscription.subscription_plan)
        
        if not tier:
            return None
        
        # Calculate stats
        remaining_tokens = max(0, tier.token_limit - subscription.tokens_consumed)
        percentage_used = (subscription.tokens_consumed / tier.token_limit * 100) if tier.token_limit > 0 else 0
        
        # Calculate days remaining in billing period
        end_date = self.get_billing_period_end_date(subscription.billing_period)
        today = date.today()
        days_remaining = (end_date - today).days if end_date >= today else 0
        
        return SubscriptionStatsResponse(
            subscription={
                **UserSubscriptionResponse.from_orm(subscription).dict(),
                "tier": SubscriptionTierResponse.from_orm(tier)
            },
            usage_this_period=subscription.tokens_consumed,
            dollar_spent_this_period=subscription.dollar_spent,
            remaining_tokens=remaining_tokens,
            percentage_used=round(percentage_used, 2),
            status=subscription.status,
            days_remaining=days_remaining
        )
    
    async def update_subscription_from_stripe(
        self, 
        db: AsyncSession, 
        user_id: str,
        plan_name: str,
        stripe_customer_id: str,
        stripe_subscription_id: str,
        status: str,
        subscription_start_ts: Optional[int] = None,
        reset_tokens: bool = False
    ) -> bool:
        """
        Update user subscription based on Stripe webhook data.
        """
        # Map Stripe status to our status
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "canceled": SubscriptionStatus.CANCELED,
            "incomplete": SubscriptionStatus.INACTIVE,
            "incomplete_expired": SubscriptionStatus.EXPIRED,
            "past_due": SubscriptionStatus.INACTIVE,
            "trialing": SubscriptionStatus.ACTIVE,
            "unpaid": SubscriptionStatus.INACTIVE
        }
        
        subscription_status = status_map.get(status, SubscriptionStatus.INACTIVE)
        
        # Determine billing period and start_date – prefer Stripe subscription start if provided
        desired_start_date: Optional[date] = None
        if subscription_start_ts:
            try:
                desired_start_date = datetime.utcfromtimestamp(subscription_start_ts).date()
            except Exception:
                desired_start_date = None
        # Get current subscription
        subscription, created = await self.get_or_create_user_subscription(
            db, 
            user_id,
            default_plan=plan_name,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id
        )
        
        # Update subscription
        updated = await user_subscription.update_by_id(
            db,
            id=subscription.id,
            obj_in={
                "subscription_plan": plan_name,
                "status": subscription_status,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": stripe_subscription_id
            }
        )

        # If we have a specific start_date from Stripe, align the billing period and start_date
        if desired_start_date and updated:
            explicit_billing_period = desired_start_date.strftime("%Y-%m")
            await user_subscription.update_by_id(
                db,
                id=updated.id,
                obj_in={
                    "billing_period": explicit_billing_period,
                    "start_date": desired_start_date
                }
            )
        
        # If renewal succeeded and reset requested, zero out tokens for current period
        if reset_tokens and updated:
            await user_subscription.update_by_id(
                db,
                id=updated.id,
                obj_in={
                    "tokens_consumed": 0,
                    "dollar_spent": 0.0
                }
            )
        
        return True


# Create singleton instance
billing_service = BillingService()

