from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserProfile
from app.schemas.profile import UserProfileResponse, UserProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=UserProfileResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.user_id))
    profile = result.scalar_one_or_none()

    return UserProfileResponse(
        nombre=profile.nombre if profile else None,
        edad=profile.edad if profile else None,
        tiene_pareja=profile.tiene_pareja if profile else None,
        nombre_pareja=profile.nombre_pareja if profile else None,
        tiempo_pareja=profile.tiempo_pareja if profile else None,
        attachment_style=profile.attachment_style if profile else None,
        partner_attachment_style=profile.partner_attachment_style if profile else None,
        relationship_status=profile.relationship_status if profile else None,
        preferred_language=user.preferred_language,
        is_premium=user.is_premium,
        email_verified=user.email_verified,
    )


@router.put("", response_model=UserProfileResponse)
async def update_profile(
    updates: UserProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user.user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserProfile(user_id=user.user_id)
        db.add(profile)

    update_data = updates.model_dump(exclude_unset=True)
    if "preferred_language" in update_data:
        user.preferred_language = update_data.pop("preferred_language")

    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    await db.refresh(user)

    return UserProfileResponse(
        nombre=profile.nombre,
        edad=profile.edad,
        tiene_pareja=profile.tiene_pareja,
        nombre_pareja=profile.nombre_pareja,
        tiempo_pareja=profile.tiempo_pareja,
        attachment_style=profile.attachment_style,
        partner_attachment_style=profile.partner_attachment_style,
        relationship_status=profile.relationship_status,
        preferred_language=user.preferred_language,
        is_premium=user.is_premium,
        email_verified=user.email_verified,
    )
