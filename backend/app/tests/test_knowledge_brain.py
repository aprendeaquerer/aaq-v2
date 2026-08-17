"""Guards against the knowledge brain silently shipping empty.

The corpus used to live at the repo root (output/...), outside the backend/
Docker build context, so the deployed container never contained it and Eldric
answered with zero retrieved chunks. These tests fail loudly if that regresses.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _load_knowledge_brain():
    """Import knowledge_brain without pulling in sqlalchemy-backed siblings."""
    if "app" not in sys.modules:
        pkg = types.ModuleType("app")
        pkg.__path__ = [str(BACKEND_ROOT / "app")]
        sys.modules["app"] = pkg
    for name, rel in (("app.services", "app/services"), ("app.services.brain", "app/services/brain")):
        if name not in sys.modules:
            mod = types.ModuleType(name)
            mod.__path__ = [str(BACKEND_ROOT / rel)]
            sys.modules[name] = mod
    if "app.services.brain.types" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "app.services.brain.types", BACKEND_ROOT / "app/services/brain/types.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["app.services.brain.types"] = module
        spec.loader.exec_module(module)
    spec = importlib.util.spec_from_file_location(
        "knowledge_brain_under_test", BACKEND_ROOT / "app/services/brain/knowledge_brain.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kb = _load_knowledge_brain()


def test_corpus_file_is_inside_backend():
    """It must ship in the Docker image, whose build context is backend/."""
    packaged = BACKEND_ROOT / "app" / kb.PACKAGED_KNOWLEDGE_JSONL
    assert packaged.exists(), f"corpus missing at {packaged}"
    assert BACKEND_ROOT in packaged.parents


def test_selected_path_does_not_escape_backend():
    selected = kb.canonical_chunks_path()
    assert selected.exists()
    assert BACKEND_ROOT in selected.parents


def test_knowledge_brain_is_not_empty():
    chunks = kb.list_knowledge_chunks()
    assert len(chunks) > 100, f"expected a populated corpus, got {len(chunks)} chunks"


@pytest.mark.parametrize("domain", ["attachment", "relationships", "polarity", "self_improvement"])
def test_every_main_domain_has_chunks(domain):
    assert kb.list_knowledge_chunks(domain=domain), f"no chunks for domain {domain}"


def test_chunks_have_content():
    for chunk in kb.list_knowledge_chunks()[:50]:
        assert chunk.id
        assert chunk.content.strip()


# --- Retrieval targeting (gap found by the QA run of 2026-08-03) ---

CURRENT_PARTNER_QUERIES = [
    "lleva tres semanas contestandome tarde y ya paso de escribirle",
    "discutimos por las tareas de casa y siempre acabamos igual",
    "siento que ya no me cuenta las cosas como antes",
]

BREAKUP_QUERIES = [
    "lo dejamos hace un mes y no consigo superar a mi ex",
    "rompimos en enero y sigo mirando su instagram",
]


def _topics(query):
    return [set(chunk.topics) for chunk in kb.retrieve_knowledge(query, "es", 4)]


@pytest.mark.parametrize("query", CURRENT_PARTNER_QUERIES)
def test_current_partner_queries_do_not_retrieve_breakup_material(query):
    """The QA run found 32 conversations where someone asking about their current
    partner was answered with material about getting over an ex."""
    for topics in _topics(query):
        assert "duelo_ruptura" not in topics, f"{query} -> {topics}"


@pytest.mark.parametrize("query", BREAKUP_QUERIES)
def test_actual_breakups_still_retrieve_breakup_material(query):
    topics = _topics(query)
    assert topics, query
    assert any("duelo_ruptura" in t for t in topics), f"{query} -> {topics}"


# --- the operating manual is not material for the user (2026-08-17) -----------


def test_the_operating_manual_never_reaches_retrieval():
    """Part 12 is written for whoever does the coaching: a question bank, work
    itineraries, example dialogues, a chapter on how NOT to answer. Retrieval used
    to hand it to the model as material to answer from, so Eldric could read the
    coach's own question bank out loud to the user."""
    from app.services.brain.knowledge_brain import retrievable_chunks

    for chunk in retrievable_chunks():
        assert "Parte 12" not in chunk.section, chunk.section
        assert "Manual operativo" not in chunk.section, chunk.section


def test_the_manual_is_excluded_from_retrieval_not_from_the_corpus():
    """The material is good, it is just addressed to the wrong reader — so it
    stays loaded and visible, it only stops being answer material."""
    from app.services.brain.knowledge_brain import list_knowledge_chunks, retrievable_chunks

    todo = list_knowledge_chunks()
    recuperable = retrievable_chunks()

    assert len(todo) > len(recuperable)
    assert any("Manual operativo" in c.section for c in todo)


def test_the_rest_of_the_book_survives_the_exclusion():
    """Guard against a marker that is too broad quietly emptying the corpus."""
    from app.services.brain.knowledge_brain import retrievable_chunks

    secciones = " ".join(c.section for c in retrievable_chunks())
    for parte in ("Parte 5", "Parte 9", "Parte 10", "Parte 11"):
        assert parte in secciones, parte
