"""Tests for the deterministic crisis-safety rails."""

import pytest

from app.services import safety


# --- True positives: each must fire the expected category ---

POSITIVE_CASES = [
    # Suicide / self-harm
    ("no quiero vivir más, quiero morirme", safety.SUICIDE),
    ("estoy pensando en suicidarme", safety.SUICIDE),
    ("a veces quiero hacerme daño", safety.SUICIDE),
    ("I don't want to live anymore", safety.SUICIDE),
    ("sometimes I want to kill myself", safety.SUICIDE),
    ("не хочу жить, хочу умереть", safety.SUICIDE),
    # Partner / domestic violence
    ("mi novio me pega cuando discutimos", safety.PARTNER_VIOLENCE),
    ("me ha encerrado en casa y no me deja salir", safety.PARTNER_VIOLENCE),
    ("tengo miedo de mi pareja, me amenaza", safety.PARTNER_VIOLENCE),
    ("my boyfriend hits me", safety.PARTNER_VIOLENCE),
    ("he locked me in and won't let me leave", safety.PARTNER_VIOLENCE),
    ("муж меня бьёт", safety.PARTNER_VIOLENCE),
    # Sexual assault
    ("me violó mi ex", safety.SEXUAL_ASSAULT),
    ("fue abuso sexual, no di mi consentimiento", safety.SEXUAL_ASSAULT),
    ("he raped me last night", safety.SEXUAL_ASSAULT),
    ("это было сексуальное насилие", safety.SEXUAL_ASSAULT),
    # Minor safety
    ("creo que abusan de un niño en mi edificio", safety.MINOR_SAFETY),
    ("I think this is child abuse", safety.MINOR_SAFETY),
    ("ребёнок в опасности", safety.MINOR_SAFETY),
]


@pytest.mark.parametrize("message,expected", POSITIVE_CASES)
def test_detects_crisis(message, expected):
    assert safety.detect_crisis(message) == expected


# --- True negatives: ordinary coaching messages must NOT fire ---

NEGATIVE_CASES = [
    "me peleé con mi novia y no sé cómo hablarlo",
    "esta semana me estoy matando a trabajar",
    "esa película es para morirse de risa",
    "el sol me pega de lleno por la mañana",
    "quiero mejorar la comunicación con mi pareja",
    "I'm dying to see that movie tonight",
    "work is killing me this week",
    "how do I set a boundary with my mom",
    "мне нравится проводить время с ребёнком",
    "хочу улучшить отношения с партнёром",
    "",
]


@pytest.mark.parametrize("message", NEGATIVE_CASES)
def test_ignores_non_crisis(message):
    assert safety.detect_crisis(message) is None


# --- Response builder ---

@pytest.mark.parametrize("category", safety.crisis_categories())
@pytest.mark.parametrize("language", ["es", "en", "ru"])
def test_response_has_emergency_and_content(category, language):
    text = safety.build_safety_response(category, language)
    assert text and len(text) > 40
    # Every response surfaces the universal emergency number.
    assert "112" in text


def test_response_language_and_lines():
    es = safety.build_safety_response(safety.SUICIDE, "es")
    assert "024" in es
    en = safety.build_safety_response(safety.SUICIDE, "en")
    assert "988" in en
    dv_es = safety.build_safety_response(safety.PARTNER_VIOLENCE, "es")
    assert "016" in dv_es
    minor_es = safety.build_safety_response(safety.MINOR_SAFETY, "es")
    assert "900 20 20 10" in minor_es


def test_unknown_language_falls_back_to_spanish():
    text = safety.build_safety_response(safety.SUICIDE, "fr")
    assert "024" in text
