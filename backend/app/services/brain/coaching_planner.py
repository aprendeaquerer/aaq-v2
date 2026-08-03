"""Build and persist Eldric's private coaching-session roadmap."""

import json
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coaching_plan import CoachingPlan
from app.services.ai.base import AIProvider
from app.services.brain.conversation_flow import (
    componer_bloque_movimiento,
    decidir_movimiento,
)
from app.services.brain.types import BrainContext


PLANNER_PROMPT = """
Eres el planificador interno de Eldric, un coach de relaciones. No hablas con el usuario.
Tu unica salida es un objeto JSON valido, sin markdown ni texto alrededor.

En cada turno:
1. Lee el mensaje nuevo dentro de la conversacion.
2. Clasifica tipo_turno: "crisis", "duda", "descarga", "situacion" o "seguimiento".
3. Clasifica drift: "profundiza", "rodeo", "objetivo_nuevo", "corrige" o "nada".
4. Rellena la ficha de contexto de seis huecos con lo que ya sabes.
5. Mantiene una pila con un unico objetivo "activo"; los demas quedan "aparcado" o "cerrado".
6. Formula hipotesis apoyadas en hechos y en el KNOWLEDGE disponible.
7. Decide el siguiente movimiento de la sesion y si toca ensenar un concepto.

TIPO DE TURNO
- "crisis": senal de suicidio, autolesion, violencia, agresion sexual o menor en peligro.
- "duda": pregunta concreta e informativa. No abre bucle de coaching.
- "descarga": relato emocional sin peticion de solucion.
- "situacion": problema concreto con hechos. Abre el bucle completo.
- "seguimiento": vuelve despues de un paso acordado en un turno anterior.

FICHA DE CONTEXTO (seis huecos fijos)
- "hecho": secuencia observable, que paso y en que orden.
- "frecuencia": cuantas veces, desde cuando.
- "conducta_propia": que hace el usuario cuando pasa.
- "intentos": que ha probado ya y con que resultado.
- "objetivo": que quiere que sea distinto.
- "supuesto": lo que da por hecho sin verificar, sobre todo sobre la otra persona.
- Cada hueco tiene status "pending", "filled" o "skipped", y "valor" con lo sabido.
- Marca "filled" solo con datos observables que el usuario haya dado o que consten en perfil o memoria.
- Marca "skipped" tras 3 turnos preguntando sin respuesta, o si ese dato no cambiaria la respuesta.
- "supuesto" se marca "pending" en cuanto el usuario afirme algo sobre la otra persona como si fuera un hecho.

BANDERAS
- "resistencia": true si el usuario rechaza o ignora la lectura o el paso que Eldric acaba de dar.
- "hecho_nuevo": true si aparece un hecho que cambia la lectura ya dada.

REGLAS
- Un rodeo aporta contexto o desahogo, pero no crea un objetivo nuevo.
- Solo crea objetivo nuevo ante una pregunta o queja sobre un tema realmente distinto.
- Cierra un objetivo solo cuando el usuario dice que esta resuelto o que lo deja.
- La confianza empieza en 0.3 o menos con una sola frase, sube con ejemplos o confirmacion y baja al corregir.
- Cada hipotesis lleva "lectura", "a_favor" y "en_contra". "en_contra" es obligatorio y no puede quedar vacio; si aun no hay evidencia contraria, indica que falta evidencia para discriminar la hipotesis. No diagnostiques ni presentes motivos ajenos como hechos.
- Los slots contienen SOLO datos observables del caso que cambiarian la respuesta. Nunca preguntes al usuario por causas, motivos, pensamientos o emociones de otra persona. Tampoco le pidas que identifique el patron: esa lectura la hace Eldric con el knowledge.
- Antes de dejar un slot pendiente, comprueba perfil y memoria. Tras 3 turnos sin respuesta pasa a "skipped". Congela slots de objetivos aparcados.
- Cada objetivo tiene un curriculum de 2 a 5 conceptos respaldados por los titulos/topics del KNOWLEDGE disponible. No inventes fuentes.
- Usa el PLAN ACTUAL y los ultimos mensajes para mantener el estado del curriculum: marca "ensenado" cuando Eldric ya entrego el concepto y "rebotado" si el usuario lo ignoro o rechazo dos veces. No vuelvas a proponer conceptos ya ensenados.
- teach solo puede contener el siguiente concepto si confianza > 0.7, sus slots requeridos estan filled y el usuario no esta en descarga emocional. Cuando exista lleva concepto, fuente, aterrizaje y practica. Si no, teach es null.
- next_move es una sola frase concreta que dirige el siguiente turno. No delegues en el usuario como proceder.
- El roadmap es interno: Eldric conduce una etapa cada vez, sin recitar fases ni pedir permiso para continuar.

Devuelve esta forma:
{
  "tipo_turno": "crisis | duda | descarga | situacion | seguimiento",
  "drift": "profundiza | rodeo | objetivo_nuevo | corrige | nada",
  "resistencia": false,
  "hecho_nuevo": false,
  "ficha": {
    "hecho": {"status": "pending | filled | skipped", "valor": null},
    "frecuencia": {"status": "pending | filled | skipped", "valor": null},
    "conducta_propia": {"status": "pending | filled | skipped", "valor": null},
    "intentos": {"status": "pending | filled | skipped", "valor": null},
    "objetivo": {"status": "pending | filled | skipped", "valor": null},
    "supuesto": {"status": "pending | filled | skipped", "valor": null}
  },
  "tema_de_fondo": "string | null",
  "objetivos": [{
    "id": "obj_1",
    "estado": "activo | aparcado | cerrado",
    "objetivo": "string",
    "tipo": "entender | saber_hacer | decidir | desahogo",
    "confianza": 0.0,
    "enunciado": false,
    "hipotesis": {"lectura": "string", "a_favor": [], "en_contra": []},
    "emociones_no_nombradas": [],
    "knowledge_query": "string",
    "slots": [{"key": "string", "pregunta": "string", "por_que": "string", "status": "pending | filled | skipped", "valor": null, "turnos_pendiente": 0}],
    "curriculum": [{"concepto": "string", "fuente": "article_id", "requiere": [], "status": "pendiente | ensenado | rebotado"}]
  }],
  "teach": {"concepto": "string", "fuente": "article_id", "aterrizaje": "string", "practica": "string"},
  "next_move": "string"
}
""".strip()


async def update_coaching_plan(
    db: AsyncSession,
    user_id: str,
    message: str,
    history: List[Dict[str, str]],
    profile_context: List[str],
    brain_context: BrainContext,
    ai: AIProvider,
) -> Dict[str, object]:
    stored = await _get_stored_plan(db, user_id)
    planner_input = _build_planner_input(
        stored=stored,
        message=message,
        history=history,
        profile_context=profile_context,
        brain_context=brain_context,
    )
    raw = await ai.chat(
        system_prompt=PLANNER_PROMPT,
        messages=[{"role": "user", "content": planner_input}],
        temperature=0.1,
        max_tokens=1800,
    )
    plan = _parse_plan(raw)
    plan["conversacion"] = _advance_conversation(stored, plan)
    await _store_plan(db, user_id, plan)
    return plan


def _advance_conversation(
    stored: Optional[Dict[str, object]],
    plan: Dict[str, object],
) -> Dict[str, object]:
    """Run the deterministic move director on top of what the planner reported."""

    previo = stored.get("conversacion") if isinstance(stored, dict) else None
    _, estado = decidir_movimiento(
        previo=previo if isinstance(previo, dict) else None,
        tipo_turno=plan.get("tipo_turno"),
        ficha=plan.get("ficha"),
        drift=plan.get("drift"),
        resistencia=bool(plan.get("resistencia")),
        hecho_nuevo=bool(plan.get("hecho_nuevo")),
    )
    return estado


def compose_session_prompt(base_prompt: str, plan: Optional[Dict[str, object]]) -> str:
    if not plan:
        return base_prompt

    # The move director applies to every turn, including the ones with no active
    # objective (a plain question, a first venting message).
    prompt = base_prompt + componer_bloque_movimiento(plan.get("conversacion"))

    active = next(
        (item for item in plan.get("objetivos", []) if isinstance(item, dict) and item.get("estado") == "activo"),
        None,
    )
    if not active:
        return prompt
    filled = [
        f"{slot.get('key')} = {slot.get('valor')}"
        for slot in active.get("slots", [])
        if isinstance(slot, dict) and slot.get("status") == "filled"
    ]
    pending = next(
        (slot for slot in active.get("slots", []) if isinstance(slot, dict) and slot.get("status") == "pending"),
        None,
    )
    session = [
        "\n\nSESION EN CURSO (interna: no la cites, no muestres el JSON y no recites las fases)",
        f"Objetivo activo: {active.get('objetivo', '')}",
        f"Confianza: {active.get('confianza', 0)}. Enunciado: {'si' if active.get('enunciado') else 'no'}.",
        f"Tema de fondo: {plan.get('tema_de_fondo') or 'ninguno'}",
        f"Lo que ya sabes: {'; '.join(filled) if filled else 'ningun slot critico lleno'}",
        f"Lo que falta: {pending.get('pregunta') if pending else 'nada critico'}",
        f"Contenido del siguiente movimiento: {plan.get('next_move', '')}",
        "Conduce ese contenido ahora, con la forma que marca la CONDUCCION DE LA CONVERSACION.",
        "Si las dos se contradicen, manda la CONDUCCION DE LA CONVERSACION.",
        "No preguntes al usuario como quiere seguir ni le pidas permiso para explorar el siguiente paso.",
    ]
    if active.get("confianza", 0) > 0.7 and not active.get("enunciado"):
        session.append("Enuncia en una frase afirmativa hacia donde vais en esta sesion; no pidas confirmacion.")
    teach = plan.get("teach")
    if isinstance(teach, dict):
        session.extend([
            "CONCEPTO A ENSENAR EN ESTE TURNO",
            f"Concepto: {teach.get('concepto', '')}",
            f"Fuente interna: {teach.get('fuente', '')}",
            f"Aterrizaje: {teach.get('aterrizaje', '')}",
            f"Practica opcional: {teach.get('practica', '')}",
            "Entregalo en 2-3 frases llanas, aterrizalo en su caso y ofrece una sola practica. No cites libro ni autor salvo que lo pidan.",
        ])
    return prompt + "\n".join(session)


async def delete_coaching_plan(db: AsyncSession, user_id: str) -> None:
    stored = await db.scalar(select(CoachingPlan).where(CoachingPlan.user_id == user_id))
    if stored:
        await db.delete(stored)


async def _get_stored_plan(db: AsyncSession, user_id: str) -> Optional[Dict[str, object]]:
    stored = await db.scalar(select(CoachingPlan).where(CoachingPlan.user_id == user_id))
    if not stored:
        return None
    try:
        parsed = json.loads(stored.plan_json)
    except (TypeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


async def _store_plan(db: AsyncSession, user_id: str, plan: Dict[str, object]) -> None:
    stored = await db.scalar(select(CoachingPlan).where(CoachingPlan.user_id == user_id))
    payload = json.dumps(plan, ensure_ascii=False)
    if stored:
        stored.plan_json = payload
    else:
        db.add(CoachingPlan(user_id=user_id, plan_json=payload))
    await db.commit()


def _build_planner_input(
    stored: Optional[Dict[str, object]],
    message: str,
    history: List[Dict[str, str]],
    profile_context: List[str],
    brain_context: BrainContext,
) -> str:
    knowledge = [
        {"article_id": chunk.article_id, "title": chunk.title, "topics": chunk.topics}
        for chunk in brain_context.knowledge_chunks
    ]
    memories = [
        memory.get("curated_summary") or memory.get("summary")
        for memory in brain_context.user_memories
    ]
    return "\n".join([
        f"PLAN ACTUAL: {json.dumps(stored, ensure_ascii=False) if stored else 'ninguno'}",
        f"PERFIL: {json.dumps(profile_context, ensure_ascii=False)}",
        f"MEMORIA: {json.dumps(memories, ensure_ascii=False)}",
        f"KNOWLEDGE DISPONIBLE: {json.dumps(knowledge, ensure_ascii=False)}",
        f"ULTIMOS MENSAJES: {json.dumps(history[-6:], ensure_ascii=False)}",
        f"MENSAJE NUEVO DEL USUARIO: {message}",
    ])


def _parse_plan(raw: str) -> Dict[str, object]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0].strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("objetivos"), list):
        raise ValueError("Planner response is missing objetivos")
    if not isinstance(parsed.get("next_move"), str):
        raise ValueError("Planner response is missing next_move")
    return parsed
