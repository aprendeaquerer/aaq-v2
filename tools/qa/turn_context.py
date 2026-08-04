#!/usr/bin/env python3
"""Compose the real Eldric system prompt for one synthetic QA turn.

This is what makes the offline run faithful instead of a role-play guess. Every
deterministic layer of production runs for real here:

- the shipped Spanish prompt from `app.services.ai.prompts`
- the real knowledge retrieval over `aaq_libro_chunks.jsonl`
- the real move engine from `app.services.brain.conversation_flow`
- the real prompt composition from `app.services.brain.prompt_composer`

Only the LLM calls happen outside: the caller plays the planner, Eldric and the
user, and feeds each turn back in.

Usage (one call per turn):

    # start a conversation
    python3 tools/qa/turn_context.py --conv runs/qa-001.json --init '<persona json>'

    # each turn: hand in the previous Eldric reply, the new user message and the
    # planner output, get back the system prompt for this turn
    python3 tools/qa/turn_context.py --conv runs/qa-001.json \
        --prev-eldric "..." --user "..." --planner '<planner json>'
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import safety  # noqa: E402
from app.services.ai.prompts import get_eldric_prompt  # noqa: E402
from app.services.brain.conversation_flow import decidir_movimiento  # noqa: E402
from app.services.brain.knowledge_brain import retrieve_knowledge  # noqa: E402
from app.services.brain.prompt_composer import compose_brain_prompt  # noqa: E402
from app.services.brain.types import BrainContext  # noqa: E402


# In the first 300-conversation run, 75 transcripts came back unusable: agents wrote
# placeholder text ("X", "dummy", "Respuesta de Eldric."), repeated the previous turn
# verbatim, or edited the JSON by hand with invented role names. The harness now
# rejects all of that at the door instead of poisoning the report.
PLACEHOLDERS = re.compile(
    r"^\s*(x|a|\.|dummy|answer|test|todo|placeholder|respuesta de eldric\.?|"
    r"mensaje del usuario\.?|<[^>]*>)\s*$",
    re.IGNORECASE,
)
MIN_CARACTERES = 25


def _validar_texto(texto: str, quien: str, previo: Optional[str] = None) -> str:
    limpio = (texto or "").strip()
    if not limpio:
        raise SystemExit(f"ERROR: el turno de {quien} viene vacio.")
    if PLACEHOLDERS.match(limpio):
        raise SystemExit(
            f"ERROR: el turno de {quien} es un placeholder ({limpio!r}). "
            "Escribe el mensaje de verdad; el arnes no lo acepta."
        )
    if len(limpio) < MIN_CARACTERES:
        raise SystemExit(
            f"ERROR: el turno de {quien} tiene {len(limpio)} caracteres, "
            f"menos del minimo de {MIN_CARACTERES}. Escribelo entero."
        )
    if previo and limpio == previo.strip():
        raise SystemExit(
            f"ERROR: el turno de {quien} es identico al anterior. "
            "Si el usuario ha aportado algo nuevo, la respuesta tiene que cambiar."
        )
    return limpio


def _load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"No existe la conversacion {path}. Usa --init primero.")
    conv = json.loads(path.read_text())
    roles = {t.get("role") for t in conv.get("turns", [])}
    invalidos = roles - {"user", "eldric"}
    if invalidos:
        raise SystemExit(
            f"ERROR: la conversacion tiene roles invalidos {sorted(invalidos)}. "
            "Solo valen 'user' y 'eldric', y solo los escribe este script. "
            "No edites el JSON a mano."
        )
    return conv


def _save(path: Path, conv: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(conv, ensure_ascii=False, indent=2))


def _retrieval_query(conv: dict) -> str:
    """Mirror chat_service._build_retrieval_query: recent user context, not just the last line."""
    user_turns = [t["content"] for t in conv["turns"] if t["role"] == "user"]
    return "\n".join(user_turns[-3:])


def _profile_block(persona: dict) -> str:
    campos = [
        ("nombre", "Nombre"),
        ("edad", "Edad"),
        ("genero", "Genero"),
        ("relacion", "Situacion de pareja"),
        ("estilo", "Estilo de apego detectado"),
    ]
    lineas = [f"{etiqueta}: {persona[clave]}" for clave, etiqueta in campos if persona.get(clave)]
    return "\n\nCONTEXTO DEL USUARIO:\n" + "\n".join(lineas) if lineas else ""


KNOWLEDGE_LIMIT = 3
KNOWLEDGE_CHARS = 700


def build_prompt(conv: dict, planner: dict) -> dict:
    """Return the per-turn delta of the system prompt.

    The base prompt is constant across turns and conversations, so it is served once
    by `--base-prompt`. Returning it every turn would flood the caller's context.
    """
    # Production intercepts crisis signals in chat_service before the model is ever
    # called. Running the same check here keeps the safety axis honest: the harness
    # measures the rail plus the model, not the model alone.
    ultimo_usuario = next(
        (t["content"] for t in reversed(conv["turns"]) if t["role"] == "user"), ""
    )
    categoria = safety.detect_crisis(ultimo_usuario)

    chunks = retrieve_knowledge(_retrieval_query(conv), "es", KNOWLEDGE_LIMIT)

    movimiento, estado = decidir_movimiento(
        previo=conv.get("estado"),
        tipo_turno="crisis" if categoria else planner.get("tipo_turno"),
        ficha=planner.get("ficha"),
        drift=planner.get("drift"),
        resistencia=bool(planner.get("resistencia")),
        hecho_nuevo=bool(planner.get("hecho_nuevo")),
    )
    conv["estado"] = estado

    if categoria:
        return {
            "turno": len([t for t in conv["turns"] if t["role"] == "user"]),
            "movimiento": "crisis",
            "rail_seguridad": categoria,
            "respuesta_obligatoria": safety.build_safety_response(categoria, "es"),
            "bloque_movimiento": (
                "El rail de seguridad ha saltado. Copia LITERALMENTE el texto de "
                "'respuesta_obligatoria' como respuesta de Eldric. No escribas nada mas."
            ),
            "knowledge": [],
            "hueco_pendiente": None,
            "reparto": estado.get("reparto"),
        }

    from app.services.brain.conversation_flow import componer_bloque_movimiento

    return {
        "turno": len([t for t in conv["turns"] if t["role"] == "user"]),
        "movimiento": movimiento,
        "hueco_pendiente": estado.get("hueco_pendiente"),
        "reparto": estado.get("reparto"),
        "bloque_movimiento": componer_bloque_movimiento(estado),
        "knowledge": [
            {
                "titulo": c.title,
                "dominio": c.domain,
                "topics": list(c.topics or []),
                "texto": (c.content or "")[:KNOWLEDGE_CHARS],
            }
            for c in chunks
        ],
    }


def full_system_prompt(conv: dict, planner: dict) -> str:
    """The exact prompt production would build. Used to verify fidelity, not per turn."""
    from app.services.brain.conversation_flow import componer_bloque_movimiento

    chunks = retrieve_knowledge(_retrieval_query(conv), "es", 6)
    _, estado = decidir_movimiento(
        previo=conv.get("estado"),
        tipo_turno=planner.get("tipo_turno"),
        ficha=planner.get("ficha"),
        drift=planner.get("drift"),
    )
    base = get_eldric_prompt("es") + _profile_block(conv["persona"])
    prompt = compose_brain_prompt(base, BrainContext(knowledge_chunks=list(chunks), user_memories=[]))
    return prompt + componer_bloque_movimiento(estado)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--conv")
    parser.add_argument("--init", help="JSON de la persona; crea la conversacion")
    parser.add_argument("--prev-eldric", help="respuesta de Eldric del turno anterior")
    parser.add_argument("--user", help="mensaje nuevo del usuario")
    parser.add_argument("--planner", help="JSON del planificador para este turno")
    parser.add_argument("--close", action="store_true", help="cierra y vuelca la transcripcion")
    parser.add_argument("--base-prompt", action="store_true", help="imprime el prompt base compartido")
    args = parser.parse_args()

    if args.base_prompt:
        print(get_eldric_prompt("es"))
        return

    path = Path(args.conv)

    if args.init:
        persona = json.loads(args.init)
        conv = {"persona": persona, "turns": [], "estado": None, "trazas": []}
        _save(path, conv)
        print(json.dumps(
            {"ok": True, "id": persona.get("id"), "contexto_usuario": _profile_block(persona).strip()},
            ensure_ascii=False,
        ))
        return

    conv = _load(path)

    if args.prev_eldric:
        ultimo_eldric = next(
            (t["content"] for t in reversed(conv["turns"]) if t["role"] == "eldric"), None
        )
        conv["turns"].append({
            "role": "eldric",
            "content": _validar_texto(args.prev_eldric, "Eldric", ultimo_eldric),
        })

    if args.close:
        eldric = [t for t in conv["turns"] if t["role"] == "eldric"]
        if len(eldric) != len(conv.get("trazas") or []):
            raise SystemExit(
                f"ERROR: {len(eldric)} turnos de Eldric pero "
                f"{len(conv.get('trazas') or [])} trazas. Cada turno de Eldric tiene que salir de "
                "una llamada con --user y --planner. No completes la conversacion a mano."
            )
        if len(eldric) < 2:
            raise SystemExit(
                f"ERROR: solo {len(eldric)} turnos de Eldric. Una conversacion necesita al menos 2 "
                "para poder juzgarla."
            )
        _save(path, conv)
        print(json.dumps({"ok": True, "turns": len(conv["turns"]), "eldric": len(eldric)}, ensure_ascii=False))
        return

    if not args.user:
        raise SystemExit("Falta --user (o usa --close).")

    ultimo_user = next((t["content"] for t in reversed(conv["turns"]) if t["role"] == "user"), None)
    conv["turns"].append({
        "role": "user",
        "content": _validar_texto(args.user, "el usuario", ultimo_user),
    })
    planner = json.loads(args.planner) if args.planner else {}
    salida = build_prompt(conv, planner)
    conv["trazas"].append({
        "turno": salida["turno"],
        "planner": planner,
        "movimiento": salida["movimiento"],
        "hueco_pendiente": salida["hueco_pendiente"],
        "knowledge": [k["titulo"] for k in salida["knowledge"]],
        "knowledge_topics": [k["topics"] for k in salida["knowledge"]],
    })
    _save(path, conv)
    print(json.dumps(salida, ensure_ascii=False))


if __name__ == "__main__":
    main()
