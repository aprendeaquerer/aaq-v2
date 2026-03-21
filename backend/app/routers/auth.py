from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    SendVerificationRequest,
    VerifyEmailRequest,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register_user(db, request.email, request.password, request.preferred_language)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return MessageResponse(message=f"User {user.email} registered successfully")


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    try:
        user, access_token, refresh_token = await auth_service.login_user(db, request.email, request.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        email=user.email,
        is_premium=user.is_premium,
        preferred_language=user.preferred_language,
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        access_token, refresh_token = await auth_service.refresh_tokens(db, request.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    payload = auth_service.decode_token(access_token)
    from sqlalchemy import select
    from app.models.user import User
    result = await db.execute(select(User).where(User.user_id == payload["sub"]))
    user = result.scalar_one()

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.user_id,
        email=user.email,
        is_premium=user.is_premium,
        preferred_language=user.preferred_language,
    )


@router.post("/send-verification", response_model=MessageResponse)
async def send_verification(request: SendVerificationRequest, db: AsyncSession = Depends(get_db)):
    try:
        code = await auth_service.send_verification_code(db, request.email)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    # TODO: Actually send the email via email_service
    return MessageResponse(message="Verification code sent")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(request: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    try:
        await auth_service.verify_email(db, request.email, request.code)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return MessageResponse(message="Email verified successfully")
