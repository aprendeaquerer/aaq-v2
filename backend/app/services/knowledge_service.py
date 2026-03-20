"""Knowledge injection service - extracts keywords and retrieves relevant content from DB."""

import json
from typing import Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# In-memory cache of used quotes per user (reset on restart)
_used_quotes: Dict[str, Set[int]] = {}

# Multi-language keyword mappings to English categories for DB lookup
ATTACHMENT_KEYWORDS = {
    "es": {
        "anxious": ["ansioso", "ansiedad", "preocupado", "miedo", "abandono", "rechazo", "inseguro", "necesito", "confirmacion"],
        "avoidant": ["evitativo", "evito", "distancia", "independiente", "solo", "espacio", "alejado", "frio", "distante"],
        "secure": ["seguro", "confianza", "equilibrio", "comodo", "tranquilo", "estable", "sano"],
        "disorganized": ["evitativo temeroso", "confundido", "contradictorio", "caos", "inconsistente"],
        "relationship": ["relacion", "relaciones", "pareja", "amor", "vinculo", "conexion", "intimidad", "cercania"],
        "communication": ["comunicacion", "hablar", "expresar", "decir", "conversar"],
        "conflict": ["conflicto", "pelea", "discusion", "problema", "disputa"],
        "trust": ["confianza", "confiar", "seguro", "seguridad"],
        "emotions": ["emocion", "sentir", "sentimiento", "triste", "feliz", "enojado", "frustrado"],
    },
    "en": {
        "anxious": ["anxious", "anxiety", "worried", "fear", "abandonment", "rejection", "insecure", "need", "confirmation"],
        "avoidant": ["avoidant", "avoid", "distance", "independent", "alone", "space", "distant", "cold", "detached"],
        "secure": ["secure", "trust", "balance", "comfortable", "calm", "stable", "healthy"],
        "disorganized": ["fearful avoidant", "confused", "contradictory", "chaos", "inconsistent"],
        "relationship": ["relationship", "partner", "love", "bond", "connection", "intimacy", "closeness"],
        "communication": ["communication", "talk", "express", "say", "converse"],
        "conflict": ["conflict", "fight", "argument", "problem", "dispute"],
        "trust": ["trust", "trusting", "secure", "security"],
        "emotions": ["emotion", "feel", "feeling", "sad", "happy", "angry", "frustrated"],
    },
    "ru": {
        "anxious": ["тревожный", "тревога", "беспокойный", "страх", "покинутость", "отвержение"],
        "avoidant": ["избегающий", "избегать", "дистанция", "независимый", "один", "пространство"],
        "secure": ["надежный", "доверие", "баланс", "комфортный", "спокойный", "стабильный"],
        "disorganized": ["дезорганизованный", "запутанный", "противоречивый", "хаос"],
        "relationship": ["отношения", "партнер", "любовь", "связь", "близость"],
        "communication": ["общение", "говорить", "выражать"],
        "conflict": ["конфликт", "ссора", "спор", "проблема"],
        "trust": ["доверие", "доверять", "безопасность"],
        "emotions": ["эмоция", "чувствовать", "чувство", "грустный", "счастливый"],
    },
}


def extract_keywords(message: str, language: str = "es") -> List[str]:
    """Extract relevant category keywords from user message for knowledge lookup."""
    message_lower = message.lower()
    lang_keywords = ATTACHMENT_KEYWORDS.get(language, ATTACHMENT_KEYWORDS["es"])

    found = []
    for category, words in lang_keywords.items():
        for word in words:
            if word in message_lower:
                found.append(category)
                break

    # Deduplicate preserving order
    seen = set()
    unique = []
    for cat in found:
        if cat not in seen:
            seen.add(cat)
            unique.append(cat)
    return unique[:5]


async def get_relevant_knowledge(
    db: AsyncSession,
    keywords: List[str],
    language: str = "es",
    user_id: Optional[str] = None,
) -> Optional[str]:
    """Query the knowledge table for relevant content based on keywords.

    Returns one formatted knowledge piece, avoiding previously used quotes for this user.
    """
    if not keywords:
        return None

    # Build tag conditions
    conditions = []
    params = {"lang": language}
    for i, kw in enumerate(keywords):
        conditions.append(f"tags ILIKE :tag_{i}")
        params[f"tag_{i}"] = f"%{kw}%"

    where_tags = " OR ".join(conditions)

    # Exclude previously used quotes
    used_ids = _used_quotes.get(user_id, set()) if user_id else set()
    exclusion = ""
    if used_ids:
        id_list = ", ".join(str(uid) for uid in used_ids)
        exclusion = f" AND id NOT IN ({id_list})"

    query = text(
        f"SELECT id, content, book, chapter FROM knowledge "
        f"WHERE language = :lang AND ({where_tags}){exclusion} "
        f"ORDER BY RANDOM() LIMIT 1"
    )

    result = await db.execute(query, params)
    row = result.first()

    # If no unused quotes, reset and try again
    if not row and used_ids:
        _used_quotes[user_id] = set()
        query_retry = text(
            f"SELECT id, content, book, chapter FROM knowledge "
            f"WHERE language = :lang AND ({where_tags}) "
            f"ORDER BY RANDOM() LIMIT 1"
        )
        result = await db.execute(query_retry, params)
        row = result.first()

    if not row:
        return None

    # Track used quote
    if user_id:
        _used_quotes.setdefault(user_id, set()).add(row.id)

    book = row.book or "Teoria del apego"
    chapter = row.chapter or ""

    # Format for injection into the system prompt
    source = f"{book}, {chapter}" if chapter else book
    return (
        f"\n\nCONOCIMIENTO PARA USAR EN TU RESPUESTA:\n"
        f"{row.content}\n"
        f"Fuente: {source}\n"
        f"Usa este conocimiento de forma natural en tu respuesta, como si fuera algo que sabes."
    )


def inject_knowledge(base_prompt: str, knowledge: Optional[str]) -> str:
    """Append knowledge to the system prompt if available."""
    if not knowledge:
        return base_prompt
    return base_prompt + knowledge
