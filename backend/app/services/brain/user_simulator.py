"""Simulated-user turn generation.

Lets the configured AI provider role-play a user persona so the QA / tests tab can
run live example conversations against the real bot and inspect how it responds and
where it pulls information from.
"""

from typing import Dict, List

from app.schemas.brain import (
    SimulateUserTurnRequest,
    SimulateUserTurnResponse,
    SimulatedPersona,
)
from app.services.ai.factory import get_ai_provider


STYLE_GUIDE_ES: Dict[str, str] = {
    "anxious": (
        "Tienes apego ansioso: te preocupa el abandono, das muchas vueltas a lo que "
        "significan los mensajes o silencios, buscas que te tranquilicen y te cuesta "
        "poner limites por miedo a que la otra persona se aleje."
    ),
    "avoidant": (
        "Tienes apego evitativo: te incomoda depender de alguien, restas importancia a "
        "lo que sientes, cambias de tema cuando la conversacion se pone muy intima y "
        "valoras mucho tu independencia."
    ),
    "secure": (
        "Tienes apego seguro: te comunicas de forma clara, expresas lo que necesitas sin "
        "dramatizar y estas abierto a mirar tu parte del problema."
    ),
    "disorganized": (
        "Tienes apego desorganizado: alternas entre querer acercarte y querer alejarte, "
        "mandas senales mezcladas y a veces tu propia reaccion te confunde."
    ),
}

STYLE_GUIDE_EN: Dict[str, str] = {
    "anxious": (
        "You have anxious attachment: you fear abandonment, over-analyze messages and "
        "silences, seek reassurance, and struggle to set boundaries in case the other "
        "person pulls away."
    ),
    "avoidant": (
        "You have avoidant attachment: you are uncomfortable depending on others, you "
        "downplay your feelings, you change the subject when things get too intimate, and "
        "you value your independence highly."
    ),
    "secure": (
        "You have secure attachment: you communicate clearly, express your needs without "
        "drama, and are open to looking at your own part of the problem."
    ),
    "disorganized": (
        "You have disorganized attachment: you swing between wanting closeness and wanting "
        "distance, you send mixed signals, and sometimes your own reactions confuse you."
    ),
}


def _persona_lines(persona: SimulatedPersona, language: str) -> str:
    label = {
        "nombre": "Nombre" if language == "es" else "Name",
        "edad": "Edad" if language == "es" else "Age",
        "genero": "Genero" if language == "es" else "Gender",
        "orientacion": "Orientacion" if language == "es" else "Orientation",
        "tipo_relacion": "Situacion de pareja" if language == "es" else "Relationship",
        "escenario": "Lo que te pasa ahora" if language == "es" else "What is going on",
        "contexto": "Contexto" if language == "es" else "Context",
    }
    parts: List[str] = []
    if persona.nombre:
        parts.append(f"- {label['nombre']}: {persona.nombre}")
    if persona.edad is not None:
        parts.append(f"- {label['edad']}: {persona.edad}")
    if persona.genero:
        parts.append(f"- {label['genero']}: {persona.genero}")
    if persona.orientacion:
        parts.append(f"- {label['orientacion']}: {persona.orientacion}")
    if persona.tipo_relacion:
        parts.append(f"- {label['tipo_relacion']}: {persona.tipo_relacion}")
    if persona.escenario:
        parts.append(f"- {label['escenario']}: {persona.escenario}")
    if persona.contexto:
        parts.append(f"- {label['contexto']}: {persona.contexto}")
    return "\n".join(parts)


def _build_system_prompt(request: SimulateUserTurnRequest) -> str:
    persona = request.persona
    language = request.language or "es"
    style_key = (persona.attachment_style or "").strip().lower()

    if language == "es":
        style_guide = STYLE_GUIDE_ES.get(style_key, "")
        closing = (
            "Es uno de tus ultimos mensajes: cierra la conversacion de forma natural "
            "(agradece, di que lo vas a pensar o que lo dejas por hoy)."
            if request.turn_number >= request.max_turns
            else "Sigue la conversacion de forma natural."
        )
        return (
            "Eres una persona real escribiendo por chat a un coach de relaciones (un bot). "
            "NO eres el coach. Interpretas al personaje de abajo y respondes SIEMPRE en "
            "primera persona, como si le escribieras tu al coach.\n\n"
            "PERSONAJE:\n"
            f"{_persona_lines(persona, language)}\n"
            f"{('- ' + style_guide) if style_guide else ''}\n\n"
            "COMO ESCRIBIR:\n"
            "- Un solo mensaje por turno, corto (1 a 4 frases), como un chat real.\n"
            "- Habla natural y coloquial. Nada de lenguaje de manual ni de terapeuta.\n"
            "- Revela tu situacion poco a poco, no lo sueltes todo de golpe.\n"
            "- Responde a lo ultimo que te ha dicho el coach; puedes dudar, resistirte o "
            "abrirte segun tu personaje.\n"
            "- No hagas de coach, no te des consejos a ti mismo, no rompas el personaje.\n"
            "- No uses asteriscos, ni acotaciones, ni comillas. Devuelve solo el mensaje.\n"
            f"- {closing}"
        )

    style_guide = STYLE_GUIDE_EN.get(style_key, "")
    closing = (
        "This is one of your last messages: close the conversation naturally (thank them, "
        "say you will think about it or leave it for today)."
        if request.turn_number >= request.max_turns
        else "Keep the conversation going naturally."
    )
    return (
        "You are a real person chatting with a relationship coach (a bot). You are NOT the "
        "coach. Play the character below and always answer in the first person, as if you "
        "were writing to the coach.\n\n"
        "CHARACTER:\n"
        f"{_persona_lines(persona, language)}\n"
        f"{('- ' + style_guide) if style_guide else ''}\n\n"
        "HOW TO WRITE:\n"
        "- One single message per turn, short (1 to 4 sentences), like a real chat.\n"
        "- Speak naturally and casually. No textbook or therapist language.\n"
        "- Reveal your situation gradually, do not dump everything at once.\n"
        "- Respond to the last thing the coach said; you can hesitate, resist, or open up "
        "depending on your character.\n"
        "- Do not act as the coach, do not advise yourself, do not break character.\n"
        "- No asterisks, stage directions, or quotes. Return only the message.\n"
        f"- {closing}"
    )


def _build_messages(request: SimulateUserTurnRequest) -> List[Dict[str, str]]:
    """Map the shared history to the simulator's point of view.

    From the simulator's side it is the "assistant": the persona's past messages are
    assistant turns, and the bot's messages are the user turns it must reply to.
    """
    messages: List[Dict[str, str]] = []
    for turn in request.history:
        role = "assistant" if turn.role == "persona" else "user"
        messages.append({"role": role, "content": turn.content})

    # The provider needs a leading user turn. If the persona opens the conversation,
    # inject a kickoff instruction.
    if not messages or messages[0]["role"] != "user":
        kickoff = (
            "(Empieza tu la conversacion contandole al coach que te pasa.)"
            if (request.language or "es") == "es"
            else "(Start the conversation by telling the coach what is going on.)"
        )
        messages.insert(0, {"role": "user", "content": kickoff})

    # Providers require the last turn to be from the user for a completion.
    if messages[-1]["role"] != "user":
        nudge = (
            "(Continua con tu siguiente mensaje.)"
            if (request.language or "es") == "es"
            else "(Continue with your next message.)"
        )
        messages.append({"role": "user", "content": nudge})

    return messages


async def generate_user_turn(request: SimulateUserTurnRequest) -> SimulateUserTurnResponse:
    provider = get_ai_provider()
    system_prompt = _build_system_prompt(request)
    messages = _build_messages(request)

    raw = await provider.chat(
        system_prompt=system_prompt,
        messages=messages,
        temperature=0.9,
        max_tokens=220,
    )

    message = _clean(raw)
    should_end = request.turn_number >= request.max_turns
    return SimulateUserTurnResponse(message=message, should_end=should_end)


def _clean(text: str) -> str:
    cleaned = (text or "").strip()
    # Strip wrapping quotes the model sometimes adds.
    if len(cleaned) >= 2 and cleaned[0] in "\"'" and cleaned[-1] in "\"'":
        cleaned = cleaned[1:-1].strip()
    return cleaned
