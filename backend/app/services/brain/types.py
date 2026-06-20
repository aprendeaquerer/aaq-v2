from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class KnowledgeChunk:
    id: str
    article_id: str
    title: str
    section: str
    content: str
    domain: str
    language: str
    topics: List[str] = field(default_factory=list)
    source_notes: Optional[str] = None
    score: float = 0.0


@dataclass
class BrainContext:
    knowledge_chunks: List[KnowledgeChunk] = field(default_factory=list)
    user_memories: List[Dict[str, str]] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    intent: str = "general_support"

