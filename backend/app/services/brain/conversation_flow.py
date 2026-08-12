"""Deterministic director for how Eldric moves through a conversation.

The coaching planner (an LLM) reads the turn and reports *what* it sees: the turn
type, which observable facts are known, whether the user pushed back. This module
decides *which move Eldric makes now* with plain Python, so the balance between
listening, explaining, proposing and resolving is enforced rather than hoped for.

Two debts regulate the balance:

- Debt of value: Eldric cannot chain two turns without delivering something.
  After two consecutive "recoger" turns he is forced to advance.
- Debt of context: Eldric cannot hand over an action step without having asked
  what the user already tried.
"""

from typing import Dict, Optional, Tuple

# The four moves of the loop, in order of advance.
MOVIMIENTOS = ("recoger", "explicar", "proponer", "resolver")

# Turn types the planner may report. Only "situacion" and "seguimiento" run the loop.
TIPOS_TURNO = ("crisis", "duda", "descarga", "situacion", "seguimiento")

# The six context holes. The planner fills them; empty ones are the only thing
# Eldric is allowed to ask about.
FICHA_KEYS = (
    "hecho",
    "frecuencia",
    "conducta_propia",
    "intentos",
    "objetivo",
    "supuesto",
)

FICHA_PREGUNTAS = {
    "hecho": "Que paso exactamente?",
    "frecuencia": "Cuanto lleva pasando?",
    "conducta_propia": "Que haces tu entonces?",
    "intentos": "Que has probado ya?",
    "objetivo": "Que quieres conseguir?",
    "supuesto": "En que lo notas?",
}

# Order in which empty holes are asked about.
FICHA_ORDEN = ("hecho", "objetivo", "supuesto", "intentos", "conducta_propia", "frecuencia")

# Holes that only make sense once there is a concrete fact on the table.
FICHA_REQUIERE_HECHO = ("frecuencia", "conducta_propia", "intentos")

# A hole can stay empty forever if the user never answers. After this many turns of
# asking for "intentos", the engine stops letting it block the action step.
TURNOS_MAX_PIDIENDO_INTENTOS = 2

# No move may run more than this many turns in a row. Without it, a planner that keeps
# reporting new facts traps the loop in "explicar" and the user never gets a step.
TURNOS_MAX_MISMO_MOVIMIENTO = 2

# A new fact or a correction invalidates the reading, but only so many times. A planner
# that reports one every turn would otherwise keep the loop in "explicar" forever.
RESETS_MAX_DE_LECTURA = 2

# Total gathering turns allowed per objective, consecutive or not. The debt of value
# only caps them back to back, so a loop that alternates recoger / explicar / recoger
# still spent almost half its turns asking. Past this, Eldric has to deliver.
TOPE_RECOGER_POR_OBJETIVO = 3

# Same idea for the reading. A planner that corrects or reports a new fact keeps
# invalidating it, and the fifth run spent 47% of its turns explaining. Two readings
# per objective is enough; past that, move on with the one you have.
TOPE_EXPLICAR_POR_OBJETIVO = 2

_ESTADO_INICIAL = {
    "tipo_turno": "situacion",
    "movimiento": None,
    "movimiento_anterior": None,
    "turnos_recoger_seguidos": 0,
    "recoger_en_objetivo": 0,
    "explicar_en_objetivo": 0,
    "turnos_mismo_movimiento": 0,
    "turnos_pidiendo_intentos": 0,
    "intentos_agotado": False,
    "resets_de_lectura": 0,
    "lectura_dada": False,
    "propuesta_dada": False,
    "paso_dado": False,
    "rechazos": 0,
    "reparto": {"recoger": 0, "explicar": 0, "proponer": 0, "resolver": 0},
}


def estado_inicial() -> Dict[str, object]:
    estado = dict(_ESTADO_INICIAL)
    estado["reparto"] = dict(_ESTADO_INICIAL["reparto"])
    return estado


def _normalizar_estado(previo: Optional[Dict[str, object]]) -> Dict[str, object]:
    estado = estado_inicial()
    if isinstance(previo, dict):
        for key, value in previo.items():
            if key in estado:
                estado[key] = value
    reparto = estado.get("reparto")
    if not isinstance(reparto, dict):
        reparto = {}
    estado["reparto"] = {mov: int(reparto.get(mov, 0) or 0) for mov in MOVIMIENTOS}
    for contador in (
        "turnos_recoger_seguidos",
        "recoger_en_objetivo",
        "explicar_en_objetivo",
        "turnos_mismo_movimiento",
        "turnos_pidiendo_intentos",
        "resets_de_lectura",
        "rechazos",
    ):
        estado[contador] = int(estado.get(contador) or 0)
    estado["intentos_agotado"] = bool(estado.get("intentos_agotado"))
    return estado


def _normalizar_ficha(ficha: Optional[Dict[str, object]]) -> Dict[str, str]:
    normalizada = {}
    origen = ficha if isinstance(ficha, dict) else {}
    for key in FICHA_KEYS:
        status = origen.get(key)
        if isinstance(status, dict):
            status = status.get("status")
        if status not in ("filled", "skipped", "pending"):
            status = "pending"
        normalizada[key] = status
    return normalizada


def _llenos(ficha: Dict[str, str]) -> set:
    return {key for key, status in ficha.items() if status == "filled"}


def umbral_explicar(ficha: Dict[str, str]) -> bool:
    """Minimum context before Eldric may name a pattern.

    This used to require the goal. People rarely state one out loud, so the fourth run
    spent 44% of its turns stuck in "recoger" waiting for a hole that never filled. A
    concrete fact plus two other observables is enough to read a pattern; the goal
    still counts as one of the two.
    """
    llenos = _llenos(ficha)
    return "hecho" in llenos and len(llenos) >= 3


def umbral_proponer(ficha: Dict[str, str], intentos_agotado: bool = False) -> bool:
    """On top of the reading, Eldric needs to know what was already tried.

    `intentos_agotado` covers the user who simply never answers that question: after a
    couple of tries the engine stops treating it as a blocker, otherwise the loop can
    never reach an action step.
    """
    if not umbral_explicar(ficha):
        return False
    return intentos_agotado or ficha.get("intentos") in ("filled", "skipped")


def siguiente_hueco(ficha: Dict[str, str], priorizar_intentos: bool = False) -> Optional[str]:
    """The one hole Eldric may ask about this turn, or None if nothing is missing.

    Once a reading has been given, `intentos` jumps the queue: it is the only hole
    standing between the conversation and an action step.
    """
    orden = FICHA_ORDEN
    if priorizar_intentos:
        orden = ("intentos",) + tuple(k for k in FICHA_ORDEN if k != "intentos")
    hay_hecho = ficha.get("hecho") == "filled"
    for key in orden:
        if ficha.get(key) != "pending":
            continue
        if key in FICHA_REQUIERE_HECHO and not hay_hecho:
            continue
        return key
    return None


def _avance(movimiento: Optional[str]) -> str:
    """The move after this one. After the last one the loop starts again.

    "resolver" wraps back to "recoger": two action steps in a row means the next one
    needs fresh context, not a third step nobody asked for.
    """
    if movimiento not in MOVIMIENTOS:
        return "explicar"
    indice = MOVIMIENTOS.index(movimiento)
    if indice == len(MOVIMIENTOS) - 1:
        return "recoger"
    return MOVIMIENTOS[indice + 1]


def _preferido(estado: Dict[str, object], ficha: Dict[str, str], drift: str) -> str:
    agotado = bool(estado.get("intentos_agotado"))
    if estado["paso_dado"]:
        return "recoger" if drift == "profundiza" else "resolver"
    if not estado["lectura_dada"]:
        return "explicar" if umbral_explicar(ficha) else "recoger"
    if not estado["propuesta_dada"]:
        return "proponer" if umbral_proponer(ficha, agotado) else "recoger"
    return "resolver"


def decidir_movimiento(
    previo: Optional[Dict[str, object]],
    tipo_turno: Optional[str],
    ficha: Optional[Dict[str, object]],
    drift: Optional[str] = None,
    resistencia: bool = False,
    hecho_nuevo: bool = False,
) -> Tuple[str, Dict[str, object]]:
    """Return the move for this turn and the state to persist."""

    estado = _normalizar_estado(previo)
    ficha_norm = _normalizar_ficha(ficha)
    drift = drift if isinstance(drift, str) else "nada"
    tipo = tipo_turno if tipo_turno in TIPOS_TURNO else "situacion"

    # Going back. Note what is NOT reset here: `turnos_mismo_movimiento`. That counter
    # is what stops a move repeating, and the third QA run showed a planner emitting
    # "corrige" and "objetivo_nuevo" on alternate turns, which cleared the counter every
    # time and let Eldric explain three turns in a row anyway.
    if drift == "objetivo_nuevo":
        estado.update(
            lectura_dada=False,
            propuesta_dada=False,
            paso_dado=False,
            turnos_recoger_seguidos=0,
            recoger_en_objetivo=0,
            explicar_en_objetivo=0,
            turnos_pidiendo_intentos=0,
            intentos_agotado=False,
            resets_de_lectura=0,
            rechazos=0,
        )
    elif (drift == "corrige" or hecho_nuevo) and estado["resets_de_lectura"] < RESETS_MAX_DE_LECTURA:
        estado["resets_de_lectura"] += 1
        estado["lectura_dada"] = False
        estado["propuesta_dada"] = False

    estado["rechazos"] = estado["rechazos"] + 1 if resistencia else 0

    if tipo == "crisis":
        movimiento = "crisis"
    elif tipo == "duda":
        movimiento = "duda"
    elif tipo == "seguimiento":
        movimiento = "seguimiento"
    elif tipo == "descarga" and not (
        estado["lectura_dada"] and umbral_proponer(ficha_norm, bool(estado["intentos_agotado"]))
    ):
        # Venting stays in listening, but the debt of value applies here too: after two
        # turns of pure listening Eldric delivers a reading, full card or not. This used
        # to allow a third gathering turn when the card was thin, and a live run on
        # 2026-08-10 showed exactly what that buys: three near-identical questions in a
        # row ("que paso?", "que significa fatal?", "hubo alguna situacion?") to a user
        # who had already given the fact in her first message. A partial reading on turn
        # three beats a third question every time; componer_bloque_movimiento already
        # tells the model to deliver it even with missing context.
        if estado["turnos_recoger_seguidos"] >= 2:
            movimiento = "explicar"
        else:
            movimiento = "recoger"
    else:
        movimiento = _preferido(estado, ficha_norm, drift)

        # Debt of value: never a third consecutive listening turn, and never more than
        # TOPE_RECOGER_POR_OBJETIVO gathering turns in the same objective overall.
        if movimiento == "recoger" and (
            estado["turnos_recoger_seguidos"] >= 2
            or estado["recoger_en_objetivo"] >= TOPE_RECOGER_POR_OBJETIVO
        ):
            if not estado["lectura_dada"]:
                movimiento = "explicar"
            else:
                movimiento = "proponer"

        # No move runs three turns in a row. Without this a planner that keeps
        # reporting new facts pins the loop to "explicar" and no step ever arrives.
        if (
            movimiento == estado.get("movimiento")
            and estado["turnos_mismo_movimiento"] >= TURNOS_MAX_MISMO_MOVIMIENTO
        ):
            movimiento = _avance(movimiento)

        # Two readings per objective is the cap: a planner that keeps correcting must
        # not be able to hold the conversation in "explicar" indefinitely.
        if movimiento == "explicar" and estado["explicar_en_objetivo"] >= TOPE_EXPLICAR_POR_OBJETIVO:
            movimiento = "proponer" if umbral_proponer(
                ficha_norm, bool(estado["intentos_agotado"])
            ) else "recoger"

        # Debt of context: no action step before asking what was already tried.
        if (
            movimiento == "resolver"
            and ficha_norm.get("intentos") == "pending"
            and not estado["intentos_agotado"]
        ):
            movimiento = "proponer"

        # Two refusals in a row: change the move, never repeat or insist.
        if estado["rechazos"] >= 2 and movimiento == estado.get("movimiento"):
            movimiento = _avance(movimiento)
            estado["rechazos"] = 0

    anterior = estado.get("movimiento")
    estado["movimiento_anterior"] = anterior
    estado["movimiento"] = movimiento
    estado["tipo_turno"] = tipo
    estado["turnos_mismo_movimiento"] = (
        estado["turnos_mismo_movimiento"] + 1 if movimiento == anterior else 1
    )

    if movimiento == "recoger":
        estado["turnos_recoger_seguidos"] += 1
        estado["recoger_en_objetivo"] += 1
    elif movimiento in MOVIMIENTOS:
        estado["turnos_recoger_seguidos"] = 0

    if movimiento == "explicar":
        estado["lectura_dada"] = True
        estado["explicar_en_objetivo"] += 1
    elif movimiento == "proponer":
        estado["propuesta_dada"] = True
    elif movimiento == "resolver":
        estado["paso_dado"] = True

    if movimiento in MOVIMIENTOS:
        estado["reparto"][movimiento] += 1

    hueco = siguiente_hueco(ficha_norm, priorizar_intentos=bool(estado["lectura_dada"]))
    if hueco == "intentos":
        estado["turnos_pidiendo_intentos"] += 1
        if estado["turnos_pidiendo_intentos"] >= TURNOS_MAX_PIDIENDO_INTENTOS:
            estado["intentos_agotado"] = True

    estado["hueco_pendiente"] = hueco
    estado["ficha"] = ficha_norm
    return movimiento, estado


# The shape of every reply (except the safety rail). Redesigned 2026-08-11 to the
# owner's spec: every turn teaches something from the book, every turn ends with one
# excellent question (the question is what keeps the user writing), and both lean on
# what is already known about this user so the conversation gets more specific over
# time instead of more generic.
_ESTRUCTURA = [
    "FORMA DE LA RESPUESTA, siempre en este orden:",
    "1) Una frase que responde a lo ultimo que ha dicho, sin repetirlo.",
    "2) Una ensenanza del libro aplicada a SU caso. Esto es el centro: en cada turno "
    "aprende algo, desde el primero. Usa el CONTEXTO DEL USUARIO, su memoria y lo que "
    "ya ha contado para aterrizarla: cuanto mas sabes de esta persona, mas especifica "
    "tiene que ser la ensenanza. Nada de parrafos que valdrian para cualquiera.",
    "3) La respuesta TERMINA SIEMPRE con UNA pregunta, y es lo ultimo que se lee.",
    "PREGUNTA EXCELENTE, las cuatro condiciones: (a) especifica de su caso — si valdria "
    "copiada en otra conversacion, no vale aqui; (b) pide un hecho concreto o una "
    "decision que cambia lo que le vas a ensenar despues; (c) corta, menos de 15 "
    "palabras; (d) conecta con la ensenanza que acabas de darle, no cambia de tema.",
    "UNA sola interrogacion en toda la respuesta: la del final. Ninguna antes.",
    "Antes de enviar, comprueba: hay ensenanza, la respuesta acaba en pregunta, y esa "
    "pregunta cumple las cuatro condiciones.",
]

# Applied to every move. These three come straight from the failures the
# 300-conversation QA run counted most often: opening with a summary of what the user
# just said (70 hits), more than one question in a turn (14) and blending moves (23).
_REGLAS_COMUNES = [
    "NO abras la respuesta resumiendo ni repitiendo lo que el usuario acaba de decir. "
    "La primera frase ya tiene que aportar algo que el no haya dicho.",
    "APERTURAS PROHIBIDAS, ninguna respuesta puede empezar asi: \"Entendido\" · \"Entiendo que\" · "
    "\"Te sientes\" · \"Entonces\" · "
    "\"O sea que\" · \"Vale,\" · \"Lo que me cuentas\" · \"Si te he entendido bien\" · "
    "\"Por lo que dices\" · \"Veo que\" · \"Resumiendo\" · \"Asi que\" · repetir sus hechos en fila. "
    "Empieza por el dato nuevo, por la lectura o por la pregunta, no por el resumen.",
    "Haz SOLO este movimiento. No adelantes el siguiente ni metas dos en la misma respuesta.",
    "No menciones ningun hecho que el usuario no haya contado. Si te falta, preguntalo o callatelo.",
    "NUNCA delegues en el usuario por donde seguir. Prohibidas estas preguntas y sus variantes: "
    "\"como te gustaria abordarlo?\" · \"que te gustaria hacer?\" · \"como lo plantearias?\" · "
    "\"que crees que deberias hacer?\" · \"por donde quieres empezar?\" · \"que opcion ves?\" · "
    "\"como lo enfocarias?\" · \"cual seria tu siguiente paso?\". El siguiente paso lo decides tu "
    "y lo dices en afirmativo. Si preguntas, es por un dato que te falta, nunca por la direccion.",
    "No atribuyas a la otra persona sentimientos, intenciones ni interpretaciones como si fueran "
    "hechos. Nada de \"ella puede sentir que...\", \"el lo interpreta como...\". Habla de lo "
    "observable y de lo que le pasa al usuario.",
    "PROHIBIDO preguntar por emociones: nada de \"como te sientes\", \"como estas\", \"como lo "
    "llevas\", \"que sientes\", \"como te quedaste\". Las emociones no se piden, se reconocen "
    "cuando aparecen. Toda pregunta va a un hecho: que paso, que hiciste, que has probado, que "
    "quieres conseguir.",
    "PROHIBIDO sugerir o preguntar si ha hablado o va a hablar del tema con otras personas "
    "(\"alguien\", amigos, familia, un profesional). Hablarlo ya lo esta haciendo: aqui, contigo. "
    "Tu trabajo es conducir esa conversacion, no derivarla. Unica excepcion: el movimiento de "
    "SEGURIDAD, donde orientar a ayuda real es obligatorio.",
    "NO repitas una pregunta ya hecha en la conversacion, ni pidas un dato que el usuario ya "
    "haya dado. Si su respuesta repite algo ya dicho, esa pregunta fallo: pregunta otra cosa.",
]

_INSTRUCCIONES = {
    "recoger": [
        "MOVIMIENTO DE ESTE TURNO: RECOGER.",
        "Si el usuario acaba de expresar malestar (\"fatal\", \"muy mal\", \"hecha polvo\"), "
        "reconocelo en UNA frase corta que NO repita sus palabras ni sus hechos. Bien: \"Eso "
        "duele\", \"Es un golpe\". PROHIBIDO el espejo: \"Te sientes fatal\", \"Entiendo que lo "
        "dejaste\" — eso es devolverle lo que acaba de decir.",
        "La ensenanza de este turno es ligera: un encuadre del libro que le de vocabulario para "
        "entender mejor lo que le pasa. Todavia no des el plan ni la lectura completa del patron.",
        "3 a 5 lineas mas la pregunta final.",
        "La pregunta final va a un hecho observable o a su propia conducta: es el dato que te "
        "falta para afinar la lectura. Nunca a sus emociones, nunca a lo que piensa o siente "
        "otra persona, nunca a que identifique su patron.",
    ],
    "explicar": [
        "MOVIMIENTO DE ESTE TURNO: EXPLICAR.",
        "La ensenanza de este turno es la lectura: conecta tu los hechos y NOMBRA EL PATRON en "
        "afirmativo, apoyado en el knowledge y aterrizado en su caso. Si acabas sin haber "
        "nombrado un patron, el turno no vale. Esta lectura es tu trabajo, no la del usuario.",
        "Orden: que esta pasando, por que funciona asi, que lo mantiene.",
        "4 a 8 lineas mas la pregunta final.",
        "Tampoco des aqui el plan ni la practica: eso es el movimiento siguiente.",
        "Si te falta contexto, da igualmente la lectura parcial.",
        "La pregunta final comprueba la lectura contra la realidad: pide el hecho que la "
        "confirmaria o la desmentiria. No preguntes si esta de acuerdo; pide el dato.",
    ],
    "proponer": [
        "MOVIMIENTO DE ESTE TURNO: PROPONER.",
        "La ensenanza de este turno convierte la lectura en que se puede hacer, con el criterio "
        "de por que. Una recomendacion principal. Alternativas solo si hay una decision real: "
        "maximo dos, con el coste de cada una.",
        "4 a 6 lineas mas la pregunta final. Todavia no bajes a plan con fechas.",
        "No pidas permiso para seguir. Nada de 'te parece si', 'quieres que veamos'.",
        "La pregunta final pide el dato o la eleccion que decide como bajar esto a un paso "
        "concreto: entre dos opciones reales, o el detalle practico que falta.",
    ],
    "resolver": [
        "MOVIMIENTO DE ESTE TURNO: RESOLVER.",
        "La ensenanza de este turno es el paso: baja la propuesta a una accion concreta para "
        "esta semana. Los tres datos son obligatorios: que hace exactamente, cuando lo hace, y "
        "en que se va a fijar para saber si funciono.",
        "UN SOLO paso, aunque el plan interno tenga varios. El resto te lo guardas.",
        "3 a 5 lineas mas la pregunta final.",
        "El paso no puede repetir algo que el usuario ya probo y no le funciono.",
        "No prometas el resultado. Di que va a observar, no lo que va a conseguir.",
        "La pregunta final ancla el paso en su semana real: que dia, en que momento, con que "
        "situacion concreta lo va a probar.",
    ],
    "duda": [
        "MOVIMIENTO DE ESTE TURNO: RESPONDER LA DUDA.",
        "Responde claro y directo con el knowledge disponible. No abras el bucle de coaching.",
        "No conviertas una duda sencilla en un plan largo ni en una exploracion.",
        "La pregunta final trae la respuesta a su caso: pide el hecho de su situacion que "
        "permitiria aplicarle lo que acabas de explicar.",
    ],
    "seguimiento": [
        "MOVIMIENTO DE ESTE TURNO: SEGUIMIENTO.",
        "El usuario vuelve despues de un paso acordado. Empieza por el resultado de ese paso, no por como esta.",
        "Si lo hizo y funciono: nombra que funciono y por que, y ensena el siguiente concepto.",
        "Si lo hizo y no funciono: el fallo es un dato; ensena que suele significar.",
        "Si no lo hizo dos veces, cambia el paso por uno mas pequeno, no lo repitas.",
        "La pregunta final va al resultado observable del paso o al motivo practico de no hacerlo.",
    ],
    "crisis": [
        "MOVIMIENTO DE ESTE TURNO: SEGURIDAD.",
        "La seguridad va antes que cualquier estrategia de relacion, polaridad o atraccion.",
        "Corta el coaching de pareja. No sigas con el caso como si nada.",
        "Nombra lo que ves sin juzgar ni minimizar, y orienta a ayuda real con un recurso concreto.",
        "No pidas detalles que no necesitas y no des tacticas para ocultar, vigilar o convencer a nadie.",
    ],
}


def componer_bloque_movimiento(estado: Optional[Dict[str, object]]) -> str:
    """Render the movement instructions injected into the system prompt."""

    if not isinstance(estado, dict):
        return ""
    movimiento = estado.get("movimiento")
    lineas = _INSTRUCCIONES.get(movimiento)
    if not lineas:
        return ""

    bloque = ["\n\nCONDUCCION DE LA CONVERSACION (interna: no la cites ni nombres las fases)"]
    bloque.extend(lineas)
    if movimiento != "crisis":
        bloque.extend(_ESTRUCTURA)
    bloque.extend(_REGLAS_COMUNES)

    hueco = estado.get("hueco_pendiente")
    if movimiento == "recoger" and hueco in FICHA_PREGUNTAS:
        bloque.append(
            f"El dato que te falta es este: {hueco}. "
            f"Formulacion de referencia: \"{FICHA_PREGUNTAS[hueco]}\". "
            "Adapta la pregunta final a sus palabras y a lo que acabas de ensenarle."
        )

    if movimiento == "explicar" and not umbral_explicar(_normalizar_ficha(estado.get("ficha"))):
        bloque.append(
            "Llevas dos turnos recogiendo sin entregar nada. Da ahora la lectura parcial aunque falte contexto."
        )

    return "\n".join(bloque)
