"""Tests for meaning-based search over the book.

The embeddings API is never called here: every test injects fake vectors. What
is being pinned is the behaviour around the API — ranking, the similarity floor,
the per-article cap, and above all that every failure path degrades to the old
keyword search instead of breaking the conversation.
"""

import pytest

from app.services.brain import semantic_index
from app.services.brain.types import KnowledgeChunk


def chunk(chunk_id: str, article_id: str = "libro", section: str = "Parte 5", language: str = "es") -> KnowledgeChunk:
    return KnowledgeChunk(
        id=chunk_id,
        article_id=article_id,
        title="Aprende a Querer — Método",
        section=section,
        content=f"contenido de {chunk_id}",
        domain="relationships",
        language=language,
        topics=["duelo_ruptura"],
    )


@pytest.fixture(autouse=True)
def clean_index():
    semantic_index.reset_for_tests()
    yield
    semantic_index.reset_for_tests()


def load(monkeypatch, chunks, vectors):
    """Put a ready-made index in place without touching the network."""
    monkeypatch.setattr(semantic_index, "_vectors", list(zip(chunks, vectors)))


# --- ranking -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_closest_chunk_in_meaning_comes_first(monkeypatch):
    ruptura, expectativas = chunk("ruptura"), chunk("expectativas", article_id="otro")
    # Unit vectors: the query points straight at "ruptura".
    load(monkeypatch, [ruptura, expectativas], [[1.0, 0.0], [0.0, 1.0]])
    monkeypatch.setattr(semantic_index, "_embed", _fake_embed([1.0, 0.0]))

    results = await semantic_index.search("lo he dejado con mi novio")

    assert [c.id for c in results] == ["ruptura"]


@pytest.mark.asyncio
async def test_chunks_below_the_similarity_floor_are_dropped(monkeypatch):
    """Without a floor, an off-topic message ("hola") still drags six chunks into
    the prompt and the model has to work out that all six are noise."""
    lejano = chunk("lejano")
    load(monkeypatch, [lejano], [[0.0, 1.0]])
    monkeypatch.setattr(semantic_index, "_embed", _fake_embed([1.0, 0.0]))

    assert await semantic_index.search("hola") == []


@pytest.mark.asyncio
async def test_one_article_cannot_take_every_slot(monkeypatch):
    chunks = [chunk(f"c{i}", article_id="mismo") for i in range(5)]
    load(monkeypatch, chunks, [[1.0, 0.0]] * 5)
    monkeypatch.setattr(semantic_index, "_embed", _fake_embed([1.0, 0.0]))

    results = await semantic_index.search("ruptura", max_per_article=2)

    assert len(results) == 2


@pytest.mark.asyncio
async def test_other_languages_are_filtered_out(monkeypatch):
    load(
        monkeypatch,
        [chunk("es_chunk", language="es"), chunk("en_chunk", article_id="b", language="en")],
        [[1.0, 0.0], [1.0, 0.0]],
    )
    monkeypatch.setattr(semantic_index, "_embed", _fake_embed([1.0, 0.0]))

    results = await semantic_index.search("ruptura", language="es")

    assert [c.id for c in results] == ["es_chunk"]


@pytest.mark.asyncio
async def test_the_similarity_is_reported_as_the_score(monkeypatch):
    """The debug panel shows this number, so it has to be the real similarity."""
    load(monkeypatch, [chunk("a")], [[1.0, 0.0]])
    monkeypatch.setattr(semantic_index, "_embed", _fake_embed([1.0, 0.0]))

    results = await semantic_index.search("ruptura")

    assert results[0].score == pytest.approx(1.0)


# --- degrading instead of breaking -------------------------------------------


@pytest.mark.asyncio
async def test_without_an_api_key_search_returns_none(monkeypatch):
    """None is the signal for "fall back to the keyword search", not an error."""
    monkeypatch.setattr(semantic_index.settings, "OPENAI_API_KEY", "")

    assert await semantic_index.search("lo he dejado con mi novio") is None


@pytest.mark.asyncio
async def test_an_embedding_failure_does_not_raise(monkeypatch):
    monkeypatch.setattr(semantic_index, "_embed", _fake_embed(None))

    assert await semantic_index.search("lo he dejado con mi novio") is None


@pytest.mark.asyncio
async def test_a_failed_build_is_not_retried_on_every_message(monkeypatch):
    """Retrying 7 embedding calls per message against a broken key would turn a
    degraded bot into a slow one."""
    calls = []

    async def failing(texts):
        calls.append(texts)
        return None

    monkeypatch.setattr(semantic_index, "_embed", failing)

    await semantic_index.search("uno")
    await semantic_index.search("dos")

    assert len(calls) == 1


@pytest.mark.asyncio
async def test_an_empty_corpus_does_not_build_an_index(monkeypatch):
    monkeypatch.setattr(
        "app.services.brain.knowledge_brain.list_knowledge_chunks", lambda *a, **k: []
    )

    assert await semantic_index.ensure_index() is False
    assert semantic_index.index_status()["mode"] == "keyword_fallback"


@pytest.mark.asyncio
async def test_an_empty_message_never_calls_the_api(monkeypatch):
    def explode(_texts):
        raise AssertionError("no debe llamarse a la API con un mensaje vacio")

    monkeypatch.setattr(semantic_index, "_embed", explode)

    assert await semantic_index.search("   ") is None


# --- status ------------------------------------------------------------------


def test_status_reports_the_three_states(monkeypatch):
    assert semantic_index.index_status()["mode"] == "building"

    load(monkeypatch, [chunk("a")], [[1.0, 0.0]])
    assert semantic_index.index_status() == {
        "ready": True,
        "indexed_chunks": 1,
        "mode": "semantic",
    }


# --- helpers -----------------------------------------------------------------


def _fake_embed(vector):
    async def _embed(texts):
        if vector is None:
            return None
        return [list(vector) for _ in texts]

    return _embed
