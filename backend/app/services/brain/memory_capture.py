"""First-pass user memory capture.

This deliberately creates candidate memories, not trusted facts. The goal is to
make the memory brain observable while the product is still in development.
"""

import json
import re
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_memory import UserMemory


async def capture_candidate_memories(
    db: AsyncSession,
    user_id: Optional[str],
    message: str,
    language: str = "es",
) -> List[Dict[str, str]]:
    if not user_id:
        return []

    candidates = _extract_candidates(message, language)
    created = []
    for candidate in candidates:
        if await _similar_memory_exists(db, user_id, candidate["summary"]):
            continue
        memory = UserMemory(
            user_id=user_id,
            type=candidate["type"],
            summary=candidate["summary"],
            curated_summary=candidate["curated_summary"],
            visibility="user_visible",
            sensitivity=candidate["sensitivity"],
            confidence=candidate["confidence"],
            status="candidate",
            source_message_ids=json.dumps([]),
            memory_metadata=json.dumps({"language": language, "capture": "heuristic_v1"}),
        )
        db.add(memory)
        await db.flush()
        created.append(
            {
                "id": memory.id,
                "type": memory.type,
                "summary": memory.summary,
                "curated_summary": memory.curated_summary or memory.summary,
                "status": memory.status,
                "confidence": memory.confidence,
            }
        )

    if created:
        await db.commit()
    return created


def _extract_candidates(message: str, language: str) -> List[Dict]:
    text = " ".join(message.strip().split())
    lower = text.lower()
    candidates = []

    partner_match = re.search(r"(?:mi pareja se llama|my partner is called|my partner's name is)\s+([A-ZÁÉÍÓÚÑ][\wáéíóúñ-]+)", text)
    if partner_match:
        name = partner_match.group(1)
        candidates.append(_candidate(
            "relationship_context",
            f"The user's partner is named {name}.",
            f"Your partner's name appears to be {name}.",
            0.72,
        ))

    if any(phrase in lower for phrase in ("me siento", "i feel", "siento que", "i get")):
        candidates.append(_candidate(
            "emotional_pattern",
            f"User described this emotional experience: {text}",
            f"You described this as emotionally important: {text}",
            0.42,
        ))

    if any(phrase in lower for phrase in ("quiero", "me gustaria", "i want", "i would like")):
        candidates.append(_candidate(
            "goal",
            f"User expressed a possible goal or desire: {text}",
            f"You said this may matter to you: {text}",
            0.40,
        ))

    if any(phrase in lower for phrase in ("cuando", "whenever", "when ")) and any(
        phrase in lower for phrase in ("ansiedad", "anxiety", "miedo", "fear", "triste", "sad")
    ):
        candidates.append(_candidate(
            "emotional_trigger",
            f"User described a possible trigger: {text}",
            f"This situation may be a trigger for you: {text}",
            0.46,
        ))

    return candidates[:2]


def _candidate(memory_type: str, summary: str, curated_summary: str, confidence: float) -> Dict:
    return {
        "type": memory_type,
        "summary": summary,
        "curated_summary": curated_summary,
        "confidence": confidence,
        "sensitivity": "normal",
    }


async def _similar_memory_exists(db: AsyncSession, user_id: str, summary: str) -> bool:
    result = await db.execute(
        select(UserMemory.summary)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.updated_at.desc())
        .limit(50)
    )
    normalized = _normalize(summary)
    for row in result.all():
        existing = _normalize(row[0])
        if existing == normalized or normalized[:80] in existing:
            return True
    return False


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()

