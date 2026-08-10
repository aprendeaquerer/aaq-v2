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

Only five shapes are removed, and never at the cost of content:

    R1  bare marker + . or ,   -> drop the marker
    R2  bare marker + :        -> drop the whole sentence (it is a summary list)
    R3  restating connector    -> drop the connector
    R4  first sentence is a verbatim echo of the user -> drop that sentence
    R5  first sentence is a reflection of the user's emotional state -> drop that sentence

Anything that would leave a stub, or a sentence starting with a pronoun that refers
back to what was removed, is left untouched. Safety-rail messages are never touched.

Deliberately conservative. Measured on 710 real user->Eldric pairs it changes 5% of
replies and never breaks one, but it only removes about 9% of what the judge flags as
"opens by restating": most of those are paraphrases, not echoes, and cutting a
paraphrase risks cutting a genuine reading.

R5 covers the biggest remaining slice of that gap: "Estas sintiendo ansiedad por..." /
"Tu preocupacion se centra en..." are paraphrases in Eldric's own words, so R4's
overlap check (which compares against the user's vocabulary) never fires on them. R5
instead recognises the *shape* of a reflection-of-feeling opener directly: a subject
naming an emotion, followed by a vague relational verb ("se centra en", "tiene que ver
con", "viene de"...), with no causal reasoning in the same sentence. A sentence that
also explains *why* in the same breath (it contains "porque", "ya que"...) is left
alone, since cutting it would cut a genuine reading, not just a mirror.
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


# --- R5: reflecting the user's emotional state as an opener ----------------
#
# "Nunca abras la respuesta reflejando su estado emocional" is a prompt rule, but the
# QA runs kept showing it anyway: it is the model's single strongest reflex. Unlike
# R4, these openers are Eldric's own paraphrase, not the user's words, so they need
# their own vocabulary and shape rather than an overlap check.

EMOCIONES = (
    "ansiedad", "miedo", "temor", "preocupacion", "preocupación", "tristeza", "angustia",
    "culpa", "enfado", "rabia", "ira", "frustracion", "frustración", "inseguridad",
    "confusion", "confusión", "dolor", "verguenza", "vergüenza", "celos", "estres",
    "estrés", "agobio", "malestar", "inquietud", "nerviosismo", "desconfianza", "soledad",
)

# A relational verb vague enough that naming it adds nothing the user didn't already
# say. A sentence that instead explains a mechanism ("porque...", "cuando...") is not
# matched here — see _CONECTORES_CAUSALES below.
_VERBOS_REFLEXION = (
    "se centra en", "se debe a", "tiene que ver con", "esta relacionada con",
    "está relacionada con", "esta relacionado con", "está relacionado con",
    "viene de", "surge de", "proviene de", "gira en torno a", "es sobre", "va sobre",
)

# If either of these appears in the sentence, it is doing real explanatory work
# alongside naming the feeling, so R5 must not touch it.
_CONECTORES_CAUSALES = ("porque", "ya que", "dado que", "puesto que", "debido a")

_R5_INICIO = re.compile(
    r"^\s*(estás|estas)\s+sinti(e|é)ndo\b"
    r"|^\s*(sientes|notas|percibes)\b.{0,40}?\b(" + _ALTERNATIVA(EMOCIONES) + r")\b"
    r"|^\s*(tu|su|esa|ese|esta|este)\s+(\w+\s+){0,2}(" + _ALTERNATIVA(EMOCIONES) + r")\b"
    r".{0,60}?\b(" + _ALTERNATIVA(_VERBOS_REFLEXION) + r")\b",
    re.IGNORECASE,
)

# Reflection openers rarely arrive alone: "Estas sintiendo X. Y es Z." often chains two
# in a row. Bounded so a genuine multi-sentence reading can never be eaten.
_R5_MAX_FRASES = 2


# --- R6: the empathic echo ---------------------------------------------------
#
# A live conversation on 2026-08-10 showed the two shapes everything above misses:
#
#     "Entiendo que dejaste a tu novio. ¿Como te sientes...?"
#     "Te sientes fatal tras haber dejado la relacion. ¿Que ha pasado...?"
#
# R1 needs punctuation right after the marker ("Entiendo."), so "Entiendo que..."
# slides past. R5 anchors on "sientes/notas" at the very start and on a noun from
# EMOCIONES, so "Te sientes fatal..." (pronoun first, adjective feeling) never fires.
# Both are pure mirror: they hand the user her own words back and delay the actual
# move. The causal guard from R5 applies here too — "Te sientes asi porque..." is a
# reading doing real work and must not be cut.

_R6_ECO = re.compile(
    r"^\s*(entiendo|comprendo|veo|imagino|se|sé)\s+que\b"
    r"|^\s*te\s+(sientes|encuentras|noto|veo)\b",
    re.IGNORECASE,
)

# Unlike the other rules, what remains after cutting an echo is often just the
# question — and a bare question is a complete gathering turn, not a stub.
_MINIMO_RESTANTE_R6 = 25


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


def _es_reflejo_emocional(frase: str) -> bool:
    if not _R5_INICIO.match(frase):
        return False
    baja = frase.lower()
    return not any(conector in baja for conector in _CONECTORES_CAUSALES)


def _quitar_reflejos_emocionales(texto: str) -> Tuple[str, bool]:
    """Strip up to `_R5_MAX_FRASES` leading sentences that only mirror the user's
    feeling. Stops as soon as a sentence does not match, leaves too little behind,
    or would dangle a reference — never eats a genuine reading."""
    trabajo = texto
    aplicado = False
    for _ in range(_R5_MAX_FRASES):
        primera, resto = _cortar_primera_frase(trabajo)
        if not (
            resto.strip()
            and len(resto.strip()) >= MINIMO_RESTANTE
            and not _empieza_por_anaforico(resto)
            and _es_reflejo_emocional(primera)
        ):
            break
        trabajo = _capitalizar(resto)
        aplicado = True
    return trabajo, aplicado


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

    # R5: the opening sentence(s) just mirror the user's feeling back, in Eldric's own
    # words. Runs before R4 because it targets the paraphrase R4 cannot see.
    trabajo, aplicado_r5 = _quitar_reflejos_emocionales(trabajo)
    if aplicado_r5:
        aplicadas.append("reflejo-emocional-de-apertura")

    # R6: the empathic echo ("Entiendo que...", "Te sientes fatal tras..."). Same
    # causal guard as R5: a sentence that explains why is a reading, not an echo.
    primera, resto = _cortar_primera_frase(trabajo)
    if (
        resto.strip()
        and len(resto.strip()) >= _MINIMO_RESTANTE_R6
        and not _empieza_por_anaforico(resto)
        and _R6_ECO.match(primera)
        and not any(c in primera.lower() for c in _CONECTORES_CAUSALES)
    ):
        trabajo = _capitalizar(resto)
        aplicadas.append("eco-empatico-de-apertura")

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
    minimo_final = _MINIMO_RESTANTE_R6 if "eco-empatico-de-apertura" in aplicadas else MINIMO_RESTANTE
    if not limpio or len(limpio) < minimo_final:
        return original, []
    return limpio, aplicadas
