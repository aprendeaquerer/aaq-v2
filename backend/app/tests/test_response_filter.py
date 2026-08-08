"""Tests for the opener filter.

Opening by restating the user was the most repeated failure across four QA runs and
never moved with prompt rules. These tests pin what the filter removes and, more
importantly, what it must never touch.
"""

import pytest

from app.services.brain.response_filter import limpiar_respuesta

LARGO = (
    "El primer paso es hablar desde la calma, no desde el colapso, y fijarte en como "
    "responde ella cuando lo planteas asi."
)


# --- what it removes -------------------------------------------------------


def test_bare_marker_is_dropped():
    limpio, reglas = limpiar_respuesta(f"Bien. {LARGO}")
    assert limpio == LARGO
    assert "marcador-de-apertura" in reglas


def test_summary_sentence_after_a_colon_is_dropped_whole():
    """The exact shape reported by the runs: "Entendido: <recap of their facts>"."""
    texto = (
        "Entendido: salian bien, se fue apartando hace dos semanas, le preguntaste y "
        "dijo que esta ocupado. " + LARGO
    )
    limpio, reglas = limpiar_respuesta(texto)
    assert limpio == LARGO
    assert "resumen-de-apertura" in reglas


def test_recap_connector_is_dropped_but_the_content_stays():
    texto = "Entonces la evidencia en persona es que nada cambio, y eso es lo que cuenta aqui de verdad."
    limpio, reglas = limpiar_respuesta(texto)
    assert limpio.startswith("La evidencia en persona")
    assert "conector-de-recapitulacion" in reglas


@pytest.mark.parametrize("apertura", ["Entendido.", "Vale,", "Perfecto.", "De acuerdo,", "Ya veo.", "Ok."])
def test_every_bare_marker_form(apertura):
    limpio, reglas = limpiar_respuesta(f"{apertura} {LARGO}")
    assert reglas
    assert limpio == LARGO


@pytest.mark.parametrize("conector", ["Entonces", "Asi que", "O sea que", "Por lo que dices", "Si te he entendido bien,"])
def test_every_recap_connector_form(conector):
    limpio, reglas = limpiar_respuesta(f"{conector} el problema no es el ritmo sino lo que se activa en ti cuando alguien va en serio.")
    assert reglas
    assert limpio.startswith("El problema")


# --- what it must never touch ----------------------------------------------


def test_a_direct_answer_is_not_an_opener():
    """"Si, es normal" answers a question. Stripping it would break the reply."""
    texto = "Si, es completamente normal. La privacidad y la transparencia no son lo mismo, y conviene separarlas."
    limpio, reglas = limpiar_respuesta(texto)
    assert limpio == texto
    assert reglas == []


@pytest.mark.parametrize("inicio", ["No,", "Exacto.", "Correcto.", "Claro que"])
def test_confirmations_and_denials_are_left_alone(inicio):
    texto = f"{inicio} {LARGO}"
    limpio, _ = limpiar_respuesta(texto)
    assert limpio == texto


def test_the_safety_rail_is_never_touched():
    rail = (
        "Lo que describes es violencia, y tu seguridad es lo primero. No soy un servicio "
        "de emergencia; hay recursos especializados que pueden ayudarte.\n\n"
        "En Espana:\n- Emergencias: 112\n- Atencion a la violencia contra la mujer: 016"
    )
    limpio, reglas = limpiar_respuesta(rail)
    assert limpio == rail
    assert reglas == []


def test_it_does_not_break_a_sentence_that_refers_back():
    """Removing the first sentence here would leave "Eso es el ciclo." dangling."""
    texto = "Entendido: el avisa y tu sigues escribiendo. Eso es el ciclo."
    limpio, _ = limpiar_respuesta(texto)
    assert "Eso es el ciclo" in limpio
    assert limpio.strip() != "Eso es el ciclo."


def test_it_never_leaves_a_stub():
    limpio, reglas = limpiar_respuesta("Entendido. Vale.")
    assert limpio == "Entendido. Vale."
    assert reglas == []


def test_empty_and_whitespace_survive():
    assert limpiar_respuesta("") == ("", [])
    assert limpiar_respuesta("   ")[1] == []


def test_a_normal_reply_is_returned_untouched():
    texto = (
        "Tu patron es claro: cuando baja el contacto, aumentas el tuyo, y cuando eso no "
        "da respuesta, cortas de golpe."
    )
    limpio, reglas = limpiar_respuesta(texto)
    assert limpio == texto
    assert reglas == []


def test_the_filter_only_ever_shortens_from_the_front():
    """Whatever it does, the tail of the reply must survive intact."""
    cola = "Fijate en como responde ella cuando lo planteas asi y cuentamelo la semana que viene."
    for apertura in ("Entendido: te ha dejado en visto tres veces esta semana.", "Bien.", "Entonces"):
        limpio, _ = limpiar_respuesta(f"{apertura} {LARGO} {cola}")
        assert limpio.endswith(cola)


# --- R4: restatement with no marker at all ---------------------------------


def test_a_verbatim_echo_of_the_user_is_dropped():
    """"Tres meses después de nueve años." handed straight back to the user."""
    usuario = "Nos separamos hace tres meses despues de nueve anos. Ahora tengo miedo de confiar."
    respuesta = (
        "Tres meses despues de nueve anos. El miedo a confiar aparece cuando el vinculo "
        "que sostenia tu vida se rompe de golpe y todavia no has visto nada que lo repare."
    )
    limpio, reglas = limpiar_respuesta(respuesta, usuario)
    assert "recapitulacion-sin-marcador" in reglas
    assert limpio.startswith("El miedo a confiar")


def test_a_reading_that_shares_words_with_the_user_is_not_an_echo():
    """It shares vocabulary but contributes a new idea, so it must survive."""
    usuario = "Cuando le escribo y tarda en contestar me pongo fatal y le escribo otra vez."
    respuesta = (
        "Ese doble mensaje es una comprobacion: te calma treinta segundos y refuerza el "
        "ciclo que quieres romper, porque cada vez necesitas comprobar antes."
    )
    limpio, reglas = limpiar_respuesta(respuesta, usuario)
    assert "recapitulacion-sin-marcador" not in reglas
    assert limpio == respuesta


def test_without_the_user_message_r4_never_fires():
    usuario = "Nos separamos hace tres meses despues de nueve anos."
    respuesta = "Tres meses despues de nueve anos. " + LARGO
    assert "recapitulacion-sin-marcador" not in limpiar_respuesta(respuesta)[1]
    assert "recapitulacion-sin-marcador" in limpiar_respuesta(respuesta, usuario)[1]


def test_r4_never_leaves_a_dangling_reference():
    usuario = "Sandra quiere mas intimidad y yo me cierro cuando insiste con eso."
    respuesta = "Sandra quiere mas intimidad. Eso es lo que hace que te cierres cada vez mas."
    limpio, _ = limpiar_respuesta(respuesta, usuario)
    assert limpio == respuesta


# --- R5: reflecting the user's emotional state, in Eldric's own words ------
#
# These openers do not share vocabulary with the user's message, so R4's overlap
# check never catches them. That is exactly the gap R5 exists to close.


def test_estas_sintiendo_opener_is_dropped():
    texto = (
        "Estás sintiendo una gran ansiedad respecto a la relación con tu novio, especialmente "
        "sobre si él está bien o mal contigo. " + LARGO
    )
    limpio, reglas = limpiar_respuesta(texto, "que no quiera seguir conmigo")
    assert limpio == LARGO
    assert "reflejo-emocional-de-apertura" in reglas


def test_tu_emocion_se_centra_en_opener_is_dropped():
    texto = (
        "Tu ansiedad se centra en la preocupación de que tu novio no quiera continuar la relación. "
        "Este tipo de temor puede generar una activación emocional intensa y hacer que te "
        "concentres en sus comportamientos o en la dinámica de la relación."
    )
    limpio, reglas = limpiar_respuesta(texto, "que no quiera seguir conmigo")
    assert limpio.startswith("Este tipo de temor")
    assert "reflejo-emocional-de-apertura" in reglas


def test_up_to_two_chained_reflection_openers_are_dropped():
    """"Estas sintiendo X. Y esta relacionado con Z." chains two reflections before
    any real content arrives."""
    texto = (
        "Estás sintiendo mucho miedo por lo que pueda pasar. Tu miedo tiene que ver con no saber "
        "que va a pasar despues. " + LARGO
    )
    limpio, reglas = limpiar_respuesta(texto, "no se que va a pasar")
    assert limpio == LARGO
    assert "reflejo-emocional-de-apertura" in reglas


@pytest.mark.parametrize("emocion", ["miedo", "tristeza", "culpa", "inseguridad", "frustración"])
def test_every_emotion_word_is_covered(emocion):
    texto = f"Sientes {emocion} por como ha ido todo esto. " + LARGO
    limpio, reglas = limpiar_respuesta(texto)
    assert limpio == LARGO
    assert "reflejo-emocional-de-apertura" in reglas


def test_a_reading_that_names_a_feeling_with_its_cause_is_not_touched():
    """This is the actual job of EXPLICAR: naming the feeling AND why it happens in
    the same sentence. R5 must never eat a real reading."""
    texto = (
        "Tu ansiedad crece porque interpretas su silencio como rechazo, y por eso revisas el "
        "movil cada pocos minutos aunque eso no cambie nada."
    )
    limpio, reglas = limpiar_respuesta(texto, "no me contesta y me agobio")
    assert limpio == texto
    assert reglas == []


def test_naming_a_pattern_without_reflection_vocabulary_is_not_touched():
    texto = (
        "Tu patron es claro: cuando el tarda en responder, tu escribes otra vez, y eso confirma "
        "el mismo ciclo cada semana."
    )
    limpio, reglas = limpiar_respuesta(texto)
    assert limpio == texto
    assert reglas == []


def test_r5_never_leaves_a_dangling_reference():
    texto = "Estás sintiendo mucha rabia por lo ocurrido. Eso es lo que te hace explotar tan rapido."
    limpio, _ = limpiar_respuesta(texto)
    assert limpio == texto
