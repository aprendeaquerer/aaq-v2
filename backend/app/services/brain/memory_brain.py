"""Database-backed user memory brain."""

from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_memory import UserMemory


async def retrieve_user_memories(
    db: AsyncSession,
    user_id: Optional[str],
    message: str,
    limit: int = 6,
) -> List[Dict[str, str]]:
    if not user_id:
        return []

    result = await db.execute(
        select(UserMemory)
        .where(
            UserMemory.user_id == user_id,
            UserMemory.status.in_(("candidate", "active")),
            UserMemory.visibility != "hidden",
            UserMemory.confidence >= 0.30,
        )
        .order_by(UserMemory.updated_at.desc())
        .limit(50)
    )
    memories = result.scalars().all()
    if not memories:
        return []

    terms = {term for term in message.lower().split() if len(term) > 2}
    ranked = []
    for memory in memories:
        text = f"{memory.type} {memory.summary} {memory.curated_summary or ''}".lower()
        score = sum(1 for term in terms if term in text)
        ranked.append((score, memory))

    ranked.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
    selected = [memory for _, memory in ranked[:limit]]
    return [
        {
            "id": memory.id,
            "type": memory.type,
            "summary": memory.summary,
            "curated_summary": memory.curated_summary or memory.summary,
            "visibility": memory.visibility,
            "sensitivity": memory.sensitivity,
            "status": memory.status,
            "confidence": memory.confidence,
        }
        for memory in selected
    ]
