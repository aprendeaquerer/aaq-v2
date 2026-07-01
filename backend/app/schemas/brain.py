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


class SimulatedPersona(BaseModel):
    """Persona the AI role-plays as the user in a simulated conversation."""

    nombre: str
    edad: Optional[int] = None
    genero: Optional[str] = None
    orientacion: Optional[str] = None
    tipo_relacion: Optional[str] = None
    attachment_style: Optional[str] = None
    escenario: Optional[str] = None  # what is going on / the reason for reaching out
    contexto: Optional[str] = None   # free-text extra context


class SimulatedTurn(BaseModel):
    role: str  # "persona" (the simulated user) | "bot" (Eldric)
    content: str


class SimulateUserTurnRequest(BaseModel):
    persona: SimulatedPersona
    history: List[SimulatedTurn] = []
    language: str = "es"
    turn_number: int = 1
    max_turns: int = 8


class SimulateUserTurnResponse(BaseModel):
    message: str
    should_end: bool = False
