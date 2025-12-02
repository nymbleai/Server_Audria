from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import JSONResponse
from app.schemas.subscription import (
    CreateCheckoutRequest, 
    CheckoutResponse, 
    BillingPortalRequest, 
    BillingPortalResponse,
    SubscriptionPlan
)
from app.schemas.auth import TokenData
from app.services.stripe_service import stripe_service
from app.services.supabase_service import supabase_service
from app.core.auth import get_current_user
from app.core.config import settings
import json
import stripe
import time
from typing import Dict, Any
from datetime import datetime
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.billing_service import billing_service
from app.crud import stripe_webhook_crud
from app.crud.stripe_webhook import StripeWebhookCreate

# Initialize Stripe API key
if settings.stripe_secret:
    stripe.api_key = settings.stripe_secret

# Remove caching - we'll use Supabase as source of truth

router = APIRouter()

async def get_or_create_stripe_customer(current_user: TokenData) -> Dict[str, Any]:
    """Get existing Stripe customer or create a new one"""
    try:
        # First, try to find existing customer by email
        customers = stripe.Customer.list(email=current_user.email, limit=1)
        
        if customers.data:
            # Customer exists, return it
            customer = customers.data[0]
            
            # Ensure metadata.user_id matches current Supabase user
            if customer.metadata.get("user_id") != current_user.user_id:
                stripe.Customer.modify(
                    customer.id,
                    metadata={"user_id": current_user.user_id}
                )
            
            return {
                "success": True,
                "customer": customer
            }
        else:
            # Customer doesn't exist, create new one
            return await stripe_service.create_customer(
                email=current_user.email,
                name=getattr(current_user, 'name', None),
                user_id=current_user.user_id
            )
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def update_user_subscription_status(customer_id: str, webhook_result: Dict[str, Any]):
    """Update user subscription status in Supabase based on Stripe webhook"""
    print(f"🔄 Processing webhook update for customer: {customer_id}")
    print(f"🔄 Webhook action: {webhook_result.get('action')}")
    
    try:
        # Get customer details from Stripe to find the user
        customer = stripe.Customer.retrieve(customer_id)
        user_id = customer.metadata.get("user_id")
        
        print(f"🔄 Customer metadata: {customer.metadata}")
        print(f"🔄 Found user_id: {user_id}")
        
        if not user_id:
            print(f"❌ Warning: No user_id found in Stripe customer {customer_id} metadata")
            print(f"❌ Customer email: {customer.email}")
            return
        
        # Determine subscription plan and status based on webhook action
        subscription_plan = "free"
        subscription_status = "inactive"
        
        if webhook_result.get("action") in ["subscription_created", "subscription_updated"]:
            subscription = webhook_result.get("subscription", {})
            if subscription.get("status") in ["active", "trialing"]:
                subscription_plan = "premium"
                subscription_status = subscription.get("status", "active")
        elif webhook_result.get("action") == "payment_succeeded":
            subscription_plan = "premium"
            subscription_status = "active"
        elif webhook_result.get("action") == "subscription_cancelled":
            subscription_plan = "free"
            subscription_status = "cancelled"
        
        print(f"🔄 Determined plan: {subscription_plan}, status: {subscription_status}")
        
        # Update user metadata in Supabase
        metadata_update = {
            "stripe_customer_id": customer_id,
            "subscription_plan": subscription_plan,
            "subscription_status": subscription_status,
            "last_webhook_update": webhook_result.get("action"),
            "webhook_timestamp": str(int(time.time()))
        }
        
        print(f"🔄 Updating Supabase user {user_id} with: {metadata_update}")
        
        update_result = await supabase_service.update_user_metadata(user_id, metadata_update)
        
        print(f"🔄 Supabase update result: {update_result}")
        
        if update_result["success"]:
            print(f"✅ Successfully updated user {user_id} subscription: {subscription_plan} ({subscription_status})")
        else:
            print(f"❌ Failed to update user {user_id} subscription: {update_result.get('error')}")
            
    except Exception as e:
        print(f"❌ Error updating user subscription status: {str(e)}")
        import traceback
        traceback.print_exc()

@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout_session(
    checkout_request: CreateCheckoutRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a Stripe checkout session for subscription"""
    try:
        # Get or create Stripe customer for user
        customer_result = await get_or_create_stripe_customer(current_user)
        
        if not customer_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create customer"
            )
        
        customer_id = customer_result["customer"]["id"]
        
        # Set default URLs if not provided
        success_url = checkout_request.success_url or f"{settings.frontend_url}/subscription/success"
        cancel_url = checkout_request.cancel_url or f"{settings.frontend_url}/subscription/cancel"
        
        # Create checkout session
        session_result = await stripe_service.create_checkout_session(
            customer_id=customer_id,
            plan=checkout_request.plan,
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=current_user.user_id
        )
        
        if not session_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=session_result.get("error", "Failed to create checkout session")
            )
        
        return CheckoutResponse(
            success=True,
            checkout_url=session_result["checkout_url"],
            session_id=session_result["session"]["id"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.post("/billing-portal", response_model=BillingPortalResponse)
async def create_billing_portal_session(
    portal_request: BillingPortalRequest,
    current_user: TokenData = Depends(get_current_user)
):
    """Create a Stripe billing portal session for subscription management"""
    try:
        # Get or create Stripe customer for user
        customer_result = await get_or_create_stripe_customer(current_user)
        
        if not customer_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get customer information"
            )
        
        customer_id = customer_result["customer"]["id"]
        
        # Set default return URL if not provided
        return_url = portal_request.return_url or f"{settings.frontend_url}/subscription"
        
        # Create billing portal session
        portal_result = await stripe_service.create_billing_portal_session(
            customer_id=customer_id,
            return_url=return_url
        )
        
        if not portal_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=portal_result.get("error", "Failed to create billing portal session")
            )
        
        return BillingPortalResponse(
            success=True,
            portal_url=portal_result["portal_url"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/status")
async def get_subscription_status(current_user: TokenData = Depends(get_current_user)):
    """Get current user's subscription status from Supabase (fast and reliable)"""
    try:
        # First try to get from Supabase user metadata (updated by webhooks)
        return await get_subscription_status_from_supabase(current_user)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

async def get_subscription_status_from_supabase(current_user: TokenData):
    """Get subscription status from Supabase user metadata (fast and reliable)"""
    try:
        # Get user metadata from Supabase
        user_result = await supabase_service.get_user_by_id(current_user.user_id)
        
        if user_result["success"] and user_result.get("user"):
            user_data = user_result["user"]
            user_metadata = user_data.get("raw_user_meta_data", {}) or {}
            
            # Get subscription info from metadata (updated by webhooks)
            subscription_plan = user_metadata.get("subscription_plan", "free")
            subscription_status = user_metadata.get("subscription_status", "none")
            
            return JSONResponse(
                content={
                    "success": True,
                    "subscription_plan": subscription_plan,
                    "subscription_status": subscription_status,
                    "source": "supabase",
                    "last_webhook_update": user_metadata.get("last_webhook_update")
                }
            )
        else:
            # User not found in Supabase, fallback to Stripe
            return await get_subscription_status_from_stripe(current_user)
            
    except Exception as e:
        # If Supabase fails, fallback to Stripe
        print(f"❌ Supabase lookup failed, falling back to Stripe: {str(e)}")
        return await get_subscription_status_from_stripe(current_user)

async def get_subscription_status_from_stripe(current_user: TokenData):
    """Get subscription status directly from Stripe (slower fallback)"""
    try:
        # Only get existing customer, don't create new one for status check
        customers = stripe.Customer.list(email=current_user.email, limit=1)
        
        if not customers.data:
            return JSONResponse(
                content={
                    "success": True,
                    "subscription_plan": "free",
                    "subscription_status": "none",
                    "source": "stripe"
                }
            )
        
        customer_id = customers.data[0].id
        
        # Get subscriptions
        subs_result = await stripe_service.get_customer_subscriptions(customer_id)
        
        if not subs_result["success"] or not subs_result["subscriptions"]:
            return JSONResponse(
                content={
                    "success": True,
                    "subscription_plan": "free",
                    "subscription_status": "none",
                    "source": "stripe"
                }
            )
        
        # Get the most recent active subscription
        active_subscription = None
        for sub in subs_result["subscriptions"]:
            if sub["status"] in ["active", "trialing"]:
                active_subscription = sub
                break
        
        if active_subscription:
            return JSONResponse(
                content={
                    "success": True,
                    "subscription_plan": "premium",
                    "subscription_status": active_subscription["status"],
                    "current_period_end": active_subscription["current_period_end"],
                    "cancel_at_period_end": active_subscription.get("cancel_at_period_end", False),
                    "source": "stripe"
                }
            )
        else:
            return JSONResponse(
                content={
                    "success": True,
                    "subscription_plan": "free",
                    "subscription_status": "inactive",
                    "source": "stripe"
                }
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@router.get("/webhook/test")
async def test_webhook_endpoint():
    """Test endpoint to verify webhook URL is reachable"""
    return JSONResponse(content={
        "success": True,
        "message": "Webhook endpoint is reachable",
        "webhook_secret_configured": bool(settings.stripe_webhook_secret)
    })

@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhooks (compat endpoint). Persists events and updates local subscription."""
    try:
        payload = await request.body()
        sig_header = request.headers.get('stripe-signature')
        print(f"🔔 [/subscriptions/webhook] Received Stripe webhook: {len(payload)} bytes")
        if not sig_header:
            print("❌ Missing stripe-signature header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing stripe-signature header"
            )
        
        # Verify webhook signature
        if not stripe_service.verify_webhook_signature(payload, sig_header):
            print("❌ Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature"
            )
        
        # Parse the event
        event = json.loads(payload)
        event_id = event.get('id')
        print(f"🔔 Event type: {event.get('type')} id={event_id}")

        # Idempotency check using our DB
        if event_id:
            existing = await stripe_webhook_crud.get_by_event_id(db, event_id)
            if existing:
                return JSONResponse(content={"success": True, "received": True, "event_id": event_id, "message": "Event already processed"})

        # Parse
        webhook_result = await stripe_service.handle_webhook_event(event)
        if not webhook_result.get("success"):
            return JSONResponse(content={"success": False, "message": webhook_result.get("error", "Unhandled event")}, status_code=200)

        customer_id = webhook_result.get("customer_id")
        # Persist to stripe_webhooks
        try:
            await stripe_webhook_crud.create_with_extra(
                db,
                obj_in=StripeWebhookCreate(
                    event_id=event_id or "",
                    stripe_customer_id=customer_id or "",
                    stripe_subscription_id=webhook_result.get("subscription_id"),
                    subscription_plan=webhook_result.get("plan_name"),
                    subscription_status=webhook_result.get("status"),
                    last_webhook_update=webhook_result.get("action")
                ),
                extra_data={"webhook_timestamp": datetime.utcnow()}
            )
        except Exception:
            pass

        # Try to map to user and update local subscription
        try:
            if customer_id:
                # Find user_id via Stripe customer metadata
                customer = stripe.Customer.retrieve(customer_id)
                user_id = customer.metadata.get("user_id")
                if user_id:
                    await billing_service.update_subscription_from_stripe(
                        db=db,
                        user_id=user_id,
                        plan_name=("Pro" if webhook_result.get("plan_name") in ("Pro", "premium", "Premium") else (webhook_result.get("plan_name") or "Pro" if webhook_result.get("action") == "payment_succeeded" else "Free")),
                        stripe_customer_id=customer_id,
                        stripe_subscription_id=webhook_result.get("subscription_id", ""),
                        status=webhook_result.get("status", "inactive"),
                        reset_tokens=(webhook_result.get("action") == "payment_succeeded")
                    )
        except Exception as e:
            print(f"⚠️ Local subscription update failed: {e}")

        return JSONResponse(content={"success": True, "received": True, "event_id": event_id, "action": webhook_result.get("action")})
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook error: {str(e)}"
        )

@router.get("/plans")
async def get_subscription_plans():
    """Get available subscription plans"""
    try:
        return JSONResponse(
            content={
                "success": True,
                "plans": [
                    {
                        "id": "free",
                        "name": "Free",
                        "description": "Basic features with limited usage",
                        "price": 0,
                        "features": [
                            "10 AI conversations per month",
                            "Basic chat support",
                            "Email support"
                        ]
                    },
                    {
                        "id": "premium",
                        "name": "Premium",
                        "description": "Full access to all features",
                        "price": 2999,  # $29.99 in cents
                        "features": [
                            "Unlimited AI conversations",
                            "Priority chat support",
                            "Advanced AI models",
                            "API access",
                            "Priority email support"
                        ]
                    }
                ]
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        ) 