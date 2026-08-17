"""Tests for the prompt the model actually receives.

First rule after the 2026-08-12 reset to zero: "the book first, then judgement".
Before it, the chunks were dumped under a header and nothing else — no
instruction at all — so the model read them as background noise and answered
from its own knowledge. These tests pin that the instruction is there when there
is material, and absent when there is not.
"""

from app.services.brain.prompt_composer import compose_brain_prompt
from app.services.brain.types import BrainContext, KnowledgeChunk


def chunk(content: str = "El duelo tiene fases reconocibles.") -> KnowledgeChunk:
    return KnowledgeChunk(
        id="c1",
        article_id="libro",
        title="Aprende a Querer — Método",
        section="Parte 5 — Ruptura: soltar y reconstruir",
        content=content,
        domain="relationships",
        language="es",
        topics=["duelo_ruptura"],
    )


def test_the_book_material_reaches_the_prompt():
    prompt = compose_brain_prompt("[BASE]", BrainContext(knowledge_chunks=[chunk()]))

    assert "MATERIAL DEL LIBRO PARA ESTE TURNO" in prompt
    assert "El duelo tiene fases reconocibles." in prompt
    assert "Parte 5 — Ruptura: soltar y reconstruir" in prompt


def test_the_instruction_to_use_the_book_travels_with_the_material():
    prompt = compose_brain_prompt("[BASE]", BrainContext(knowledge_chunks=[chunk()]))

    assert "COMO USAR EL MATERIAL DEL LIBRO" in prompt
    assert "El libro es tu fuente" in prompt


def test_the_instruction_allows_own_judgement_when_nothing_fits():
    """"The book first, then judgement" — not "only the book". Forcing an
    irrelevant chunk is worse than not using the book on that turn."""
    prompt = compose_brain_prompt("[BASE]", BrainContext(knowledge_chunks=[chunk()]))

    assert "responde con criterio propio" in prompt
    assert "Nunca fuerces un fragmento que no viene a cuento" in prompt


def test_eldric_must_not_quote_or_name_the_book():
    prompt = compose_brain_prompt("[BASE]", BrainContext(knowledge_chunks=[chunk()]))

    assert "no lo menciones como fuente" in prompt


def test_without_material_there_is_no_instruction_about_it():
    """An instruction about material that is not there only invites the model to
    talk about a book the user cannot see."""
    prompt = compose_brain_prompt("[BASE]", BrainContext(knowledge_chunks=[]))

    assert prompt == "[BASE]"


def test_memories_reach_the_prompt():
    context = BrainContext(
        user_memories=[
            {"type": "fact", "summary": "le gusta el senderismo", "status": "active", "confidence": 0.9}
        ]
    )

    prompt = compose_brain_prompt("[BASE]", context)

    assert "le gusta el senderismo" in prompt


def test_the_base_personality_always_comes_first():
    prompt = compose_brain_prompt("[BASE]", BrainContext(knowledge_chunks=[chunk()]))

    assert prompt.startswith("[BASE]")
