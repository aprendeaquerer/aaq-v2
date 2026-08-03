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

_ESTADO_INICIAL = {
    "tipo_turno": "situacion",
    "movimiento": None,
    "movimiento_anterior": None,
    "turnos_recoger_seguidos": 0,
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
    estado["turnos_recoger_seguidos"] = int(estado.get("turnos_recoger_seguidos") or 0)
    estado["rechazos"] = int(estado.get("rechazos") or 0)
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
    """Minimum context before Eldric may name a pattern: fact + goal + one more."""
    llenos = _llenos(ficha)
    return "hecho" in llenos and "objetivo" in llenos and len(llenos) >= 3


def umbral_proponer(ficha: Dict[str, str]) -> bool:
    """On top of the reading, Eldric needs to know what was already tried."""
    return umbral_explicar(ficha) and ficha.get("intentos") in ("filled", "skipped")


def siguiente_hueco(ficha: Dict[str, str]) -> Optional[str]:
    """The one hole Eldric may ask about this turn, or None if nothing is missing."""
    hay_hecho = ficha.get("hecho") == "filled"
    for key in FICHA_ORDEN:
        if ficha.get(key) != "pending":
            continue
        if key in FICHA_REQUIERE_HECHO and not hay_hecho:
            continue
        return key
    return None


def _avance(movimiento: Optional[str]) -> str:
    if movimiento not in MOVIMIENTOS:
        return "explicar"
    indice = MOVIMIENTOS.index(movimiento)
    return MOVIMIENTOS[min(indice + 1, len(MOVIMIENTOS) - 1)]


def _preferido(estado: Dict[str, object], ficha: Dict[str, str], drift: str) -> str:
    if estado["paso_dado"]:
        return "recoger" if drift == "profundiza" else "resolver"
    if not estado["lectura_dada"]:
        return "explicar" if umbral_explicar(ficha) else "recoger"
    if not estado["propuesta_dada"]:
        return "proponer" if umbral_proponer(ficha) else "recoger"
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

    # Going back: a new objective resets the loop, a correction or a new fact
    # invalidates the reading already given.
    if drift == "objetivo_nuevo":
        estado.update(
            lectura_dada=False,
            propuesta_dada=False,
            paso_dado=False,
            turnos_recoger_seguidos=0,
            rechazos=0,
        )
    elif drift == "corrige" or hecho_nuevo:
        estado["lectura_dada"] = False
        estado["propuesta_dada"] = False

    estado["rechazos"] = estado["rechazos"] + 1 if resistencia else 0

    if tipo == "crisis":
        movimiento = "crisis"
    elif tipo == "duda":
        movimiento = "duda"
    elif tipo == "seguimiento":
        movimiento = "seguimiento"
    elif tipo == "descarga":
        # Venting stays in listening unless the value debt is due and there is
        # enough context to say something useful.
        if estado["turnos_recoger_seguidos"] >= 2 and umbral_explicar(ficha_norm):
            movimiento = "explicar"
        else:
            movimiento = "recoger"
    else:
        movimiento = _preferido(estado, ficha_norm, drift)

        # Debt of value: never a third consecutive listening turn.
        if movimiento == "recoger" and estado["turnos_recoger_seguidos"] >= 2:
            if not estado["lectura_dada"]:
                movimiento = "explicar"
            else:
                movimiento = "proponer"

        # Debt of context: no action step before asking what was already tried.
        if movimiento == "resolver" and ficha_norm.get("intentos") == "pending":
            movimiento = "proponer"

        # Two refusals in a row: change the move, never repeat or insist.
        if estado["rechazos"] >= 2 and movimiento == estado.get("movimiento"):
            movimiento = _avance(movimiento)
            estado["rechazos"] = 0

    estado["movimiento_anterior"] = estado.get("movimiento")
    estado["movimiento"] = movimiento
    estado["tipo_turno"] = tipo

    if movimiento == "recoger":
        estado["turnos_recoger_seguidos"] += 1
    elif movimiento in MOVIMIENTOS:
        estado["turnos_recoger_seguidos"] = 0

    if movimiento == "explicar":
        estado["lectura_dada"] = True
    elif movimiento == "proponer":
        estado["propuesta_dada"] = True
    elif movimiento == "resolver":
        estado["paso_dado"] = True

    if movimiento in MOVIMIENTOS:
        estado["reparto"][movimiento] += 1

    estado["hueco_pendiente"] = siguiente_hueco(ficha_norm)
    estado["ficha"] = ficha_norm
    return movimiento, estado


_INSTRUCCIONES = {
    "recoger": [
        "MOVIMIENTO DE ESTE TURNO: RECOGER.",
        "Registra lo que hay sin ponerle etiqueta emocional y sin resumir lo que acaba de decir.",
        "2 a 4 lineas. Prohibido dar plan, consejo o practica en este turno.",
        "Puedes cerrar con UNA sola pregunta, la del hueco pendiente, o con ninguna.",
    ],
    "explicar": [
        "MOVIMIENTO DE ESTE TURNO: EXPLICAR.",
        "Conecta tu los hechos y nombra el patron en afirmativo. Esta lectura es tu trabajo, no la del usuario.",
        "Orden: que esta pasando, por que funciona asi, que lo mantiene.",
        "4 a 8 lineas, apoyado en el knowledge recuperado y aterrizado en su caso concreto.",
        "PROHIBIDO preguntar en este turno: cero signos de interrogacion.",
        "Si te falta contexto, da igualmente la lectura parcial y di en una linea que dato la afinaria.",
    ],
    "proponer": [
        "MOVIMIENTO DE ESTE TURNO: PROPONER.",
        "Convierte la lectura en que se puede hacer, con el criterio de por que.",
        "Una recomendacion principal. Alternativas solo si hay una decision real: maximo dos, con el coste de cada una.",
        "4 a 6 lineas. Todavia no bajes a plan con fechas.",
        "Sin preguntas, salvo que el usuario tenga que elegir entre dos opciones reales.",
    ],
    "resolver": [
        "MOVIMIENTO DE ESTE TURNO: RESOLVER.",
        "Baja la propuesta a una accion concreta para esta semana.",
        "Di que hace, cuando, y en que se va a fijar para saber si funciono.",
        "UN SOLO paso, aunque el plan interno tenga varios. El resto te lo guardas.",
        "3 a 5 lineas. Sin preguntas.",
        "El paso no puede repetir algo que el usuario ya probo y no le funciono.",
    ],
    "duda": [
        "MOVIMIENTO DE ESTE TURNO: RESPONDER LA DUDA.",
        "Responde claro y directo con el knowledge disponible. No abras el bucle de coaching.",
        "No conviertas una duda sencilla en un plan largo ni en una exploracion.",
    ],
    "seguimiento": [
        "MOVIMIENTO DE ESTE TURNO: SEGUIMIENTO.",
        "El usuario vuelve despues de un paso acordado. Empieza por el resultado de ese paso, no por como esta.",
        "Si lo hizo y funciono: nombra que funciono y por que, y da el siguiente paso.",
        "Si lo hizo y no funciono: vuelve a recoger el hecho. El fallo es un dato.",
        "Si no lo hizo: una sola pregunta al motivo practico. Si ya son dos veces, cambia el paso por uno mas pequeno, no lo repitas.",
    ],
    "crisis": [
        "MOVIMIENTO DE ESTE TURNO: SEGURIDAD.",
        "La seguridad va antes que cualquier estrategia. Aplica las reglas de seguridad y orienta a ayuda real.",
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

    hueco = estado.get("hueco_pendiente")
    if movimiento in ("recoger", "seguimiento") and hueco in FICHA_PREGUNTAS:
        bloque.append(
            f"Si preguntas, pregunta solo por esto: {hueco}. "
            f"Formulacion de referencia: \"{FICHA_PREGUNTAS[hueco]}\". "
            "Adaptala a sus palabras, manten 4 o 5 palabras y no la encadenes con otra."
        )
    elif movimiento in ("recoger", "seguimiento"):
        bloque.append("No falta ningun dato critico: avanza sin preguntar.")

    if movimiento == "explicar" and not umbral_explicar(_normalizar_ficha(estado.get("ficha"))):
        bloque.append(
            "Llevas dos turnos recogiendo sin entregar nada. Da ahora la lectura parcial aunque falte contexto."
        )

    return "\n".join(bloque)
