from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.payment import CheckoutResponse, CreateCheckoutRequest, PremiumStatusResponse

router = APIRouter(prefix="/payment", tags=["payment"])


@router.post("/create-checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CreateCheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.payment_service import create_checkout_session
    url = await create_checkout_session(user, request.success_url, request.cancel_url)
    return CheckoutResponse(checkout_url=url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    from app.services.payment_service import handle_webhook
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    await handle_webhook(db, payload, sig_header)
    return {"status": "ok"}


@router.get("/status", response_model=PremiumStatusResponse)
async def premium_status(user: User = Depends(get_current_user)):
    return PremiumStatusResponse(
        is_premium=user.is_premium,
        expires_at=user.premium_expires_at.isoformat() if user.premium_expires_at else None,
    )
