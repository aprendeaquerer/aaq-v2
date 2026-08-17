import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.brain import semantic_index
from app.services.brain.knowledge_brain import retrieve_knowledge, route_domains
from app.services.brain.memory_brain import retrieve_user_memories
from app.services.brain.types import BrainContext, KnowledgeChunk

logger = logging.getLogger(__name__)


async def build_brain_context(
    db: AsyncSession,
    user_id: Optional[str],
    message: str,
    language: str = "es",
) -> BrainContext:
    domains = route_domains(message)
    knowledge_chunks = await retrieve_book_material(message, language)
    user_memories = await retrieve_user_memories(db, user_id, message)
    return BrainContext(
        knowledge_chunks=knowledge_chunks,
        user_memories=user_memories,
        domains=domains,
        intent=_detect_intent(message),
    )


async def retrieve_book_material(message: str, language: str = "es") -> List[KnowledgeChunk]:
    """Search the book by meaning, falling back to the old word search.

    Meaning-based search is the one that works: users do not write in the book's
    vocabulary. The keyword search stays as a fallback because it needs no API
    call, so a missing key or a bad minute at the embeddings endpoint degrades
    the answer instead of breaking the conversation.
    """
    try:
        chunks = await semantic_index.search(message, language=language)
    except Exception:
        logger.exception("build_brain_context: semantic search failed")
        chunks = None

    if chunks is not None:
        return chunks
    return retrieve_knowledge(message, language=language)


def _detect_intent(message: str) -> str:
    text = message.lower()
    if any(word in text for word in ("ansiedad", "anxiety", "panic", "panico", "miedo")):
        return "emotional_activation"
    if any(word in text for word in ("texto", "message", "decir", "say", "responder")):
        return "communication_help"
    if any(word in text for word in ("pelea", "conflict", "discusion", "argument")):
        return "conflict_repair"
    return "general_support"

