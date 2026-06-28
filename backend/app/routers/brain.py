from fastapi import APIRouter, Query

from app.schemas.brain import KnowledgeBrainResponse, KnowledgeChunkResponse
from app.services.brain.knowledge_brain import list_knowledge_chunks
from app.services.brain.types import KnowledgeChunk

router = APIRouter(prefix="/brain", tags=["brain"])


@router.get("/knowledge", response_model=KnowledgeBrainResponse)
async def get_knowledge_brain(
    language: str = Query(default="", max_length=8),
    domain: str = Query(default="", max_length=64),
):
    chunks = list_knowledge_chunks(language=language, domain=domain)
    domains: dict[str, int] = {}
    articles: dict[str, int] = {}

    for chunk in chunks:
        domains[chunk.domain] = domains.get(chunk.domain, 0) + 1
        articles[chunk.article_id] = articles.get(chunk.article_id, 0) + 1

    return KnowledgeBrainResponse(
        chunks=[_to_response(chunk) for chunk in chunks],
        domains=domains,
        articles=articles,
    )


def _to_response(chunk: KnowledgeChunk) -> KnowledgeChunkResponse:
    return KnowledgeChunkResponse(
        id=chunk.id,
        article_id=chunk.article_id,
        title=chunk.title,
        section=chunk.section,
        content=chunk.content,
        preview=_preview(chunk.content),
        domain=chunk.domain,
        language=chunk.language,
        polarity_lane=chunk.polarity_lane,
        topics=chunk.topics,
        source_notes=chunk.source_notes,
    )


def _preview(value: str, limit: int = 220) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."
