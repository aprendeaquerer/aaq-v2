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


def test_umbral_explicar_needs_fact_goal_and_one_more():
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


def test_venting_stays_in_gathering_while_the_card_is_empty():
    estado = estado_inicial()
    for _ in range(3):
        movimiento, estado = avanzar(estado, tipo_turno="descarga", ficha=ficha())
        assert movimiento == "recoger"


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


def test_gathering_block_carries_exactly_one_question():
    _, estado = avanzar(estado_inicial(), ficha=ficha())
    bloque = componer_bloque_movimiento(estado)
    assert "RECOGER" in bloque
    assert "Que paso exactamente?" in bloque


def test_explaining_block_forbids_questions():
    llena = ficha(hecho="filled", objetivo="filled", supuesto="filled")
    _, estado = avanzar(estado_inicial(), ficha=llena)
    bloque = componer_bloque_movimiento(estado)
    assert "EXPLICAR" in bloque
    assert "PROHIBIDO preguntar" in bloque
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


def test_moves_that_deliver_forbid_every_question_mark():
    from app.services.brain.conversation_flow import _INSTRUCCIONES

    for movimiento in ("explicar", "proponer", "resolver"):
        bloque = componer_bloque_movimiento({"movimiento": movimiento, "ficha": ficha()})
        assert "CERO signos de interrogacion" in bloque, movimiento


def test_gathering_moves_cap_the_question_count():
    for movimiento in ("recoger", "seguimiento"):
        bloque = componer_bloque_movimiento({"movimiento": movimiento, "ficha": ficha()})
        assert "UN solo signo de interrogacion" in bloque, movimiento


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
