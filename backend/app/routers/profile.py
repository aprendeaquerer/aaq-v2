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

    return _to_response(profile, user)


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

    return _to_response(profile, user)


def _to_response(profile: UserProfile | None, user: User) -> UserProfileResponse:
    return UserProfileResponse(
        nombre=profile.nombre if profile else None,
        edad=profile.edad if profile else None,
        genero=profile.genero if profile else None,
        tiene_pareja=profile.tiene_pareja if profile else None,
        nombre_pareja=profile.nombre_pareja if profile else None,
        edad_pareja=profile.edad_pareja if profile else None,
        genero_pareja=profile.genero_pareja if profile else None,
        tiempo_pareja=profile.tiempo_pareja if profile else None,
        orientacion=profile.orientacion if profile else None,
        tipo_relacion=profile.tipo_relacion if profile else None,
        convive_con_pareja=profile.convive_con_pareja if profile else None,
        tiene_hijos=profile.tiene_hijos if profile else None,
        attachment_style=profile.attachment_style if profile else None,
        partner_attachment_style=profile.partner_attachment_style if profile else None,
        relationship_status=profile.relationship_status if profile else None,
        preferred_language=user.preferred_language,
        is_premium=user.is_premium,
        email_verified=user.email_verified,
    )
