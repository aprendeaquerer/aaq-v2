#!/usr/bin/env python3
"""
Smoke test user memory capture through the public API.

Usage:
  cd /Users/pedro/AAQ/backend
  python scripts/memory_capture_smoke.py --api-url http://localhost:8000

The script creates disposable synthetic users, sends Spanish chat messages, and
asserts that profile fields plus candidate memories are visible through the API.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


DEFAULT_API_URL = "http://localhost:8000"
PASSWORD = "MemorySmoke!2026"

PROFILE_FIELDS = (
    "nombre",
    "edad",
    "genero",
    "tiene_pareja",
    "nombre_pareja",
    "edad_pareja",
    "genero_pareja",
    "tipo_relacion",
    "attachment_style",
    "partner_attachment_style",
    "relationship_status",
)

REQUIRED_MEMORY_TYPES = {"goal", "emotional_pattern"}
CONTEXT_MEMORY_TYPES = {
    "relationship_context",
    "profile_fact",
    "important_person",
    "interest_or_preference",
    "attachment_context",
    "relationship_pattern",
    "relationship_conflict",
    "partner_stance",
    "life_context",
    "value_or_need",
    "knowledge_interest",
    "support_interest",
    "object_or_project_context",
    "personal_context",
}


@dataclass(frozen=True)
class SyntheticUser:
    slug: str
    messages: list[str]
    expected_profile: dict[str, Any]


SYNTHETIC_USERS = [
    SyntheticUser(
        slug="clara",
        expected_profile={
            "nombre": "Clara",
            "edad": 31,
            "genero": "mujer",
            "tiene_pareja": True,
            "nombre_pareja": "Diego",
            "edad_pareja": 34,
            "genero_pareja": "hombre",
            "tipo_relacion": "noviazgo",
            "attachment_style": "anxious",
            "partner_attachment_style": "avoidant",
            "relationship_status": "anxious_avoidant_dynamic",
        },
        messages=[
            "Me llamo Clara, tengo 31 años y soy mujer.",
            "Mi novio se llama Diego y tiene 34 años.",
            "Es mi novio y mi pareja es hombre.",
            "Mi estilo de apego es ansioso y mi pareja es evitativo.",
            "Quiero aprender a pedir seguridad sin sonar exigente.",
            "Me siento insegura cuando Diego tarda horas en responder.",
            "Siempre que hay conflicto mi pareja evita hablar y se cierra.",
            "Mi pareja dice que exagero cuando intento reparar una discusión.",
            "Vivimos juntos desde hace dos años y no tenemos hijos.",
            "Me gustaría entender cómo reparar después de una pelea.",
            "Me interesa practicar comunicación no violenta y escribir un diario emocional.",
        ],
    ),
    SyntheticUser(
        slug="marcos",
        expected_profile={
            "nombre": "Marcos",
            "edad": 42,
            "genero": "hombre",
            "tiene_pareja": True,
            "nombre_pareja": "Irene",
            "edad_pareja": 40,
            "genero_pareja": "mujer",
            "tipo_relacion": "matrimonio",
            "attachment_style": "secure",
            "partner_attachment_style": "secure",
            "relationship_status": "secure_dynamic",
        },
        messages=[
            "Soy Marcos, tengo 42 años y soy hombre.",
            "Mi esposa se llama Irene y tiene 40 años.",
            "Estamos casados y mi esposa es mujer.",
            "Mi apego es seguro y mi esposa tiene apego seguro.",
            "Quiero cuidar mejor los pequeños rituales de conexión diaria.",
            "Me siento triste cuando dejamos pasar semanas sin una cita tranquila.",
            "Cuando hay estrés familiar me da ansiedad y hablo más seco.",
            "A menudo mi pareja dice que me voy al modo solución demasiado rápido.",
            "Tenemos hijos y vivimos juntos.",
            "Necesito aprender a escuchar antes de aconsejar.",
            "Me interesa la crianza consciente, la cocina y caminar por la mañana.",
        ],
    ),
    SyntheticUser(
        slug="lucia",
        expected_profile={
            "nombre": "Lucía",
            "edad": 28,
            "genero": "mujer",
            "tiene_pareja": True,
            "nombre_pareja": "Alex",
            "edad_pareja": 29,
            "genero_pareja": "no_binario",
            "attachment_style": "disorganized",
            "partner_attachment_style": "anxious",
            "relationship_status": "disorganized_dynamic",
        },
        messages=[
            "Me llamo Lucía, tengo 28 años y soy mujer.",
            "Soy bisexual y mi pareja se llama Alex y tiene 29 años.",
            "Mi pareja es no binaria.",
            "Mi estilo de apego es desorganizada y mi pareja parece ansiosa.",
            "Quiero aprender a no desaparecer cuando siento demasiada intensidad.",
            "Me siento sola cuando Alex pregunta muchas veces si todo está bien.",
            "Cuando discutimos me da miedo perder la relación y luego me cierro.",
            "Siempre que hay conflicto mi pareja quiere hablar enseguida y yo evito.",
            "Mi pareja cree que necesito más espacio, pero también más claridad.",
            "No vivimos juntos y no tenemos hijos.",
            "Me gustaría trabajar límites, música y volver a pintar los fines de semana.",
        ],
    ),
]


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.access_token: str | None = None

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        request = Request(
            urljoin(self.base_url, path.lstrip("/")),
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8")
                return json.loads(response_body) if response_body else {}
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise ApiError(f"{method} {path} failed with HTTP {exc.code}: {error_body}") from exc
        except URLError as exc:
            raise ApiError(f"{method} {path} failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ApiError(f"{method} {path} timed out after {self.timeout}s") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test API-backed user memory capture.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help=f"API base URL. Default: {DEFAULT_API_URL}")
    parser.add_argument("--users", type=int, choices=(2, 3), default=3, help="Number of synthetic users to run.")
    parser.add_argument("--timeout", type=float, default=45.0, help="HTTP timeout per request in seconds.")
    parser.add_argument("--pause", type=float, default=0.0, help="Optional delay between chat messages.")
    parser.add_argument("--email-prefix", default="aaq.memory.smoke", help="Prefix for disposable test emails.")
    args = parser.parse_args()

    run_id = f"{int(time.time())}.{uuid.uuid4().hex[:8]}"
    selected_users = SYNTHETIC_USERS[: args.users]

    print(f"Running memory capture smoke against {args.api_url}")
    print(f"Creating {len(selected_users)} disposable users with run id {run_id}")

    failures: list[str] = []
    for synthetic_user in selected_users:
        email = f"{args.email_prefix}+{run_id}.{synthetic_user.slug}@example.com"
        try:
            run_user(args, synthetic_user, email)
            print(f"PASS {synthetic_user.slug}: profile and memories captured")
        except Exception as exc:  # noqa: BLE001 - smoke script should summarize all failures.
            failures.append(f"{synthetic_user.slug} ({email}): {exc}")
            print(f"FAIL {synthetic_user.slug}: {exc}", file=sys.stderr)

    if failures:
        print("\nSmoke test failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nSmoke test passed.")
    return 0


def run_user(args: argparse.Namespace, synthetic_user: SyntheticUser, email: str) -> None:
    client = ApiClient(args.api_url, args.timeout)

    client.post(
        "/auth/register",
        {"email": email, "password": PASSWORD, "preferred_language": "es"},
    )
    login = client.post("/auth/login", {"email": email, "password": PASSWORD})
    client.access_token = require(login, "access_token", "login response")

    for index, message in enumerate(synthetic_user.messages, start=1):
        response = client.post(
            "/chat/message",
            {"message": message, "language": "es", "debug": True},
        )
        response_type = response.get("type")
        if response_type not in {"conversation", "paywall"}:
            raise AssertionError(f"message {index} returned unexpected chat type {response_type!r}")
        if args.pause:
            time.sleep(args.pause)

    profile = client.get("/profile")
    assert_profile(synthetic_user, profile)

    memory_response = client.get("/memory")
    memories = memory_response.get("memories", [])
    assert_memories(synthetic_user, memories)


def assert_profile(synthetic_user: SyntheticUser, profile: dict[str, Any]) -> None:
    missing_fields = []
    mismatches = []
    populated_fields = [field for field in PROFILE_FIELDS if profile.get(field) not in (None, "", "unknown")]

    for field, expected in synthetic_user.expected_profile.items():
        actual = profile.get(field)
        if actual in (None, "", "unknown"):
            missing_fields.append(field)
        elif actual != expected:
            mismatches.append(f"{field}: expected {expected!r}, got {actual!r}")

    if missing_fields or mismatches:
        details = []
        if missing_fields:
            details.append(f"missing profile fields: {', '.join(missing_fields)}")
        if mismatches:
            details.append("profile mismatches: " + "; ".join(mismatches))
        details.append(f"populated fields: {', '.join(populated_fields) or 'none'}")
        raise AssertionError("; ".join(details))


def assert_memories(synthetic_user: SyntheticUser, memories: list[dict[str, Any]]) -> None:
    if not memories:
        raise AssertionError("no user-visible candidate/active memories returned")

    memory_types = {memory.get("type") for memory in memories}
    missing_required = REQUIRED_MEMORY_TYPES - memory_types
    if missing_required:
        raise AssertionError(
            f"missing required memory types {sorted(missing_required)}; found {sorted(memory_types)}"
        )

    context_matches = sorted(CONTEXT_MEMORY_TYPES & memory_types)
    if not context_matches:
        raise AssertionError(
            "missing relationship/person/interest context memory; "
            f"accepted context types are {sorted(CONTEXT_MEMORY_TYPES)}, found {sorted(memory_types)}"
        )

    summaries = " ".join(
        str(memory.get("summary", "")) + " " + str(memory.get("curated_summary", ""))
        for memory in memories
    ).lower()
    for marker in ("quiero", "me siento"):
        if marker not in summaries:
            raise AssertionError(f"{synthetic_user.slug} memories did not preserve marker {marker!r}")


def require(payload: dict[str, Any], field: str, label: str) -> Any:
    value = payload.get(field)
    if value in (None, ""):
        raise AssertionError(f"{label} missing {field!r}: {payload}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
