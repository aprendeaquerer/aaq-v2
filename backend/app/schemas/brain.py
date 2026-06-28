from typing import Dict, List, Optional

from pydantic import BaseModel


class KnowledgeChunkResponse(BaseModel):
    id: str
    article_id: str
    title: str
    section: str
    content: str
    preview: str
    domain: str
    language: str
    polarity_lane: str = ""
    topics: List[str]
    source_notes: Optional[str] = None


class KnowledgeBrainResponse(BaseModel):
    chunks: List[KnowledgeChunkResponse]
    domains: Dict[str, int]
    articles: Dict[str, int]
