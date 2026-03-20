"""Daily affirmation service - sequential rotation per attachment style."""

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.affirmation import Affirmation
from app.models.user import UserProfile


async def get_daily_affirmation(
    db: AsyncSession, user_id: str
) -> Optional[str]:
    """Get the next sequential affirmation for the user's attachment style.

    Returns None if: no profile, no attachment style, or already received today.
    """
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile or not profile.attachment_style:
        return None

    # Check if already received today
    now = datetime.now(timezone.utc)
    if profile.last_affirmation_at and profile.last_affirmation_at.date() == now.date():
        return None

    style = profile.attachment_style

    # Get current index for this style
    try:
        indices = json.loads(profile.affirmation_index or "{}")
    except (json.JSONDecodeError, TypeError):
        indices = {}

    current_index = indices.get(style, 0)

    # Fetch the affirmation at this index
    aff_result = await db.execute(
        select(Affirmation)
        .where(Affirmation.attachment_style == style)
        .order_by(Affirmation.order_index)
        .offset(current_index)
        .limit(1)
    )
    affirmation = aff_result.scalar_one_or_none()

    if not affirmation:
        # Wrap around to beginning
        current_index = 0
        aff_result = await db.execute(
            select(Affirmation)
            .where(Affirmation.attachment_style == style)
            .order_by(Affirmation.order_index)
            .limit(1)
        )
        affirmation = aff_result.scalar_one_or_none()

    if not affirmation:
        return None

    # Update tracking
    indices[style] = current_index + 1
    profile.affirmation_index = json.dumps(indices)
    profile.last_affirmation_at = now
    await db.commit()

    return affirmation.text
