"""Tests for the deterministic conversation move director."""

from app.services.brain.conversation_flow import (
    componer_bloque_movimiento,
    decidir_movimiento,
    estado_inicial,
    siguiente_hueco,
    umbral_explicar,
    umbral_proponer,
)


def ficha(**estados):
    base = {
        "hecho": "pending",
        "frecuencia": "pending",
        "conducta_propia": "pending",
        "intentos": "pending",
        "objetivo": "pending",
        "supuesto": "pending",
    }
    base.update(estados)
    return base


def avanzar(estado, tipo_turno="situacion", **kwargs):
    return decidir_movimiento(previo=estado, tipo_turno=tipo_turno, **kwargs)


# --- thresholds -------------------------------------------------------------


def test_umbral_explicar_needs_a_fact_and_two_more_observables():
    assert not umbral_explicar(ficha(hecho="filled", objetivo="filled"))
    assert umbral_explicar(ficha(hecho="filled", objetivo="filled", supuesto="filled"))
    assert not umbral_explicar(ficha(objetivo="filled", supuesto="filled", frecuencia="filled"))


def test_umbral_proponer_needs_attempts():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    assert not umbral_proponer(llena)
    assert umbral_proponer({**llena, "intentos": "filled"})
    assert umbral_proponer({**llena, "intentos": "skipped"})


# --- curiosity engine -------------------------------------------------------


def test_first_hole_asked_is_the_fact():
    assert siguiente_hueco(ficha()) == "hecho"


def test_holes_that_need_a_fact_are_not_asked_first():
    # With no concrete fact, frequency / own behaviour / attempts make no sense.
    hueco = siguiente_hueco(ficha(objetivo="filled", supuesto="filled"))
    assert hueco not in ("frecuencia", "conducta_propia", "intentos")


def test_no_hole_left_means_no_question():
    completa = {key: "filled" for key in ficha()}
    assert siguiente_hueco(completa) is None


# --- the loop ---------------------------------------------------------------


def test_situation_starts_by_gathering():
    movimiento, _ = avanzar(estado_inicial(), ficha=ficha())
    assert movimiento == "recoger"


def test_debt_of_value_forces_a_reading_after_two_gathering_turns():
    estado = estado_inicial()
    for _ in range(2):
        movimiento, estado = avanzar(estado, ficha=ficha())
        assert movimiento == "recoger"
    # Third turn with an still-empty card: Eldric must deliver a partial reading.
    movimiento, estado = avanzar(estado, ficha=ficha())
    assert movimiento == "explicar"


def test_threshold_reached_moves_to_explaining_without_waiting():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    movimiento, _ = avanzar(estado_inicial(), ficha=llena)
    assert movimiento == "explicar"


def test_debt_of_context_blocks_the_step_until_attempts_have_been_asked_for():
    """No action step before asking what was already tried.

    The engine asks twice; if the user never answers it stops treating the hole as a
    blocker, otherwise a silent user could never be given a step at all.
    """
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    estado = estado_inicial()
    movimiento, estado = avanzar(estado, ficha=llena)
    assert movimiento == "explicar"

    # Reading given, attempts unknown: it gathers, and asks precisely for attempts.
    movimiento, estado = avanzar(estado, ficha=llena)
    assert movimiento == "recoger"
    assert estado["hueco_pendiente"] == "intentos"
    assert estado["paso_dado"] is False

    # It cannot jump to a step off the back of a single unanswered question.
    movimiento, estado = avanzar(estado, ficha=llena)
    assert movimiento != "resolver"


def test_full_loop_reaches_the_step():
    completa = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    secuencia = []
    for _ in range(3):
        movimiento, estado = avanzar(estado, ficha=completa)
        secuencia.append(movimiento)
    assert secuencia == ["explicar", "proponer", "resolver"]


def test_reparto_is_tracked():
    completa = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    for _ in range(3):
        _, estado = avanzar(estado, ficha=completa)
    assert estado["reparto"] == {"recoger": 0, "explicar": 1, "proponer": 1, "resolver": 1}


# --- going back and resistance ---------------------------------------------


def test_new_objective_reopens_the_loop():
    completa = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    for _ in range(3):
        _, estado = avanzar(estado, ficha=completa)
    assert estado["paso_dado"] is True
    movimiento, estado = avanzar(estado, ficha=ficha(), drift="objetivo_nuevo")
    assert movimiento == "recoger"
    assert estado["lectura_dada"] is False


def test_a_new_fact_invalidates_the_reading():
    completa = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    movimiento, estado = avanzar(estado, ficha=completa)
    assert movimiento == "explicar"
    movimiento, estado = avanzar(estado, ficha=completa, hecho_nuevo=True)
    assert movimiento == "explicar"


def test_two_refusals_change_the_move_instead_of_repeating():
    completa = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    movimiento, estado = avanzar(estado, ficha=completa)
    assert movimiento == "explicar"
    # Two refusals in a row while the loop would keep proposing the same move.
    movimiento, estado = avanzar(estado, ficha=completa, resistencia=True, drift="corrige")
    movimiento, estado = avanzar(estado, ficha=completa, resistencia=True, drift="corrige")
    assert movimiento != "explicar"


# --- turn types -------------------------------------------------------------


def test_a_plain_question_does_not_open_the_loop():
    movimiento, estado = avanzar(estado_inicial(), tipo_turno="duda", ficha=ficha())
    assert movimiento == "duda"
    assert estado["lectura_dada"] is False


def test_venting_listens_two_turns_then_delivers_even_with_an_empty_card():
    """Regression for a live conversation on 2026-08-10: three near-identical gathering
    questions in a row to a user who said "ayer lo deje con mi novio" and then "fatal".
    Venting used to get a third listening turn when the card was thin; now the debt of
    value applies the same as everywhere else — two turns listening, then a reading,
    partial if it has to be."""
    estado = estado_inicial()
    for _ in range(2):
        movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=ficha())
        assert movimiento == "recoger"
    movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=ficha())
    assert movimiento == "explicar"


def test_venting_delivers_once_there_is_enough_context():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    estado = estado_inicial()
    movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=llena)
    assert movimiento == "recoger"
    movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=llena)
    assert movimiento == "recoger"
    movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=llena)
    assert movimiento == "explicar"


def test_crisis_short_circuits_everything():
    movimiento, _ = avanzar(estado_inicial(), tipo_turno="crisis", ficha=ficha())
    assert movimiento == "crisis"


def test_follow_up_is_its_own_move():
    movimiento, _ = avanzar(estado_inicial(), tipo_turno="seguimiento", ficha=ficha())
    assert movimiento == "seguimiento"


# --- prompt block -----------------------------------------------------------


def test_gathering_block_points_the_final_question_at_the_pending_hole():
    _, estado = avanzar(estado_inicial(), ficha=ficha())
    bloque = componer_bloque_movimiento(estado)
    assert "RECOGER" in bloque
    assert "Que paso exactamente?" in bloque


def test_explaining_block_teaches_the_reading_and_checks_it_with_the_final_question():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    _, estado = avanzar(estado_inicial(), ficha=llena)
    bloque = componer_bloque_movimiento(estado)
    assert "EXPLICAR" in bloque
    assert "NOMBRA EL PATRON" in bloque
    assert "confirmaria o la desmentiria" in bloque
    assert "Que paso exactamente?" not in bloque


def test_every_move_block_carries_the_common_rules():
    """The three failures the QA run counted most: opening with a summary, more than
    one question, and blending two moves in one answer."""
    from app.services.brain.conversation_flow import _INSTRUCCIONES

    for movimiento in _INSTRUCCIONES:
        bloque = componer_bloque_movimiento({"movimiento": movimiento, "ficha": ficha()})
        assert "resumiendo" in bloque, movimiento
        assert "SOLO este movimiento" in bloque, movimiento
        assert "no haya contado" in bloque, movimiento
        # "Entendido: ..." opened 43 of the 90 conversations in the validation run.
        assert "APERTURAS PROHIBIDAS" in bloque, movimiento
        assert "Entendido" in bloque, movimiento


def test_every_move_teaches_and_ends_with_one_excellent_question():
    """Owner's spec 2026-08-11: every reply teaches something from the book and always
    ends with a single excellent question — that question is what keeps the user
    writing. The crisis rail is the only exception."""
    for movimiento in ("recoger", "explicar", "proponer", "resolver", "duda", "seguimiento"):
        bloque = componer_bloque_movimiento({"movimiento": movimiento, "ficha": ficha()})
        assert "TERMINA SIEMPRE con UNA pregunta" in bloque, movimiento
        assert "PREGUNTA EXCELENTE" in bloque, movimiento
        assert "UNA sola interrogacion" in bloque, movimiento
        assert "ensenanza" in bloque.lower(), movimiento


def test_the_reply_shape_leans_on_what_is_known_about_the_user():
    bloque = componer_bloque_movimiento({"movimiento": "recoger", "ficha": ficha()})
    assert "CONTEXTO DEL USUARIO" in bloque
    assert "cuanto mas sabes de esta persona" in bloque


def test_the_crisis_rail_does_not_get_the_question_requirement():
    bloque = componer_bloque_movimiento({"movimiento": "crisis", "ficha": ficha()})
    assert "TERMINA SIEMPRE con UNA pregunta" not in bloque


def test_crisis_block_stops_the_coaching():
    bloque = componer_bloque_movimiento({"movimiento": "crisis", "ficha": ficha()})
    assert "Corta el coaching" in bloque
    assert "recurso concreto" in bloque


def test_block_is_empty_without_state():
    assert componer_bloque_movimiento(None) == ""
    assert componer_bloque_movimiento({}) == ""


# --- traps found by the 300-conversation synthetic run --------------------------


def test_a_planner_reporting_new_facts_every_turn_cannot_pin_the_loop_to_explaining():
    """The bug the QA run surfaced: hecho_nuevo reset the reading on every turn, so
    Eldric explained forever and never reached a step."""
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    estado = estado_inicial()
    movimientos = []
    for _ in range(6):
        movimiento, estado = avanzar(estado, ficha=llena, hecho_nuevo=True)
        movimientos.append(movimiento)
    assert movimientos.count("explicar") <= 3
    assert "proponer" in movimientos


def test_no_move_runs_three_turns_in_a_row():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    movimientos = []
    for _ in range(8):
        movimiento, estado = avanzar(estado, ficha=llena, drift="corrige")
        movimientos.append(movimiento)
    for a, b, c in zip(movimientos, movimientos[1:], movimientos[2:]):
        assert not (a == b == c), f"tres turnos seguidos de {a}: {movimientos}"


def test_reset_drifts_cannot_defeat_the_anti_repeat_rule():
    """The trace that made the third run collapse to 0.7% action steps: the planner
    emitted "corrige" and "objetivo_nuevo" on alternate turns, and every reset cleared
    the counter that is supposed to stop a move repeating."""
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    drifts = ["nada", "profundiza", "profundiza", "corrige", "objetivo_nuevo",
              "corrige", "objetivo_nuevo", "corrige"]
    movimientos = []
    for d in drifts:
        movimiento, estado = avanzar(estado, ficha=llena, drift=d)
        movimientos.append(movimiento)
    for a, b, c in zip(movimientos, movimientos[1:], movimientos[2:]):
        assert not (a == b == c), f"tres turnos seguidos de {a}: {movimientos}"
    assert "proponer" in movimientos, movimientos


def test_a_planner_that_corrects_every_turn_still_reaches_a_step():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    movimientos = []
    for _ in range(8):
        movimiento, estado = avanzar(estado, ficha=llena, drift="corrige")
        movimientos.append(movimiento)
    assert "resolver" in movimientos, movimientos


def test_attempts_hole_jumps_the_queue_once_a_reading_is_given():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    estado = estado_inicial()
    _, estado = avanzar(estado, ficha=llena)
    assert estado["lectura_dada"] is True
    _, estado = avanzar(estado, ficha=llena)
    assert estado["hueco_pendiente"] == "intentos"


def test_a_user_who_never_says_what_they_tried_still_gets_a_step():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    estado = estado_inicial()
    movimientos = []
    for _ in range(6):
        movimiento, estado = avanzar(estado, ficha=llena)
        movimientos.append(movimiento)
    assert "resolver" in movimientos, movimientos


def test_session_prompt_injects_the_move_even_without_an_active_objective():
    from app.services.brain.coaching_planner import compose_session_prompt

    _, estado = avanzar(estado_inicial(), ficha=ficha())
    prompt = compose_session_prompt("BASE", {"objetivos": [], "conversacion": estado})
    assert "BASE" in prompt
    assert "RECOGER" in prompt


def test_session_prompt_survives_a_plan_without_conversation_state():
    from app.services.brain.coaching_planner import compose_session_prompt

    assert compose_session_prompt("BASE", {"objetivos": []}) == "BASE"
    assert compose_session_prompt("BASE", None) == "BASE"


def test_planner_advances_the_state_across_turns():
    from app.services.brain.coaching_planner import _advance_conversation

    plan = {"tipo_turno": "situacion", "drift": "nada", "ficha": ficha()}
    primero = _advance_conversation(None, plan)
    assert primero["movimiento"] == "recoger"
    segundo = _advance_conversation({"conversacion": primero}, plan)
    assert segundo["turnos_recoger_seguidos"] == 2


def test_malformed_state_and_card_do_not_crash():
    movimiento, estado = decidir_movimiento(
        previo={"reparto": "roto", "turnos_recoger_seguidos": None},
        tipo_turno="loquesea",
        ficha={"hecho": "raro", "inventado": "filled"},
        drift=None,
    )
    assert movimiento == "recoger"
    assert estado["reparto"]["recoger"] == 1


def test_no_move_hands_the_direction_back_to_the_user():
    """Reported from production: Eldric closed with "¿Cómo te gustaría abordar este tema
    con ella?". The next move is Eldric's decision, never the user's."""
    from app.services.brain.conversation_flow import _INSTRUCCIONES

    for movimiento in _INSTRUCCIONES:
        bloque = componer_bloque_movimiento({"movimiento": movimiento, "ficha": ficha()})
        assert "NUNCA delegues en el usuario" in bloque, movimiento
        assert "como te gustaria abordarlo" in bloque, movimiento


def test_no_move_lets_eldric_read_the_other_person_s_mind():
    from app.services.brain.conversation_flow import _INSTRUCCIONES

    for movimiento in _INSTRUCCIONES:
        bloque = componer_bloque_movimiento({"movimiento": movimiento, "ficha": ficha()})
        assert "No atribuyas a la otra persona" in bloque, movimiento


# --- balance of moves (point 2 of the fourth run: 44% gathering, 4% action) ---


def test_the_goal_is_no_longer_required_to_read_a_pattern():
    """People rarely state a goal, and requiring it stalled the loop in gathering."""
    sin_objetivo = ficha(hecho="filled", frecuencia="filled", conducta_propia="filled")
    assert umbral_explicar(sin_objetivo)
    movimiento, _ = avanzar(estado_inicial(), ficha=sin_objetivo)
    assert movimiento == "explicar"


def test_a_bare_fact_is_still_not_enough():
    assert not umbral_explicar(ficha(hecho="filled"))
    assert not umbral_explicar(ficha(hecho="filled", frecuencia="filled"))


def test_gathering_is_capped_per_objective_not_just_consecutively():
    """Alternating recoger / explicar / recoger kept gathering near half the turns."""
    vacia = ficha()
    estado = estado_inicial()
    movimientos = []
    for _ in range(10):
        movimiento, estado = avanzar(estado, ficha=vacia, drift="corrige")
        movimientos.append(movimiento)
    assert movimientos.count("recoger") <= 4, movimientos


def test_venting_delivers_by_the_third_turn_even_with_an_empty_card():
    estado = estado_inicial()
    movimientos = []
    for _ in range(4):
        movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=ficha())
        movimientos.append(movimiento)
    assert "explicar" in movimientos, movimientos


def test_a_new_objective_gives_back_the_gathering_budget():
    vacia = ficha()
    estado = estado_inicial()
    for _ in range(6):
        _, estado = avanzar(estado, ficha=vacia)
    _, estado = avanzar(estado, ficha=vacia, drift="objetivo_nuevo")
    assert estado["recoger_en_objetivo"] <= 1


def test_a_five_turn_situation_reaches_an_action_step():
    """The shape of a real test conversation: the card fills gradually."""
    fichas = [
        ficha(hecho="filled"),
        ficha(hecho="filled", supuesto="filled"),
        ficha(hecho="filled", supuesto="filled", conducta_propia="filled"),
        ficha(hecho="filled", supuesto="filled", conducta_propia="filled", intentos="filled"),
        ficha(hecho="filled", supuesto="filled", conducta_propia="filled", intentos="filled", objetivo="filled"),
    ]
    estado = estado_inicial()
    movimientos = []
    for f in fichas:
        movimiento, estado = avanzar(estado, ficha=f)
        movimientos.append(movimiento)
    assert "explicar" in movimientos, movimientos
    assert "proponer" in movimientos, movimientos
    assert "resolver" in movimientos, movimientos


def test_venting_that_turns_into_a_request_stops_being_venting():
    """The fifth run had a batch where every turn was labelled "descarga", so the loop
    could never propose anything even with a full card and a reading already given."""
    completa = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    movimientos = []
    for _ in range(5):
        movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=completa)
        movimientos.append(movimiento)
    assert "proponer" in movimientos, movimientos
    assert "resolver" in movimientos, movimientos


def test_venting_with_a_thin_card_still_only_listens():
    estado = estado_inicial()
    movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=ficha(hecho="filled"))
    assert movimiento == "recoger"


def test_two_readings_per_objective_is_the_cap():
    """A planner that keeps correcting must not hold the loop in "explicar"."""
    completa = ficha(hecho="filled", objetivo="filled", supuesto="filled", intentos="filled")
    estado = estado_inicial()
    movimientos = []
    for _ in range(6):
        movimiento, estado = avanzar(estado, ficha=completa, drift="corrige")
        movimientos.append(movimiento)
    assert movimientos.count("explicar") <= 2, movimientos


def test_feelings_questions_are_banned_in_every_move():
    """Live conversation 2026-08-10: "¿Como te sientes desde que dejaste a tu novio?"
    followed one turn later by another feelings probe. Emotions are acknowledged when
    they show up, never extracted by interrogation — the card has no feelings slot."""
    for movimiento in ("recoger", "explicar", "proponer", "resolver", "duda", "seguimiento"):
        bloque = componer_bloque_movimiento({"movimiento": movimiento, "ficha": ficha()})
        assert "PROHIBIDO preguntar por emociones" in bloque, movimiento
        assert "como te sientes" in bloque, movimiento


def test_referring_the_user_to_someone_else_is_banned():
    """Live conversation 2026-08-10: "¿Has intentado hablar con alguien sobre esto?".
    The product IS the place where she is talking about it; the only referral allowed
    is the safety move."""
    for movimiento in ("recoger", "explicar", "proponer", "resolver", "duda", "seguimiento"):
        bloque = componer_bloque_movimiento({"movimiento": movimiento, "ficha": ficha()})
        assert "hablar del tema con otras personas" in bloque, movimiento
    rail = componer_bloque_movimiento({"movimiento": "crisis", "ficha": ficha()})
    assert "orientar a ayuda real es obligatorio" in rail
