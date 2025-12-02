from functools import wraps
from typing import Callable, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.billing_service import billing_service
from app.models.usage_log import FeatureType


class BillingCheckResult:
    """Result of a billing check"""
    def __init__(self, allowed: bool, message: str, tokens_remaining: Optional[int] = None):
        self.allowed = allowed
        self.message = message
        self.tokens_remaining = tokens_remaining


async def check_billing_limit(
    db: AsyncSession,
    user_id: str,
    feature_type: FeatureType,
    estimated_tokens: Optional[int] = None
) -> BillingCheckResult:
    """
    Check if user has sufficient tokens for the request.
    Raises HTTPException if limit is reached.
    """
    result = await billing_service.check_subscription_limit(
        db, 
        user_id, 
        feature_type, 
        estimated_tokens
    )
    
    if not result.allowed:
        print("Subscription limit reached")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "Subscription limit reached",
                "message": result.message,
                "subscription": result.subscription.dict() if result.subscription else None,
                "tier": result.tier.dict() if result.tier else None,
                "tokens_remaining": result.tokens_remaining
            }
        )
    
    return BillingCheckResult(
        allowed=True,
        message=result.message,
        tokens_remaining=result.tokens_remaining
    )


async def log_billing_usage(
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
) -> dict:
    """
    Log token usage for a completed request.
    Returns usage log result.
    """
    result = await billing_service.log_usage(
        db,
        user_id,
        feature_type,
        tokens_used,
        request_id,
        meta_data,
        latency_ms=latency_ms,
        model_used=model_used,
        project_id=project_id,
        file_id=file_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        status=status
    )
    
    return {
        "success": result.success,
        "limit_reached": result.limit_reached,
        "tokens_remaining": None  # This info is available via billing stats endpoint
    }


def with_billing_check(feature_type: FeatureType, estimated_tokens: Optional[int] = None):
    """
    Decorator to check billing limits before executing a function.
    
    Usage:
    @with_billing_check(FeatureType.INGESTION, estimated_tokens=1000)
    async def my_endpoint(...):
        ...
    
    Note: This is a simplified version. For more complex scenarios,
    you may want to use dependency injection instead.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Extract db and user_id from kwargs
            db: Optional[AsyncSession] = kwargs.get('db')
            current_user = kwargs.get('current_user')
            
            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Billing middleware requires 'db' and 'current_user' parameters"
                )
            
            # Check billing limit
            await check_billing_limit(
                db,
                current_user.user_id,
                feature_type,
                estimated_tokens
            )
            
            # Execute the function
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


class BillingDependency:
    """
    FastAPI dependency for checking billing limits.
    
    Usage in router:
    @router.post("/my-endpoint")
    async def my_endpoint(
        billing_check: BillingCheckResult = Depends(BillingDependency(FeatureType.INGESTION)),
        current_user: TokenData = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ):
        # Your endpoint logic here
        pass
    """
    def __init__(self, feature_type: FeatureType, estimated_tokens: Optional[int] = None):
        self.feature_type = feature_type
        self.estimated_tokens = estimated_tokens
    
    async def __call__(
        self,
        db: AsyncSession,
        current_user: Any
    ) -> BillingCheckResult:
        """Check billing limit and return result"""
        return await check_billing_limit(
            db,
            current_user.user_id,
            self.feature_type,
            self.estimated_tokens
        )

