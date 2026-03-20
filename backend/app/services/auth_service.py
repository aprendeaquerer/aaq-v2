import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile
from app.utils.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token


async def register_user(db: AsyncSession, email: str, password: str, preferred_language: str = "es") -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        preferred_language=preferred_language,
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(user_id=user.id)
    db.add(profile)
    await db.commit()
    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise ValueError("Invalid email or password")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    return user, access_token, refresh_token


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise ValueError("Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    new_access = create_access_token(user.id)
    new_refresh = create_refresh_token(user.id)
    return new_access, new_refresh


def generate_verification_code() -> str:
    return "".join(random.choices(string.digits, k=6))


async def send_verification_code(db: AsyncSession, email: str) -> str:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    code = generate_verification_code()
    user.verification_code = code
    user.verification_code_expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    await db.commit()
    return code


async def verify_email(db: AsyncSession, email: str, code: str) -> bool:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    if user.verification_code != code:
        raise ValueError("Invalid verification code")

    if user.verification_code_expires and user.verification_code_expires < datetime.now(timezone.utc):
        raise ValueError("Verification code expired")

    user.email_verified = True
    user.verification_code = None
    user.verification_code_expires = None
    await db.commit()
    return True
