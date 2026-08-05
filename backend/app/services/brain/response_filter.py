"""Strip acknowledgement and summary openers from Eldric's replies.

Four QA runs in a row, opening the answer by restating what the user had just said
was the most repeated failure, and it never moved: it stayed above 40 hits per 100
conversations through three rounds of prompt rules. Models default to it. So this
stops being a prompt problem and becomes a post-processing one.

The filter is deliberately narrow. Looking at 400 real Eldric turns, most openers are
legitimate:

    "Sí, es completamente normal."          -> a direct answer, keep it
    "Bien. El primer paso es hablar..."     -> "Bien." is filler, the rest is content
    "Entonces la evidencia es que nada..."  -> a reading, not a restatement

Only four shapes are removed, and never at the cost of content:

    R1  bare marker + . or ,   -> drop the marker
    R2  bare marker + :        -> drop the whole sentence (it is a summary list)
    R3  restating connector    -> drop the connector
    R4  first sentence is a verbatim echo of the user -> drop that sentence

Anything that would leave a stub, or a sentence starting with a pronoun that refers
back to what was removed, is left untouched. Safety-rail messages are never touched.

Deliberately conservative. Measured on 710 real user->Eldric pairs it changes 5% of
replies and never breaks one, but it only removes about 9% of what the judge flags as
"opens by restating": most of those are paraphrases, not echoes, and cutting a
paraphrase risks cutting a genuine reading. That part stays a prompt problem.
"""

from __future__ import annotations

import re
from typing import List, Tuple

# Bare discourse markers: they carry no content of their own.
# "si", "no", "exacto" and "correcto" are NOT here: those answer a question.
MARCADORES = (
    "entendido",
    "entiendo",
    "vale",
    "perfecto",
    "de acuerdo",
    "ya veo",
    "muy bien",
    "bien",
    "genial",
    "ok",
    "okay",
    "resumiendo",
    "en resumen",
)

# Connectors that frame what follows as a recap of the user's own words.
CONECTORES = (
    "entonces",
    "asi que",
    "así que",
    "o sea que",
    "o sea",
    "por lo que dices",
    "por lo que cuentas",
    "por lo que me cuentas",
    "lo que me cuentas es que",
    "lo que me dices es que",
    "si te he entendido bien",
    "si lo he entendido bien",
    "a ver si te he entendido",
)

# If the remainder starts with one of these it refers back to the removed text, so
# removing would break the sentence.
ANAFORICOS = (
    "eso", "esto", "ese", "esa", "esos", "esas", "aquello",
    "ahi", "ahí", "asi", "así", "lo mismo", "ambos", "ambas",
    "los dos", "las dos", "por eso", "y eso", "todo eso", "ninguno", "ninguna",
)

# Below this, removing would leave a stub instead of an answer.
MINIMO_RESTANTE = 60

# Never touch a fixed safety message.
_SENALES_RAIL = ("no soy un servicio de emergencia", "findahelpline", "016", "024", "112")

_ALTERNATIVA = lambda opciones: "|".join(re.escape(o) for o in opciones)  # noqa: E731

_R1 = re.compile(rf"^\s*({_ALTERNATIVA(MARCADORES)})\s*[.,;!]+\s+", re.IGNORECASE)
_R2 = re.compile(rf"^\s*({_ALTERNATIVA(MARCADORES)})\s*:\s*", re.IGNORECASE)
_R3 = re.compile(rf"^\s*({_ALTERNATIVA(CONECTORES)})\s*[,:]?\s+", re.IGNORECASE)


def _es_rail_de_seguridad(texto: str) -> bool:
    bajo = texto.lower()
    return sum(1 for senal in _SENALES_RAIL if senal in bajo) >= 2


def _empieza_por_anaforico(texto: str) -> bool:
    primera = texto.lstrip().lower()
    return any(primera.startswith(a + " ") or primera.startswith(a + ",") for a in ANAFORICOS)


def _capitalizar(texto: str) -> str:
    limpio = texto.lstrip()
    if not limpio:
        return limpio
    return limpio[0].upper() + limpio[1:]


def _cortar_primera_frase(texto: str) -> Tuple[str, str]:
    """Split off the first sentence. Returns (first sentence, rest)."""
    corte = re.search(r"(?<=[.!?])\s+", texto)
    if not corte:
        return texto, ""
    return texto[: corte.start()], texto[corte.end():]


# --- Restatement without a marker ------------------------------------------
#
# Most restatements carry no opener at all: "Hace cuatro años están juntos.",
# "Pasaron un año separados." Those are the user's own facts handed back. They are
# caught by comparing the first sentence against what the user just wrote.

_PALABRAS_VACIAS = {
    "a", "al", "algo", "ahora", "ante", "antes", "aqui", "asi", "aun", "aunque", "cada",
    "como", "con", "contra", "cuando", "de", "del", "desde", "donde", "dos", "el", "ella",
    "ellas", "ellos", "en", "entre", "era", "eran", "es", "esa", "ese", "eso", "esta",
    "estan", "este", "esto", "estoy", "fue", "ha", "hace", "han", "hasta", "hay", "he",
    "la", "las", "le", "les", "lo", "los", "mas", "me", "mi", "mucho", "muy", "ni", "no",
    "nos", "o", "para", "pero", "poco", "por", "porque", "que", "se", "segun", "ser",
    "si", "sin", "sobre", "solo", "son", "su", "sus", "tambien", "te", "tiene", "tienen",
    "todo", "tu", "tus", "un", "una", "uno", "unos", "y", "ya", "yo",
}

# The first sentence is a restatement when almost all of its content words already
# appear in the user's message and it contributes almost nothing new.
SOLAPE_MINIMO = 0.75
NUEVAS_MAXIMO = 0
PALABRAS_MINIMO = 3


def _contenido(texto: str) -> List[str]:
    palabras = re.findall(r"[a-záéíóúñü]+", texto.lower(), re.IGNORECASE)
    return [p for p in palabras if p not in _PALABRAS_VACIAS and len(p) > 2]


def _es_recapitulacion(frase: str, mensaje_usuario: str) -> bool:
    de_eldric = _contenido(frase)
    if len(de_eldric) < PALABRAS_MINIMO:
        return False
    del_usuario = set(_contenido(mensaje_usuario))
    if not del_usuario:
        return False
    repetidas = [p for p in de_eldric if p in del_usuario]
    nuevas = len(de_eldric) - len(repetidas)
    return (len(repetidas) / len(de_eldric)) >= SOLAPE_MINIMO and nuevas <= NUEVAS_MAXIMO


def limpiar_respuesta(texto: str, mensaje_usuario: str = "") -> Tuple[str, List[str]]:
    """Return the cleaned reply and the list of rules that fired.

    The reply is only ever shortened at the front, never rewritten. If any rule would
    leave too little text, or a dangling reference, nothing is changed.
    """
    if not texto or not texto.strip():
        return texto, []

    original = texto
    aplicadas: List[str] = []
    trabajo = texto.lstrip()

    if _es_rail_de_seguridad(trabajo):
        return original, []

    # R2 first: "Entendido: a, b, c." is a whole sentence of recap.
    coincidencia = _R2.match(trabajo)
    if coincidencia:
        sin_marcador = trabajo[coincidencia.end():]
        primera, resto = _cortar_primera_frase(sin_marcador)
        if resto.strip() and len(resto.strip()) >= MINIMO_RESTANTE and not _empieza_por_anaforico(resto):
            trabajo = _capitalizar(resto)
            aplicadas.append("resumen-de-apertura")
        elif len(sin_marcador.strip()) >= MINIMO_RESTANTE:
            trabajo = _capitalizar(sin_marcador)
            aplicadas.append("marcador-de-apertura")

    coincidencia = _R1.match(trabajo)
    if coincidencia:
        resto = trabajo[coincidencia.end():]
        if len(resto.strip()) >= MINIMO_RESTANTE and not _empieza_por_anaforico(resto):
            trabajo = _capitalizar(resto)
            aplicadas.append("marcador-de-apertura")

    coincidencia = _R3.match(trabajo)
    if coincidencia:
        resto = trabajo[coincidencia.end():]
        if len(resto.strip()) >= MINIMO_RESTANTE and not _empieza_por_anaforico(resto):
            trabajo = _capitalizar(resto)
            aplicadas.append("conector-de-recapitulacion")

    # R4: the first sentence just hands the user their own facts back.
    if mensaje_usuario:
        primera, resto = _cortar_primera_frase(trabajo)
        if (
            resto.strip()
            and len(resto.strip()) >= MINIMO_RESTANTE
            and not _empieza_por_anaforico(resto)
            and _es_recapitulacion(primera, mensaje_usuario)
        ):
            trabajo = _capitalizar(resto)
            aplicadas.append("recapitulacion-sin-marcador")

    limpio = trabajo.strip()
    if not limpio or len(limpio) < MINIMO_RESTANTE:
        return original, []
    return limpio, aplicadas
