#!/usr/bin/env python3
"""Run generated user personas against Eldric and publish inspectable QA transcripts."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import secrets
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_PATH = ROOT / "frontend/src/data/personalityTestScenarios.json"
PUBLIC_QA_DIR = ROOT / "frontend/public/qa"
PRIVATE_QA_DIR = ROOT / ".qa"
DEFAULT_API_URL = "https://aprendeaquerer.com/api/backend"
PRINT_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def request_json(
    api_url: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: dict[str, Any] | None = None,
    attempts: int = 3,
) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            f"{api_url.rstrip('/')}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts:
                detail = ""
                if isinstance(exc, urllib.error.HTTPError):
                    detail = exc.read().decode(errors="replace")[:500]
                raise RuntimeError(f"{method} {path} failed: {exc} {detail}") from exc
            time.sleep(attempt * 2)


def step(debug: dict[str, Any], stage: str) -> dict[str, Any]:
    return next((item for item in debug.get("steps", []) if item.get("stage") == stage), {})


def normalise_items(items: Any, fields: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [{field: item.get(field) for field in fields} for item in items if isinstance(item, dict)]


def turn_record(prompt: str, response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data", {})
    debug = data.get("debug") or {}
    router = step(debug, "brain_router")
    knowledge = step(debug, "knowledge_brain")
    memory_retrieval = step(debug, "memory_brain")
    memory_capture = step(debug, "memory_capture")
    profile_capture = step(debug, "profile_capture")
    router_payload = router.get("payload") or {}
    knowledge_payload = knowledge.get("payload") or {}
    memory_payload = memory_retrieval.get("payload") or {}
    capture_payload = memory_capture.get("payload") or {}
    profile_payload = profile_capture.get("payload") or {}

    chunks = normalise_items(
        knowledge_payload.get("chunks"),
        ("id", "title", "section", "domain", "score", "preview"),
    )
    memories = normalise_items(
        memory_payload.get("memories"),
        ("id", "type", "confidence", "status", "summary"),
    )
    candidates = normalise_items(
        capture_payload.get("candidates"),
        ("id", "type", "confidence", "status", "summary"),
    )
    ai_error = next(
        (item.get("detail") for item in debug.get("steps", []) if item.get("stage") == "ai_error"),
        None,
    )
    return {
        "prompt": prompt,
        "type": response.get("type"),
        "message": data.get("message", ""),
        "debug": debug,
        "reasoning_summary": debug.get("reasoning_summary"),
        "intent": router_payload.get("intent"),
        "routed_domains": router_payload.get("domains", []),
        "knowledge": {"count": len(chunks), "detail": knowledge.get("detail", ""), "chunks": chunks},
        "memory_retrieval": {
            "count": len(memories),
            "detail": memory_retrieval.get("detail", ""),
            "memories": memories,
        },
        "memory_capture": {
            "count": len(candidates),
            "detail": memory_capture.get("detail", ""),
            "candidates": candidates,
        },
        "profile_capture": {
            "updates": profile_payload.get("updates", {}),
            "error": profile_payload.get("error"),
        },
        "ai_error": ai_error,
    }


def run_scenario(api_url: str, scenario: dict[str, Any], run_stamp: str, max_turns: int) -> dict[str, Any]:
    slug = scenario["id"][:24]
    email = f"qa-live+{slug}-{run_stamp}-{secrets.token_hex(3)}@aprendeaquerer.com"
    password = f"QA-{secrets.token_urlsafe(18)}-aaq"
    profile = scenario["profile"]
    result: dict[str, Any] = {
        "id": scenario["id"],
        "title": scenario["title"],
        "kind": scenario["kind"],
        "purpose": scenario["purpose"],
        "qaNote": scenario["qaNote"],
        "email": email,
        "expectedAttachmentStyle": scenario["attachmentStyle"],
        "profileSeed": profile,
        "openingPrompt": scenario["scenario"],
        "turns": [],
        "error": None,
    }
    try:
        request_json(
            api_url,
            "/auth/register",
            method="POST",
            body={"email": email, "password": password, "preferred_language": "es"},
        )
        login = request_json(
            api_url, "/auth/login", method="POST", body={"email": email, "password": password}
        )
        token = login["access_token"]
        result["userId"] = login.get("user_id")
        request_json(api_url, "/profile", method="PUT", token=token, body=profile)
        request_json(api_url, "/chat/session?language=es&debug=true", token=token)
        opening = request_json(
            api_url,
            "/chat/message",
            method="POST",
            token=token,
            body={"message": "A", "language": "es", "debug": True},
        )
        opening_message = str((opening.get("data") or {}).get("message") or "")
        result["setupResponses"] = [opening]
        history: list[dict[str, str]] = []
        if opening_message:
            history.append({"role": "bot", "content": opening_message})

        persona = {
            "nombre": profile["nombre"],
            "edad": profile["edad"],
            "genero": profile.get("genero"),
            "orientacion": profile.get("orientacion"),
            "tipo_relacion": profile.get("tipo_relacion"),
            "attachment_style": scenario["attachmentStyle"],
            "escenario": scenario["scenario"],
            "contexto": scenario.get("context"),
        }

        for turn_number in range(1, max_turns + 1):
            generated = request_json(
                api_url,
                "/brain/simulate-user-turn",
                method="POST",
                token=token,
                body={
                    "persona": persona,
                    "history": history,
                    "language": "es",
                    "turn_number": turn_number,
                    "max_turns": max_turns,
                },
            )
            prompt = str(generated.get("message") or "").strip()
            if not prompt:
                break
            response = request_json(
                api_url,
                "/chat/message",
                method="POST",
                token=token,
                body={"message": prompt, "language": "es", "debug": True},
            )
            result["turns"].append(turn_record(prompt, response))
            bot_message = str((response.get("data") or {}).get("message") or "")
            history.extend(
                [
                    {"role": "persona", "content": prompt},
                    {"role": "bot", "content": bot_message},
                ]
            )
            with PRINT_LOCK:
                print(f"[{scenario['id']}] turn {turn_number}/{max_turns}", flush=True)
            if generated.get("should_end"):
                break

        result["storedProfile"] = request_json(api_url, "/profile", token=token)
        memory_response = request_json(api_url, "/memory", token=token)
        result["storedMemoryResponse"] = memory_response
        result["finalMemories"] = memory_response.get("memories", [])
    except Exception as exc:  # keep the other personas running and publish the failure
        result["error"] = str(exc)
        with PRINT_LOCK:
            print(f"[{scenario['id']}] ERROR: {exc}", file=sys.stderr, flush=True)
    return result


def aggregate(conversations: list[dict[str, Any]]) -> dict[str, Any]:
    turns = [turn for conversation in conversations for turn in conversation.get("turns", [])]
    knowledge_counts = [turn["knowledge"]["count"] for turn in turns]
    planner_errors = 0
    for turn in turns:
        steps = (turn.get("debug") or {}).get("steps", [])
        planner_errors += any(
            item.get("stage") == "coaching_planner" and (item.get("payload") or {}).get("error")
            for item in steps
            if isinstance(item, dict)
        )
    return {
        "conversationCount": len(conversations),
        "failedConversationCount": sum(bool(item.get("error")) for item in conversations),
        "turnCount": len(turns),
        "aiErrorTurnCount": sum(bool(turn.get("ai_error")) for turn in turns),
        "plannerErrorTurnCount": planner_errors,
        "knowledgeTurnCount": sum(turn["knowledge"]["count"] > 0 for turn in turns),
        "noKnowledgeTurnCount": sum(turn["knowledge"]["count"] == 0 for turn in turns),
        "memoryRetrievedTurnCount": sum(turn["memory_retrieval"]["count"] > 0 for turn in turns),
        "memoryCapturedTurnCount": sum(turn["memory_capture"]["count"] > 0 for turn in turns),
        "profileCapturedTurnCount": sum(bool(turn["profile_capture"]["updates"]) for turn in turns),
        "averageKnowledgeChunks": round(sum(knowledge_counts) / len(knowledge_counts), 2) if turns else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--turns", type=int, default=6)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    scenarios = json.loads(SCENARIOS_PATH.read_text())
    if args.limit:
        scenarios = scenarios[: args.limit]
    started_at = utc_now()
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_id = f"personality-live-qa-{run_stamp}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_scenario, args.api_url, item, run_stamp, args.turns) for item in scenarios]
        conversations = [future.result() for future in futures]

    completed_at = utc_now()
    permanent_name = f"{run_id}.json"
    report = {
        "runId": run_id,
        "startedAt": started_at,
        "completedAt": completed_at,
        "apiUrl": args.api_url,
        "focus": "New personality: generated realistic personas across age, gender, orientation, and relationship status",
        "instructions": "Inspect each turn for the simulated user's message, Eldric's reply, concise decision summary, routed domains, retrieved knowledge, and saved memory. Hidden chain-of-thought is not exposed.",
        "permanentPath": f"/qa/{permanent_name}",
        "aggregate": aggregate(conversations),
        "conversations": conversations,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    PUBLIC_QA_DIR.mkdir(parents=True, exist_ok=True)
    PRIVATE_QA_DIR.mkdir(parents=True, exist_ok=True)
    (PUBLIC_QA_DIR / "personality-latest.json").write_text(rendered)
    (PUBLIC_QA_DIR / permanent_name).write_text(rendered)
    (PRIVATE_QA_DIR / permanent_name).write_text(rendered)
    print(json.dumps(report["aggregate"], indent=2), flush=True)
    print(f"Published {PUBLIC_QA_DIR / 'personality-latest.json'}", flush=True)
    return 1 if report["aggregate"]["failedConversationCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
