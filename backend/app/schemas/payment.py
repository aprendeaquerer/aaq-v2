from typing import Optional

from pydantic import BaseModel


class CreateCheckoutRequest(BaseModel):
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class PremiumStatusResponse(BaseModel):
    is_premium: bool
    expires_at: Optional[str] = None
