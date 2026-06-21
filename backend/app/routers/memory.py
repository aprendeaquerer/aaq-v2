from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.user_memory import UserMemory
from app.schemas.memory import UserMemoryListResponse, UserMemoryResponse, UserMemoryUpdate

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=UserMemoryListResponse)
async def list_memories(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserMemory)
        .where(
            UserMemory.user_id == user.user_id,
            UserMemory.visibility == "user_visible",
            UserMemory.status.in_(("candidate", "active")),
        )
        .order_by(UserMemory.updated_at.desc())
    )
    memories = result.scalars().all()
    return UserMemoryListResponse(memories=[_to_response(memory) for memory in memories])


@router.patch("/{memory_id}", response_model=UserMemoryResponse)
async def update_memory(
    memory_id: str,
    updates: UserMemoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserMemory).where(UserMemory.id == memory_id, UserMemory.user_id == user.user_id)
    )
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in {"curated_summary", "visibility", "status"}:
            setattr(memory, field, value)

    await db.commit()
    await db.refresh(memory)
    return _to_response(memory)


def _to_response(memory: UserMemory) -> UserMemoryResponse:
    return UserMemoryResponse(
        id=memory.id,
        type=memory.type,
        summary=memory.summary,
        curated_summary=memory.curated_summary,
        visibility=memory.visibility,
        sensitivity=memory.sensitivity,
        confidence=memory.confidence,
        status=memory.status,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )
