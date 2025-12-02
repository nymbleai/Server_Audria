from fastapi import APIRouter, HTTPException, Depends, status, Request, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import time
import csv
import io
from datetime import datetime, timedelta

from app.schemas.auth import TokenData
from app.schemas.billing import (
    CheckSubscriptionRequest,
    CheckSubscriptionResponse,
    LogUsageRequest,
    LogUsageResponse,
    GetUserSubscriptionResponse,
    GetUsageHistoryResponse,
    SubscriptionStatsResponse,
    SubscriptionTierResponse,
    UserSubscriptionWithTier
)
from app.core.auth import get_current_user
from app.core.database import get_db
from app.services.billing_service import billing_service
from app.services.stripe_service import stripe_service
from app.services.supabase_service import supabase_service
from app.crud import subscription_tier, user_subscription, usage_log, stripe_webhook_crud
from app.crud.stripe_webhook import StripeWebhookCreate

router = APIRouter()


@router.post("/check-subscription", response_model=CheckSubscriptionResponse)
async def check_subscription(
    request: CheckSubscriptionRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check if user has an active subscription and can make a request.
    Returns subscription details and whether the request is allowed.
    """
    try:
        result = await billing_service.check_subscription_limit(
            db,
            user_id=current_user.user_id,
            feature_type=request.feature_type,
            estimated_tokens=request.estimated_tokens
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check subscription: {str(e)}"
        )


@router.post("/log-usage", response_model=LogUsageResponse)
async def log_usage(
    request: LogUsageRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Log token usage for a completed request.
    Updates the user's subscription usage and returns updated stats.
    """
    try:
        result = await billing_service.log_usage(
            db,
            user_id=current_user.user_id,
            feature_type=request.feature_type,
            tokens_used=request.tokens_used,
            request_id=request.request_id,
            meta_data=request.meta_data
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to log usage: {str(e)}"
        )


@router.get("/subscription", response_model=GetUserSubscriptionResponse)
async def get_user_subscription(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current user's subscription details including tier information.
    """
    try:
        # Get current subscription
        subscription, _ = await billing_service.get_or_create_user_subscription(
            db, current_user.user_id
        )
        
        # Get tier details
        tier = await subscription_tier.get_by_plan_name(db, subscription.subscription_plan)
        
        if not tier:
            return GetUserSubscriptionResponse(
                success=False,
                subscription=None,
                message=f"Subscription tier '{subscription.subscription_plan}' not found"
            )
        
        # Create response with tier included
        subscription_with_tier = UserSubscriptionWithTier(
            **subscription.__dict__,
            tier=SubscriptionTierResponse.from_orm(tier)
        )
        
        return GetUserSubscriptionResponse(
            success=True,
            subscription=subscription_with_tier,
            message="Subscription retrieved successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscription: {str(e)}"
        )


@router.get("/stats", response_model=SubscriptionStatsResponse)
async def get_subscription_stats(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive subscription statistics including usage, remaining tokens, etc.
    """
    try:
        stats = await billing_service.get_subscription_stats(db, current_user.user_id)
        
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription statistics not found"
            )
        
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscription stats: {str(e)}"
        )


@router.get("/usage-history", response_model=GetUsageHistoryResponse)
async def get_usage_history(
    days: int = 30,
    skip: int = 0,
    limit: int = 100,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get usage history for the current user.
    Defaults to last 30 days, with pagination.
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get usage logs
        logs, total = await usage_log.get_by_user_id_and_period(
            db,
            user_id=current_user.user_id,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit
        )
        
        # Get summary
        summary = await usage_log.get_usage_summary(
            db,
            user_id=current_user.user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return GetUsageHistoryResponse(
            success=True,
            usage_logs=[log for log in logs],
            total_count=total,
            total_tokens=summary['total_tokens'],
            total_cost=summary['total_cost']
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get usage history: {str(e)}"
        )


@router.get("/export-logs")
async def export_logs(
    range: str = Query("current", description="Export range: current, 7days, 30days, year, all"),
    start_date: Optional[str] = Query(None, description="Custom start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Custom end date (YYYY-MM-DD)"),
    timezone_offset: int = Query(0, description="User's timezone offset in minutes"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Export usage logs as CSV file with streaming for memory efficiency.
    Supports different time ranges and custom date ranges.
    """
    try:
        # Calculate date range based on the 'range' parameter
        now = datetime.utcnow()
        
        if range == "7days":
            start = now - timedelta(days=7)
            end = now
            filename = f"logs_last_7_days_{now.strftime('%Y%m%d')}.csv"
        elif range == "30days":
            start = now - timedelta(days=30)
            end = now
            filename = f"logs_last_30_days_{now.strftime('%Y%m%d')}.csv"
        elif range == "year":
            start = now - timedelta(days=365)
            end = now
            filename = f"logs_last_year_{now.strftime('%Y%m%d')}.csv"
        elif range == "all":
            # Get all logs (set start date to a very old date)
            start = datetime(2020, 1, 1)
            end = now
            filename = f"logs_all_{now.strftime('%Y%m%d')}.csv"
        elif range == "current" or range == "custom":
            # For current/custom, use provided dates or default to last 7 days
            if start_date and end_date:
                try:
                    start = datetime.strptime(start_date, "%Y-%m-%d")
                    end = datetime.strptime(end_date, "%Y-%m-%d")
                    filename = f"logs_custom_{start.strftime('%Y%m%d')}_to_{end.strftime('%Y%m%d')}.csv"
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid date format. Use YYYY-MM-DD"
                    )
            else:
                # Default to last 7 days for current view
                start = now - timedelta(days=7)
                end = now
                filename = f"logs_current_{now.strftime('%Y%m%d')}.csv"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid range parameter. Use: current, 7days, 30days, year, or all"
            )
        
        # Create CSV in memory using StringIO for efficient streaming
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write CSV header
        writer.writerow([
            'Date',
            'Feature Used',
            'Model Used',
            'Tokens Used',
            'Prompt Tokens',
            'Completion Tokens',
            'Total Cost',
            'Status',
            'Latency (ms)',
            'Project ID',
            'File ID'
        ])
        
        # Fetch logs in batches to avoid loading all data into memory
        batch_size = 1000
        skip = 0
        
        while True:
            logs, total = await usage_log.get_by_user_id_and_period(
                db,
                user_id=current_user.user_id,
                start_date=start,
                end_date=end,
                skip=skip,
                limit=batch_size
            )
            
            if not logs:
                break
            
            # Write batch to CSV
            for log in logs:
                # Format feature name
                feature_name = log.feature_used.value if hasattr(log.feature_used, 'value') else str(log.feature_used)
                feature_name = feature_name.replace('_', ' ').title()
                
                # Convert UTC to user's timezone and format as "Oct 28, 2025, 03:33 PM"
                if log.created_at:
                    # Apply timezone offset (offset is in minutes)
                    user_time = log.created_at + timedelta(minutes=timezone_offset)
                    # Format as Oct 28, 2025, 03:33 PM
                    formatted_date = user_time.strftime('%b %d, %Y, %I:%M %p')
                else:
                    formatted_date = 'N/A'
                
                writer.writerow([
                    formatted_date,
                    feature_name,
                    log.model_used or 'N/A',
                    log.tokens_used if log.tokens_used is not None else 'N/A',
                    log.prompt_tokens if log.prompt_tokens is not None else 'N/A',
                    log.completion_tokens if log.completion_tokens is not None else 'N/A',
                    f"${log.dollar_cost:.4f}" if log.dollar_cost is not None else 'N/A',
                    log.status or 'N/A',
                    log.latency_ms if log.latency_ms is not None else 'N/A',
                    (log.project_id or ''),
                    (log.file_id or '')
                ])
            
            skip += batch_size
            
            # If we've fetched all logs, break
            if skip >= total:
                break
        
        # Get the CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Return as streaming response
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export logs: {str(e)}"
        )


@router.get("/tiers")
async def get_subscription_tiers(
    db: AsyncSession = Depends(get_db)
):
    """
    Get all available subscription tiers.
    Public endpoint - no authentication required.
    """
    try:
        tiers, _ = await subscription_tier.get_multi(db, skip=0, limit=100)
        return {
            "success": True,
            "tiers": [SubscriptionTierResponse.from_orm(tier) for tier in tiers]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subscription tiers: {str(e)}"
        )


@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhook events.
    Syncs subscription data with both Supabase and local database.
    """
    try:
        # Get raw body and signature
        payload = await request.body()
        signature = request.headers.get('stripe-signature')
        
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe signature"
            )
        
        # Verify webhook signature
        if not stripe_service.verify_webhook_signature(payload, signature):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Stripe signature"
            )
        
        # Parse event
        import json
        event = json.loads(payload)
        
        # Handle the event via Stripe service parser (normalized fields)
        webhook_result = await stripe_service.handle_webhook_event(event)
        
        if not webhook_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=webhook_result.get("error", "Webhook processing failed")
            )
        
        # Idempotency: store event locally if not seen before
        event_id = event.get("id")
        if event_id:
            existing = await stripe_webhook_crud.get_by_event_id(db, event_id)
            if existing:
                return JSONResponse(content={"success": True, "message": "Event already processed", "action": webhook_result.get("action")})

        # Get user ID from customer
        customer_id = webhook_result.get("customer_id")
        if not customer_id:
            return JSONResponse(content={"success": True, "message": "No customer ID in event"})
        
        # Prefer explicit user_id from event (client_reference_id), fallback to Stripe customer metadata
        user_id = webhook_result.get("user_id") or await stripe_service.get_user_id_from_customer(customer_id)
        if not user_id:
            return JSONResponse(content={"success": True, "message": "User ID not found for customer"})
        
        # Persist webhook locally (no Supabase metadata updates)
        try:
            await stripe_webhook_crud.create_with_extra(
                db,
                obj_in=StripeWebhookCreate(
                    event_id=event_id or "",
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=webhook_result.get("subscription_id"),
                    subscription_plan=webhook_result.get("plan_name"),
                    subscription_status=webhook_result.get("status"),
                    last_webhook_update=webhook_result.get("action")
                ),
                extra_data={
                    "webhook_timestamp": datetime.utcnow()
                }
            )
        except Exception:
            # Don't fail the webhook entirely due to persistence error
            pass

        # Update local database subscription status/plan
        if webhook_result.get("action") in ["subscription_created", "subscription_updated", "subscription_cancelled", "payment_succeeded", "payment_failed"]:
            try:
                await billing_service.update_subscription_from_stripe(
                    db,
                    user_id=user_id,
                    plan_name=("Pro" if webhook_result.get("plan_name") in ("Pro", "premium", "Premium") else (webhook_result.get("plan_name") or "Pro" if webhook_result.get("action") == "payment_succeeded" else "Free")),
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=webhook_result.get("subscription_id", ""),
                    status=webhook_result.get("status", "inactive"),
                    subscription_start_ts=webhook_result.get("subscription_start"),
                    reset_tokens=(webhook_result.get("action") == "payment_succeeded")
                )
            except Exception:
                # Non-fatal; we already stored the webhook event
                pass
        
        return JSONResponse(content={
            "success": True,
            "message": "Webhook processed successfully",
            "action": webhook_result.get("action"),
            "event_id": event_id
        })
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing error: {str(e)}"
        )


@router.get("/health")
async def billing_health_check():
    """Check billing service health"""
    return {
        "success": True,
        "message": "Billing service is operational",
        "timestamp": datetime.utcnow().isoformat()
    }

