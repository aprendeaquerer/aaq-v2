from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.brain.knowledge_brain import retrieve_knowledge, route_domains
from app.services.brain.memory_brain import retrieve_user_memories
from app.services.brain.types import BrainContext


async def build_brain_context(
    db: AsyncSession,
    user_id: Optional[str],
    message: str,
    language: str = "es",
) -> BrainContext:
    domains = route_domains(message)
    knowledge_chunks = retrieve_knowledge(message, language=language)
    user_memories = await retrieve_user_memories(db, user_id, message)
    return BrainContext(
        knowledge_chunks=knowledge_chunks,
        user_memories=user_memories,
        domains=domains,
        intent=_detect_intent(message),
    )


def _detect_intent(message: str) -> str:
    text = message.lower()
    if any(word in text for word in ("ansiedad", "anxiety", "panic", "panico", "miedo")):
        return "emotional_activation"
    if any(word in text for word in ("texto", "message", "decir", "say", "responder")):
        return "communication_help"
    if any(word in text for word in ("pelea", "conflict", "discusion", "argument")):
        return "conflict_repair"
    return "general_support"

