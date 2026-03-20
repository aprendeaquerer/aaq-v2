"""Stripe payment service for premium subscriptions."""

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User

stripe.api_key = settings.STRIPE_SECRET_KEY

PREMIUM_PRICE_CENTS = 999  # $9.99


async def create_checkout_session(user: User, success_url: str, cancel_url: str) -> str:
    """Create a Stripe Checkout session for one-time premium payment."""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": "Aprende a Querer Premium"},
                "unit_amount": PREMIUM_PRICE_CENTS,
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user.id,
        customer_email=user.email,
    )
    return session.url


async def handle_webhook(db: AsyncSession, payload: bytes, sig_header: str) -> None:
    """Handle Stripe webhook events."""
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise ValueError("Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_premium = True
                await db.commit()
