import stripe
from app.core.config import settings
from typing import Optional, Dict, Any, List
from enum import Enum
import time

class SubscriptionPlan(str, Enum):
    FREE = "free"
    PREMIUM = "premium"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class StripeService:
    def __init__(self):
        if settings.stripe_secret:
            stripe.api_key = settings.stripe_secret
            self.webhook_secret = settings.stripe_webhook_secret
        else:
            # Don't raise exception during initialization, handle it in methods
            self.webhook_secret = None

    async def create_customer(self, email: str, name: str = None, user_id: str = None) -> Dict[str, Any]:
        """Create a new Stripe customer"""
        try:
            if not settings.stripe_secret:
                return {
                    "success": False,
                    "error": "Stripe not configured"
                }
            
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": user_id} if user_id else {}
            )
            return {
                "success": True,
                "customer": customer
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def create_checkout_session(
        self, 
        customer_id: str, 
        plan: SubscriptionPlan, 
        success_url: str, 
        cancel_url: str,
        client_reference_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Stripe checkout session for subscription"""
        try:
            # Get the price ID based on the plan
            price_id = self._get_price_id(plan)
            if not price_id:
                return {
                    "success": False,
                    "error": f"Price ID not configured for plan: {plan}"
                }

            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription' if plan != SubscriptionPlan.FREE else 'payment',
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
                billing_address_collection='auto',
                client_reference_id=client_reference_id
            )
            
            return {
                "success": True,
                "session": session,
                "checkout_url": session.url
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def get_customer_subscriptions(self, customer_id: str) -> Dict[str, Any]:
        """Get all subscriptions for a customer"""
        try:
            subscriptions = stripe.Subscription.list(customer=customer_id)
            return {
                "success": True,
                "subscriptions": subscriptions.data
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Cancel a subscription"""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                "success": True,
                "subscription": subscription
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def create_billing_portal_session(self, customer_id: str, return_url: str) -> Dict[str, Any]:
        """Create a billing portal session for customer to manage subscription"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            return {
                "success": True,
                "session": session,
                "portal_url": session.url
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _get_price_id(self, plan: SubscriptionPlan) -> Optional[str]:
        """Get Stripe price ID for a subscription plan"""
        if plan == SubscriptionPlan.FREE:
            return settings.stripe_price_free
        elif plan == SubscriptionPlan.PREMIUM:
            # Prefer STRIPE_PRICE_ID_PRO if set, else fallback to STRIPE_PRICE_PREMIUM
            return settings.stripe_price_id_pro or settings.stripe_price_premium
        return None

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Stripe webhook signature"""
        try:
            stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            return True
        except Exception:
            return False

    def _extract_plan_name_from_subscription(self, subscription: Dict[str, Any]) -> str:
        """Extract plan name from Stripe subscription object"""
        try:
            # Try to get plan from subscription items
            if 'items' in subscription and subscription['items']['data']:
                price_id = subscription['items']['data'][0]['price']['id']
                
                # Map price IDs to plan names (you can configure this)
                # For now, we'll try to extract from price metadata or nickname
                price = subscription['items']['data'][0]['price']
                
                if 'metadata' in price and 'plan_name' in price['metadata']:
                    return price['metadata']['plan_name']
                
                if 'nickname' in price and price['nickname']:
                    # If nickname exists and equals Pro, prefer that
                    if str(price['nickname']).lower() == 'pro':
                        return 'Pro'
                    return price['nickname']
                
                # Default mapping based on price ID
                if (settings.stripe_price_id_pro and price_id == settings.stripe_price_id_pro) or \
                   (settings.stripe_price_premium and price_id == settings.stripe_price_premium):
                    return "Pro"
                elif settings.stripe_price_free and price_id == settings.stripe_price_free:
                    return "Free"
            
            # Fallback to Free plan
            return "Free"
        except Exception:
            return "Free"
    
    async def handle_webhook_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            event_type = event['type']
            
            if event_type == 'customer.subscription.created':
                # Handle new subscription
                subscription = event['data']['object']
                customer_id = subscription['customer']
                subscription_id = subscription['id']
                status = subscription['status']
                plan_name = self._extract_plan_name_from_subscription(subscription)
                
                return {
                    "success": True,
                    "action": "subscription_created",
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "plan_name": plan_name,
                    "status": status,
                    "subscription": subscription
                }
                
            elif event_type == 'customer.subscription.updated':
                # Handle subscription update
                subscription = event['data']['object']
                customer_id = subscription['customer']
                subscription_id = subscription['id']
                status = subscription['status']
                plan_name = self._extract_plan_name_from_subscription(subscription)
                
                return {
                    "success": True,
                    "action": "subscription_updated",
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "plan_name": plan_name,
                    "status": status,
                    "subscription": subscription
                }
                
            elif event_type == 'customer.subscription.deleted':
                # Handle subscription cancellation
                subscription = event['data']['object']
                customer_id = subscription['customer']
                subscription_id = subscription['id']
                plan_name = self._extract_plan_name_from_subscription(subscription)
                
                return {
                    "success": True,
                    "action": "subscription_cancelled",
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "plan_name": plan_name,
                    "status": "canceled",
                    "subscription": subscription
                }
                
            elif event_type == 'invoice.payment_succeeded':
                # Handle successful payment (subscription renewal)
                invoice = event['data']['object']
                customer_id = invoice['customer']
                subscription_id = invoice.get('subscription')
                # Try to determine plan name from invoice lines or subscription
                plan_name = None
                subscription_start = None
                try:
                    # Prefer invoice line price mapping
                    lines = invoice.get('lines', {}).get('data', [])
                    if lines:
                        price = lines[0].get('price') or {}
                        price_id = price.get('id')
                        if price.get('nickname') and str(price.get('nickname')).lower() == 'pro':
                            plan_name = 'Pro'
                        elif price_id and (
                            (settings.stripe_price_id_pro and price_id == settings.stripe_price_id_pro) or
                            (settings.stripe_price_premium and price_id == settings.stripe_price_premium)
                        ):
                            plan_name = 'Pro'
                        elif settings.stripe_price_free and price_id == settings.stripe_price_free:
                            plan_name = 'Free'
                    # If still unknown, fetch subscription and reuse extraction
                    if not plan_name and subscription_id:
                        sub = stripe.Subscription.retrieve(subscription_id)
                        plan_name = self._extract_plan_name_from_subscription(sub)
                        # Subscription start based on current_period_start
                        subscription_start = sub.get('current_period_start')
                except Exception:
                    plan_name = None
                    subscription_start = None
                # Fallback to invoice period_start
                if not subscription_start:
                    subscription_start = invoice.get('period_start')
                
                return {
                    "success": True,
                    "action": "payment_succeeded",
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "status": "active",
                    "plan_name": plan_name or 'Pro',
                    "subscription_start": subscription_start,
                    "invoice": invoice
                }
                
            elif event_type == 'invoice.payment_failed':
                # Handle failed payment
                invoice = event['data']['object']
                customer_id = invoice['customer']
                subscription_id = invoice.get('subscription')
                
                return {
                    "success": True,
                    "action": "payment_failed",
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "status": "unpaid",
                    "invoice": invoice
                }
            
            elif event_type == 'checkout.session.completed':
                # Handle checkout completion – often the first event
                session = event['data']['object']
                customer_id = session.get('customer')
                subscription_id = session.get('subscription')
                # Prefer client_reference_id for user mapping if present
                user_id = session.get('client_reference_id')
                plan_name = None
                subscription_start = None
                try:
                    if subscription_id:
                        sub = stripe.Subscription.retrieve(subscription_id)
                        plan_name = self._extract_plan_name_from_subscription(sub)
                        subscription_start = sub.get('current_period_start')
                except Exception:
                    plan_name = None
                    subscription_start = None
                return {
                    "success": True,
                    "action": "checkout_completed",
                    "customer_id": customer_id,
                    "subscription_id": subscription_id,
                    "user_id": user_id,
                    "plan_name": plan_name or 'Pro',
                    "subscription_start": subscription_start
                }
            
            return {
                "success": True,
                "action": "unhandled_event",
                "event_type": event_type
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_id_from_customer(self, customer_id: str) -> Optional[str]:
        """Get Supabase user ID from Stripe customer ID"""
        try:
            customer = stripe.Customer.retrieve(customer_id)
            if customer and 'metadata' in customer and 'user_id' in customer.metadata:
                return customer.metadata['user_id']
            return None
        except Exception:
            return None

# Create a singleton instance
stripe_service = StripeService() 