"""Semantic search over the book, by meaning instead of by words.

Why this exists (measured 2026-08-17): the keyword search this replaces scored a
chunk by how many of the user's words appeared in it. Real users do not use the
book's vocabulary. "lo he dejado con mi novio" reduces to two useful words,
"dejado" and "novio". The book has 53 chunks on breakups — exactly the material
that answer needs — and only 2 of them contain "dejado", none contain "novio".
So the right chapter was invisible, and what surfaced instead were chapters on
expectations and on digital relationships that happened to use those words in
passing.

Embeddings fix that: each chunk becomes a vector that encodes what it is about,
not which words it uses, so a message lands on the breakup chapters even when it
shares no vocabulary with them.

Design notes:

- 512 dimensions, not the default 1536. text-embedding-3-small is trained so the
  leading dimensions carry most of the signal, 512 is plenty to separate 661
  chunks, and it keeps the dot product fast enough in plain Python that this
  module needs no numpy dependency.
- Vectors are normalised at index time, so cosine similarity is a plain dot
  product at query time.
- The index is built once per process, guarded by a lock, and kicked off in the
  background at startup so the first user does not pay for it.
- Every failure path returns None rather than raising: no API key, a network
  error, an empty corpus. The caller falls back to the keyword search, which
  stays in the codebase for exactly this reason. A degraded answer beats a 500.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Sequence, Tuple

from app.config import settings
from app.services.brain.types import KnowledgeChunk

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 512

# The embeddings endpoint takes arrays; 661 chunks is 7 calls at this size.
_BATCH_SIZE = 100

# Chunks below this similarity are not about the message at all. Without a floor
# every message retrieves six chunks, and on an off-topic turn ("hola", "gracias")
# those six become noise the model has to ignore.
MIN_SIMILARITY = 0.25

_vectors: Optional[List[Tuple[KnowledgeChunk, Sequence[float]]]] = None
_build_lock = asyncio.Lock()
_build_failed = False


def _embedding_text(chunk: KnowledgeChunk) -> str:
    """What gets embedded: the chunk plus its place in the book.

    The section path carries real signal ("Parte 5 — Ruptura: soltar y
    reconstruir"), and topics carry the curation that was done by hand.
    """
    parts = [chunk.section, chunk.content]
    if chunk.topics:
        parts.append(" ".join(chunk.topics))
    return "\n".join(part for part in parts if part)


def _normalise(vector: Sequence[float]) -> List[float]:
    magnitude = sum(value * value for value in vector) ** 0.5
    if magnitude == 0:
        return list(vector)
    return [value / magnitude for value in vector]


async def _embed(texts: List[str]) -> Optional[List[List[float]]]:
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        out: List[List[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start:start + _BATCH_SIZE]
            response = await client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                dimensions=EMBEDDING_DIMENSIONS,
            )
            out.extend(item.embedding for item in response.data)
        return out
    except Exception:
        logger.exception("semantic_index: embedding call failed")
        return None


async def ensure_index() -> bool:
    """Build the index once. Returns True when it is usable."""
    global _vectors, _build_failed

    if _vectors is not None:
        return True
    if _build_failed:
        return False

    async with _build_lock:
        # Another request may have built it while this one waited.
        if _vectors is not None:
            return True
        if _build_failed:
            return False

        from app.services.brain.knowledge_brain import list_knowledge_chunks

        chunks = list_knowledge_chunks()
        if not chunks:
            logger.warning("semantic_index: the corpus is empty, nothing to index")
            _build_failed = True
            return False

        embeddings = await _embed([_embedding_text(chunk) for chunk in chunks])
        if embeddings is None or len(embeddings) != len(chunks):
            logger.warning(
                "semantic_index: build failed, falling back to keyword search "
                "(chunks=%d, embeddings=%s)",
                len(chunks),
                "none" if embeddings is None else len(embeddings),
            )
            _build_failed = True
            return False

        _vectors = [
            (chunk, _normalise(embedding))
            for chunk, embedding in zip(chunks, embeddings)
        ]
        logger.info("semantic_index: indexed %d chunks", len(_vectors))
        return True


async def search(
    message: str,
    language: str = "es",
    limit: int = 6,
    max_per_article: int = 2,
) -> Optional[List[KnowledgeChunk]]:
    """Chunks closest in meaning to the message, or None if unavailable."""
    if not message.strip():
        return None
    if not await ensure_index() or not _vectors:
        return None

    query = await _embed([message])
    if not query:
        return None
    query_vector = _normalise(query[0])

    scored: List[Tuple[float, KnowledgeChunk]] = []
    for chunk, vector in _vectors:
        if chunk.language not in (language, "multi", ""):
            continue
        similarity = sum(a * b for a, b in zip(query_vector, vector))
        if similarity >= MIN_SIMILARITY:
            scored.append((similarity, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)

    results: List[KnowledgeChunk] = []
    per_article: dict = {}
    for similarity, chunk in scored:
        seen = per_article.get(chunk.article_id, 0)
        if seen >= max_per_article:
            continue
        results.append(
            KnowledgeChunk(
                id=chunk.id,
                article_id=chunk.article_id,
                title=chunk.title,
                section=chunk.section,
                content=chunk.content,
                domain=chunk.domain,
                language=chunk.language,
                polarity_lane=chunk.polarity_lane,
                topics=chunk.topics,
                source_notes=chunk.source_notes,
                score=round(similarity, 4),
            )
        )
        per_article[chunk.article_id] = seen + 1
        if len(results) >= limit:
            break
    return results


def index_status() -> dict:
    """For /status: whether the book is searchable by meaning right now."""
    if _vectors is not None:
        return {"ready": True, "indexed_chunks": len(_vectors), "mode": "semantic"}
    if _build_failed:
        return {"ready": False, "indexed_chunks": 0, "mode": "keyword_fallback"}
    return {"ready": False, "indexed_chunks": 0, "mode": "building"}


def reset_for_tests() -> None:
    global _vectors, _build_failed
    _vectors = None
    _build_failed = False
