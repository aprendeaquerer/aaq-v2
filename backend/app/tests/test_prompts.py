"""Tests for the base personality.

Every rule here comes from a failure seen in a real conversation, and each test
names the failure it prevents. After the 2026-08-12 reset to zero this file
starts almost empty on purpose; it grows one rule at a time.
"""

import pytest

from app.services.ai.prompts import ELDRIC_PROMPTS, get_eldric_prompt


def test_eldric_is_introduced_and_answers_in_spanish():
    prompt = get_eldric_prompt("es")

    assert "Eldric" in prompt
    assert "Aprende a Querer" in prompt
    assert "español" in prompt


def test_an_unknown_language_falls_back_to_spanish():
    assert get_eldric_prompt("fr") == ELDRIC_PROMPTS["es"]
    assert get_eldric_prompt("") == ELDRIC_PROMPTS["es"]


# --- rule 2: do not assume her state or her goal (2026-08-17) -----------------
#
# Observed: "lo he dejado con mi novio" -> "Lo siento, debe estar siendo
# doloroso", and one turn later "es normal que el contacto cero duela" plus
# advice framed around not using no-contact "como una estrategia para que
# vuelva". She had said none of it. She was the one who left.


def test_assuming_she_is_suffering_is_banned():
    prompt = get_eldric_prompt("es")

    assert "NO DES POR HECHO COMO ESTA NI QUE QUIERE" in prompt
    assert "debe estar siendo doloroso" in prompt
    assert "es normal que" in prompt


def test_a_fact_does_not_carry_its_emotion():
    """Leaving someone can be relief, doubt, sadness, or all three."""
    prompt = get_eldric_prompt("es")

    assert "alivio, duda, tristeza" in prompt
    assert "Un hecho no trae su emocion incluida" in prompt


def test_assuming_what_she_wants_is_banned_even_when_denied():
    """"no como una estrategia para que vuelva" already assumes she wants him
    back — denying the goal still asserts it."""
    prompt = get_eldric_prompt("es")

    assert "Prohibido suponer que quiere" in prompt
    assert "ni siquiera para negarlo" in prompt


def test_her_own_words_must_not_be_escalated():
    prompt = get_eldric_prompt("es")

    assert "sin subirle la" in prompt and "intensidad" in prompt


def test_asking_is_the_way_out_of_assuming():
    prompt = get_eldric_prompt("es")

    assert "Preguntar no" in prompt and "suponer si" in prompt


def test_the_rule_does_not_ask_eldric_to_be_cold():
    """A ban on assuming feelings could easily be read as a ban on warmth."""
    prompt = get_eldric_prompt("es")

    assert "no te obliga a ser frio" in prompt


@pytest.mark.parametrize("language", ["en", "ru"])
def test_other_languages_stay_minimal_for_now(language):
    """Rules are being rebuilt in Spanish first, where the failures are being
    observed. Pinned so nobody assumes the other languages carry them."""
    prompt = get_eldric_prompt(language)

    assert "Eldric" in prompt
    assert "NO DES POR HECHO" not in prompt
