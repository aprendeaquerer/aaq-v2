"""Deterministic crisis-safety rails.

When a user message contains signals of suicide/self-harm, partner or domestic
violence, sexual assault, or a minor in danger, the chat flow short-circuits and
returns a fixed, verified safety message instead of a model-generated reply.

Design notes:
- Detection is deterministic (no LLM). Resources always surface, even if the AI
  provider fails.
- Matching runs on an accent-stripped, lowercased copy of the message. Patterns
  are phrase-level (not single ambiguous words) to keep false positives low.
- Because the behavior is a hard override of the normal coaching flow, the design
  errs toward catching real cases. A false positive costs one interrupted turn;
  a false negative can cost far more.
- Phone lines were verified against official sources (Ministerio de Sanidad 024,
  Ministerio de Igualdad 016, Fundacion ANAR, 988 Lifeline, Samaritans, RAINN,
  Childhelp, Russian all-country helpline). Review periodically.
"""

import unicodedata
from typing import List, Optional

# --- Crisis categories (priority order: first match wins) ---
SUICIDE = "suicide"
PARTNER_VIOLENCE = "partner_violence"
SEXUAL_ASSAULT = "sexual_assault"
MINOR_SAFETY = "minor_safety"

CRISIS_PRIORITY = (SUICIDE, PARTNER_VIOLENCE, SEXUAL_ASSAULT, MINOR_SAFETY)

SUPPORTED_LANGUAGES = ("es", "en", "ru")


def _normalize(text: str) -> str:
    """Lowercase and strip Latin accents. Cyrillic is left intact."""
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# Patterns are stored accent-stripped and lowercase. They are matched across all
# languages regardless of the UI language, since users may write in any language.
_PATTERNS = {
    SUICIDE: [
        # Spanish
        "quiero morir", "quiero morirme", "me quiero morir", "no quiero vivir",
        "no quiero seguir viviendo", "ya no quiero vivir", "quitarme la vida",
        "acabar con mi vida", "poner fin a mi vida", "quiero matarme",
        "me quiero matar", "voy a matarme", "pienso en matarme", "me voy a suicidar",
        "quiero suicidarme", "pienso en suicidarme", "suicidarme", "suicidio",
        "me pego un tiro", "hacerme dano", "quiero hacerme dano", "autolesion",
        "autolesionarme", "cortarme las venas", "no vale la pena vivir",
        "mejor estar muerto", "mejor estar muerta", "no aguanto mas y quiero acabar",
        "desaparecer para siempre",
        # English
        "want to die", "i wanna die", "kill myself", "killing myself",
        "end my life", "end it all", "take my own life", "suicidal", "suicide",
        "hurt myself", "harm myself", "self-harm", "self harm", "cut myself",
        "don't want to live", "dont want to live", "better off dead",
        "no reason to live", "no point in living",
        # Russian
        "покончить с собой", "покончу с собой", "убить себя", "убью себя",
        "не хочу жить", "хочу умереть", "хочу умирать", "свести счеты с жизнью",
        "суицид", "самоубийств", "причинить себе вред", "резать себя",
        "нет смысла жить", "лучше бы я умер", "лучше бы я умерла",
    ],
    PARTNER_VIOLENCE: [
        # Spanish
        "mi novio me pega", "mi pareja me pega", "mi marido me pega",
        "mi esposo me pega", "me pega mi novio", "me pega mi pareja",
        "me pega mi marido", "me pega mi esposo", "me pegan en casa",
        "me da una paliza", "me da palizas", "me da golpes", "me golpea",
        "me maltrata", "malos tratos", "me pega punetazos", "me tira del pelo",
        "me empuja", "me ha pegado", "me ha encerrado", "me tiene encerrada",
        "me tiene encerrado", "me encierra", "no me deja salir", "no me deja salir de casa",
        "no me deja ver a", "me amenaza", "amenaza con pegarme", "amenaza con matarme",
        "tengo miedo de mi novio", "tengo miedo de mi pareja", "tengo miedo de mi marido",
        "me agrede", "violencia de genero", "violencia domestica", "me da miedo mi pareja",
        # English
        "he hits me", "she hits me", "my boyfriend hits me", "my partner hits me",
        "my husband hits me", "he beats me", "beats me", "he hit me", "he punched me",
        "he locked me", "locked me in", "he won't let me leave", "he wont let me leave",
        "won't let me leave the house", "he threatens me", "threatens to kill me",
        "afraid of my boyfriend", "afraid of my partner", "afraid of my husband",
        "he abuses me", "he is abusing me", "domestic violence", "he chokes me",
        "he strangled me", "he pushed me",
        # Russian
        "он меня бьёт", "он меня бьет", "муж меня бьёт", "муж меня бьет",
        "парень меня бьёт", "парень меня бьет", "избивает меня", "бьёт меня",
        "бьет меня", "запер меня", "запирает меня", "не выпускает меня",
        "не даёт выйти", "не дает выйти", "угрожает мне", "угрожает убить",
        "боюсь своего парня", "боюсь мужа", "домашнее насилие", "он меня душит",
    ],
    SEXUAL_ASSAULT: [
        # Spanish
        "me violo", "me violaron", "me han violado", "violacion", "abuso sexual",
        "abuso de mi", "me forzo a tener sexo", "me obligo a tener sexo",
        "sin mi consentimiento", "me agredio sexualmente", "agresion sexual",
        "me toco sin permiso", "me manoseo",
        # English
        "raped me", "was raped", "i was raped", "sexual assault", "sexually assaulted",
        "molested me", "he molested", "forced me to have sex", "without my consent",
        "assaulted me sexually",
        # Russian
        "изнасиловал", "изнасиловали", "изнасилование", "сексуальное насилие",
        "принудил к сексу", "без моего согласия", "домогательства", "надругались надо мной",
    ],
    MINOR_SAFETY: [
        # Spanish
        "abusan de un nino", "abusan de una nina", "abuso de menores",
        "abuso a un menor", "maltratan a mi hijo", "maltratan a mi hija",
        "le pegan a mi hijo", "le pegan a mi hija", "pegan a un nino",
        "un nino en peligro", "una nina en peligro", "un menor en peligro",
        "tocan a un nino", "tocan a una nina", "abusan de mi hijo", "abusan de mi hija",
        # English
        "child abuse", "abusing a child", "a child is being abused", "child in danger",
        "they hit my son", "they hit my daughter", "minor in danger", "kid is being abused",
        # Russian
        "жестокое обращение с ребёнком", "жестокое обращение с ребенком",
        "насилие над ребёнком", "насилие над ребенком", "ребёнок в опасности",
        "ребенок в опасности", "бьют ребёнка", "бьют ребенка", "издеваются над ребёнком",
    ],
}


def detect_crisis(message: str) -> Optional[str]:
    """Return the crisis category for a message, or None.

    Categories are checked in CRISIS_PRIORITY order and the first match wins.
    """
    if not message:
        return None
    normalized = _normalize(message)
    for category in CRISIS_PRIORITY:
        for pattern in _PATTERNS[category]:
            if pattern in normalized:
                return category
    return None


def _language(language: str) -> str:
    return language if language in SUPPORTED_LANGUAGES else "es"


# Fixed, verified safety messages. Plain language, no diagnosis, no judgement.
_MESSAGES = {
    SUICIDE: {
        "es": (
            "Lo que cuentas es serio y me importa. Soy un bot educativo, no un servicio "
            "de emergencia, así que quiero darte contacto con personas que pueden ayudarte ahora mismo.\n\n"
            "En España:\n"
            "• Emergencias: 112\n"
            "• Línea de atención a la conducta suicida: 024 (24 h, gratuita y confidencial)\n\n"
            "Si estás en peligro inmediato, llama al 112. Si puedes, díselo también a alguien "
            "de confianza que esté cerca de ti."
        ),
        "en": (
            "What you're describing is serious and it matters. I'm an educational bot, not an "
            "emergency service, so I want to connect you with people who can help right now.\n\n"
            "• Emergency: 911 (US) / 999 (UK) / 112 (EU)\n"
            "• Suicide & Crisis Lifeline: call or text 988 (US) — Samaritans: 116 123 (UK & Ireland)\n"
            "• Find a helpline in your country: findahelpline.com\n\n"
            "If you're in immediate danger, call your local emergency number. If you can, reach out "
            "to someone you trust nearby too."
        ),
        "ru": (
            "То, что ты описываешь, серьёзно, и это важно. Я обучающий бот, а не экстренная служба, "
            "поэтому хочу дать контакты тех, кто может помочь прямо сейчас.\n\n"
            "• Экстренные службы: 112\n"
            "• Всероссийский телефон доверия (дети, подростки и взрослые): 8-800-2000-122 "
            "(бесплатно, конфиденциально)\n"
            "• Найти линию помощи: findahelpline.com/countries/ru\n\n"
            "Если ты в непосредственной опасности, звони 112. Если можешь, расскажи об этом близкому "
            "человеку рядом."
        ),
    },
    PARTNER_VIOLENCE: {
        "es": (
            "Lo que describes es violencia, y tu seguridad es lo primero. No soy un servicio de "
            "emergencia; hay recursos especializados que pueden ayudarte.\n\n"
            "En España:\n"
            "• Emergencias: 112\n"
            "• Atención a la violencia contra la mujer: 016 (24 h, gratuito y confidencial, no deja "
            "rastro en la factura; también WhatsApp 600 000 016)\n\n"
            "Si estás en peligro ahora, llama al 112. El 016 puede orientarte sobre qué hacer y cómo "
            "protegerte, aunque todavía no quieras denunciar."
        ),
        "en": (
            "What you're describing is violence, and your safety comes first. I'm not an emergency "
            "service, but there are people trained to help.\n\n"
            "• Emergency: 911 (US) / 999 (UK) / 112 (EU)\n"
            "• US National Domestic Violence Hotline: 1-800-799-7233 (24/7)\n"
            "• Find a local helpline: findahelpline.com\n\n"
            "If you're in danger right now, call your local emergency number. A hotline can help you "
            "think through how to stay safe, even if you're not ready to report anything."
        ),
        "ru": (
            "То, что ты описываешь, — это насилие, и твоя безопасность на первом месте. Я не "
            "экстренная служба, но есть специалисты, которые могут помочь.\n\n"
            "• Экстренные службы: 112 (или 102 — полиция)\n"
            "• Всероссийский телефон доверия: 8-800-2000-122\n"
            "• Найти линию помощи: findahelpline.com/countries/ru\n\n"
            "Если тебе угрожает опасность прямо сейчас, звони 112. Горячая линия поможет понять, как "
            "защитить себя, даже если ты пока не готова обращаться в полицию."
        ),
    },
    SEXUAL_ASSAULT: {
        "es": (
            "Siento lo que ha pasado, y no es culpa tuya. Hay servicios especializados que pueden "
            "ayudarte.\n\n"
            "En España:\n"
            "• Emergencias: 112\n"
            "• Atención a la violencia sexual y contra la mujer: 016 (24 h, gratuito y confidencial; "
            "también WhatsApp 600 000 016)\n\n"
            "Si ha sido reciente o estás en peligro, llama al 112. El 016 atiende también la violencia "
            "sexual y puede orientarte sobre atención médica y tus opciones."
        ),
        "en": (
            "I'm sorry this happened, and it is not your fault. There are trained services that can help.\n\n"
            "• Emergency: 911 (US) / 999 (UK) / 112 (EU)\n"
            "• US National Sexual Assault Hotline (RAINN): 1-800-656-4673 (24/7)\n"
            "• Find a local helpline: findahelpline.com\n\n"
            "If it was recent or you're in danger, call your local emergency number. A hotline can guide "
            "you on medical care and your options."
        ),
        "ru": (
            "Мне жаль, что это произошло, и это не твоя вина. Есть службы, которые могут помочь.\n\n"
            "• Экстренные службы: 112\n"
            "• Всероссийский телефон доверия: 8-800-2000-122\n"
            "• Найти линию помощи: findahelpline.com/countries/ru\n\n"
            "Если это случилось недавно или тебе угрожает опасность, звони 112."
        ),
    },
    MINOR_SAFETY: {
        "es": (
            "Cuando un menor puede estar en peligro, lo primero es su protección.\n\n"
            "En España:\n"
            "• Emergencias: 112\n"
            "• Teléfono ANAR de ayuda a niños y adolescentes: 900 20 20 10 o 116 111 (24 h, gratuito "
            "y confidencial)\n"
            "• Atención a la violencia contra la mujer: 016\n\n"
            "Si un menor está en peligro inmediato, llama al 112."
        ),
        "en": (
            "When a child may be in danger, protecting them comes first.\n\n"
            "• Emergency: 911 (US) / 999 (UK) / 112 (EU)\n"
            "• US Childhelp National Child Abuse Hotline: 1-800-422-4453 (24/7)\n"
            "• Find a local helpline: findahelpline.com\n\n"
            "If a child is in immediate danger, call your local emergency number."
        ),
        "ru": (
            "Когда ребёнок может быть в опасности, его защита — самое важное.\n\n"
            "• Экстренные службы: 112\n"
            "• Всероссийский детский телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно)\n"
            "• Найти линию помощи: findahelpline.com/countries/ru\n\n"
            "Если ребёнок в непосредственной опасности, звони 112."
        ),
    },
}


def build_safety_response(category: str, language: str = "es") -> str:
    """Return the fixed safety message for a category and language."""
    lang = _language(language)
    messages = _MESSAGES.get(category)
    if not messages:
        messages = _MESSAGES[SUICIDE]
    return messages.get(lang, messages["es"])


def crisis_categories() -> List[str]:
    return list(CRISIS_PRIORITY)
