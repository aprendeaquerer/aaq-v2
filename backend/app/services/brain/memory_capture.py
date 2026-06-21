"""First-pass user memory capture.

This deliberately creates candidate memories, not trusted facts. The goal is to
make the memory brain observable while the product is still in development.
"""

import json
import re
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_memory import UserMemory


async def capture_candidate_memories(
    db: AsyncSession,
    user_id: Optional[str],
    message: str,
    language: str = "es",
) -> List[Dict[str, str]]:
    if not user_id:
        return []

    candidates = _extract_candidates(message, language)
    created = []
    for candidate in candidates:
        if await _similar_memory_exists(db, user_id, candidate["summary"]):
            continue
        memory = UserMemory(
            user_id=user_id,
            type=candidate["type"],
            summary=candidate["summary"],
            curated_summary=candidate["curated_summary"],
            visibility="user_visible",
            sensitivity=candidate["sensitivity"],
            confidence=candidate["confidence"],
            status="candidate",
            source_message_ids=json.dumps([]),
            memory_metadata=json.dumps({"language": language, "capture": "heuristic_v1"}),
        )
        db.add(memory)
        await db.flush()
        created.append(
            {
                "id": memory.id,
                "type": memory.type,
                "summary": memory.summary,
                "curated_summary": memory.curated_summary or memory.summary,
                "status": memory.status,
                "confidence": memory.confidence,
            }
        )

    if created:
        await db.commit()
    return created


def _extract_candidates(message: str, language: str) -> List[Dict]:
    text = " ".join(message.strip().split())
    lower = text.lower()
    if _is_low_signal_message(lower):
        return []

    candidates = []

    user_name_match = re.search(
        r"\b(?:me llamo|mi nombre es)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not user_name_match:
        user_name_match = re.search(
            r"^\s*soy\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)(?=\s*(?:,|\.|;|y tengo|tengo|$))",
            text,
            flags=re.IGNORECASE,
        )
    if user_name_match:
        name = _format_name(user_name_match.group(1))
        if _looks_like_person_name(name):
            candidates.append(_candidate(
                "profile_fact",
                f"The user's name is {name}.",
                f"Your name appears to be {name}.",
                0.86,
            ))

    user_age_match = re.search(r"\b(?:tengo|yo tengo)\s+(\d{1,2})\s*(?:anos|años)?\b", lower)
    if user_age_match:
        age = int(user_age_match.group(1))
        if 13 <= age <= 100:
            candidates.append(_candidate(
                "profile_fact",
                f"The user is {age} years old.",
                f"You appear to be {age} years old.",
                0.82,
            ))

    partner_match = re.search(
        r"(?:mi pareja|mi novia|mi novio|mi mujer|mi marido|mi esposa|mi esposo)\s+(?:se llama|es)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)",
        text,
        flags=re.IGNORECASE,
    )
    if partner_match:
        name = _format_name(partner_match.group(1))
        if _looks_like_person_name(name):
            candidates.append(_candidate(
                "relationship_context",
                f"The user's partner is named {name}.",
                f"Your partner's name appears to be {name}.",
                0.72,
            ))

    partner_age_match = re.search(
        r"\b(?:mi pareja|mi novia|mi novio|mi mujer|mi marido|mi esposa|mi esposo|ella|el|él)\s+(?:tiene|tendra|tendrá)\s+(\d{1,2})\s*(?:anos|años)?\b",
        lower,
    )
    if not partner_age_match:
        partner_age_match = re.search(r"\b(?:se llama|es)\s+[\wáéíóúñ-]+\s+y\s+tiene\s+(\d{1,2})\s*(?:anos|años)?\b", lower)
    if partner_age_match:
        age = int(partner_age_match.group(1))
        if 13 <= age <= 100:
            candidates.append(_candidate(
                "relationship_context",
                f"The user's partner is {age} years old.",
                f"Your partner appears to be {age} years old.",
                0.76,
            ))

    candidates.extend(_extract_people_context(text))
    candidates.extend(_extract_object_context(text))
    candidates.extend(_extract_life_context(text))
    candidates.extend(_extract_preferences_and_interests(text))
    candidates.extend(_extract_values_context(text))

    if any(phrase in lower for phrase in (
        "me siento", "i feel", "siento que", "i get", "me molesta", "me duele",
        "me preocupa", "me frustra", "me da rabia", "no me gusta", "me da miedo",
        "me da ansiedad", "tengo miedo", "tengo ansiedad", "estoy triste",
        "estoy ansioso", "estoy ansiosa", "me siento inseguro", "me siento insegura",
        "me siento solo", "me siento sola", "me agobia", "me angustia",
        "estoy confundido", "estoy confundida", "me cuesta", "i struggle",
    )):
        candidates.append(_candidate(
            "emotional_pattern",
            f"User described this emotional experience: {text}",
            f"You described this as emotionally important: {text}",
            0.42,
        ))

    if any(phrase in lower for phrase in (
        "quiero", "me gustaria", "me gustaría", "quisiera", "necesito",
        "mi objetivo es", "mi objetivo seria", "mi objetivo sería", "mi meta es",
        "mi meta seria", "mi meta sería", "busco", "estoy intentando",
        "estoy tratando", "me encantaria", "me encantaría", "quiero aprender",
        "quiero dejar de", "quiero empezar a", "tengo ganas de", "ojala",
        "ojalá", "espero poder", "me gustaria poder", "me gustaría poder",
        "necesito aprender", "i want", "i would like", "i need", "my goal is",
        "my objective is", "i am trying to",
    )):
        candidates.append(_candidate(
            "goal",
            f"User expressed a possible goal or desire: {text}",
            f"You said this may matter to you: {text}",
            0.40,
        ))

    if _looks_like_support_interest(lower):
        candidates.append(_candidate(
            "support_interest",
            f"User may be looking for support or resources: {text}",
            f"You may be looking for support or resources around this: {text}",
            0.36,
        ))

    if _looks_like_attachment_context(lower):
        candidates.append(_candidate(
            "attachment_context",
            f"User described an attachment-related context: {text}",
            f"This attachment context may matter later: {text}",
            0.48,
        ))

    if any(phrase in lower for phrase in ("cuando", "whenever", "when ")) and any(
        phrase in lower for phrase in ("ansiedad", "anxiety", "miedo", "fear", "triste", "sad")
    ):
        candidates.append(_candidate(
            "emotional_trigger",
            f"User described a possible trigger: {text}",
            f"This situation may be a trigger for you: {text}",
            0.46,
        ))

    if _looks_like_relationship_pattern(lower):
        candidates.append(_candidate(
            "relationship_pattern",
            f"User described a recurring relationship pattern: {text}",
            f"A recurring relationship pattern may be: {text}",
            0.50,
        ))

    if _looks_like_conflict_context(lower):
        candidates.append(_candidate(
            "relationship_conflict",
            f"User described a relationship conflict context: {text}",
            f"This relationship conflict context may matter later: {text}",
            0.44,
        ))

    if _looks_like_partner_stance(lower):
        candidates.append(_candidate(
            "partner_stance",
            f"User described their partner's stance or framing: {text}",
            f"Your partner's stance or framing may be: {text}",
            0.40,
        ))

    if _looks_like_knowledge_interest(lower):
        candidates.append(_candidate(
            "knowledge_interest",
            f"User showed interest in a knowledge topic: {text}",
            f"This topic may be useful to bring into future conversations: {text}",
            0.34,
        ))

    if not candidates and _looks_like_personal_context(lower):
        candidates.append(_candidate(
            "personal_context",
            f"User shared personal context: {text}",
            f"You shared this personal context: {text}",
            0.30,
        ))

    return _dedupe_candidates(candidates)[:10]


def _is_low_signal_message(lower: str) -> bool:
    normalized = _normalize(lower)
    return normalized in {
        "",
        "a",
        "b",
        "c",
        "d",
        "hola",
        "hello",
        "hi",
        "ok",
        "okay",
        "vale",
        "gracias",
        "thanks",
        "session_start",
        "saludo inicial",
    }


def _extract_people_context(text: str) -> List[Dict]:
    people = []
    relationship_pattern = re.compile(
        r"\bmi\s+(madre|mama|mamá|padre|papa|papá|hermana|hermano|hija|hijo|"
        r"amiga|amigo|ex|jefa|jefe|terapeuta|coach|mentor|mentora)\s+"
        r"(?:se llama|es)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)",
        flags=re.IGNORECASE,
    )
    for relation, raw_name in relationship_pattern.findall(text):
        name = _format_name(raw_name)
        if _looks_like_person_name(name):
            people.append(_candidate(
                "important_person",
                f"The user mentioned {relation} named {name}.",
                f"{name} may be an important person for you ({relation}).",
                0.70,
            ))
    informal_pattern = re.compile(
        r"\bmi\s+(madre|mama|mamá|padre|papa|papá|hermana|hermano|hija|hijo|"
        r"amiga|amigo|ex|jefa|jefe|terapeuta|coach|mentor|mentora)\s+"
        r"([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)\b",
        flags=re.IGNORECASE,
    )
    for relation, raw_name in informal_pattern.findall(text):
        name = _format_name(raw_name)
        if _looks_like_person_name(name):
            people.append(_candidate(
                "important_person",
                f"The user mentioned {relation} named {name}.",
                f"{name} may be an important person for you ({relation}).",
                0.58,
            ))
    lower = text.lower()
    if any(term in lower for term in ("mi ex", "my ex")):
        people.append(_candidate(
            "important_person",
            f"User mentioned an ex-partner in this context: {text}",
            f"An ex-partner may matter in this context: {text}",
            0.46,
        ))
    return people


def _extract_object_context(text: str) -> List[Dict]:
    lower = text.lower()
    object_terms = (
        "mi casa", "mi piso", "mi coche", "mi negocio", "mi empresa",
        "mi proyecto", "mi libro", "mi diario", "mi cuerpo", "mi salud",
        "mi rutina", "mi ciudad", "my house", "my car", "my business",
        "my company", "my project", "my book", "my journal", "my body",
        "my health", "my routine", "my city",
    )
    if not any(term in lower for term in object_terms):
        return []
    return [_candidate(
        "object_or_project_context",
        f"User mentioned an object, project, place, or life area that matters: {text}",
        f"This object, project, place, or life area may matter later: {text}",
        0.38,
    )]


def _extract_life_context(text: str) -> List[Dict]:
    lower = text.lower()
    contexts = []
    if any(phrase in lower for phrase in ("trabajo como", "trabajo en", "mi trabajo", "my job", "i work as", "i work in")):
        contexts.append(_candidate(
            "life_context",
            f"User shared work context: {text}",
            f"Your work context may matter later: {text}",
            0.46,
        ))
    if any(phrase in lower for phrase in ("vivo en", "vivo con", "vivo solo", "vivo sola", "i live in", "i live with", "i live alone")):
        contexts.append(_candidate(
            "life_context",
            f"User shared living context: {text}",
            f"Your living context may matter later: {text}",
            0.46,
        ))
    if any(phrase in lower for phrase in ("estudio", "estoy estudiando", "i study", "i am studying")):
        contexts.append(_candidate(
            "life_context",
            f"User shared study context: {text}",
            f"Your study context may matter later: {text}",
            0.42,
        ))
    return contexts


def _extract_preferences_and_interests(text: str) -> List[Dict]:
    lower = text.lower()
    interests = []
    preference_terms = (
        "me gusta", "me gustan", "me encanta", "me encantan", "disfruto",
        "prefiero", "no me gusta", "odio", "me interesa", "me interesan",
        "estoy aprendiendo", "leo sobre", "i like", "i love", "i prefer",
        "i dislike", "i hate", "i am interested in", "i'm interested in",
    )
    if any(term in lower for term in preference_terms):
        interests.append(_candidate(
            "interest_or_preference",
            f"User shared an interest or preference: {text}",
            f"This interest or preference may help personalize future conversations: {text}",
            0.42,
        ))
    return interests


def _extract_values_context(text: str) -> List[Dict]:
    lower = text.lower()
    value_terms = (
        "para mi es importante", "para mí es importante", "valoro", "mis valores",
        "necesito sentir", "me importa mucho", "no negocio", "my values",
        "i value", "it matters to me", "important to me",
    )
    if not any(term in lower for term in value_terms):
        return []
    return [_candidate(
        "value_or_need",
        f"User described a value or need: {text}",
        f"This value or need may matter later: {text}",
        0.48,
    )]


def _looks_like_relationship_pattern(lower: str) -> bool:
    recurrence_terms = (
        "siempre", "cada vez", "normalmente", "a menudo", "muchas veces",
        "often", "always", "usually", "every time",
    )
    relationship_terms = (
        "mi pareja", "pareja", "ella", "el ", "él", "novia", "novio",
        "my partner", "girlfriend", "boyfriend", "wife", "husband",
    )
    pattern_terms = (
        "evita", "evitar", "avoid", "avoids", "se cierra", "se aleja",
        "no habla", "no quiere hablar", "conflicto", "pelea", "discusion",
        "discusión", "argument", "fight", "shuts down", "withdraws",
    )
    return (
        any(term in lower for term in recurrence_terms)
        and any(term in lower for term in relationship_terms)
        and any(term in lower for term in pattern_terms)
    )


def _looks_like_conflict_context(lower: str) -> bool:
    relationship_terms = (
        "mi pareja", "pareja", "ella", "el ", "él", "novia", "novio",
        "my partner", "girlfriend", "boyfriend", "wife", "husband",
    )
    conflict_terms = (
        "conflicto", "pelea", "discusion", "discusión", "discutimos",
        "argument", "fight", "fighting", "repair", "reparar",
    )
    return any(term in lower for term in relationship_terms) and any(term in lower for term in conflict_terms)


def _looks_like_partner_stance(lower: str) -> bool:
    relationship_terms = (
        "mi pareja", "pareja", "ella", "el ", "él", "novia", "novio",
        "my partner", "girlfriend", "boyfriend", "wife", "husband",
    )
    stance_terms = (
        "dice que", "cree que", "piensa que", "siente que", "segun ella",
        "según ella", "segun el", "según él", "says that", "thinks that",
        "believes that", "identity", "identidad", "mi problema", "my problem",
    )
    return any(term in lower for term in relationship_terms) and any(term in lower for term in stance_terms)


def _looks_like_attachment_context(lower: str) -> bool:
    attachment_terms = (
        "apego", "attachment", "ansioso", "ansiosa", "anxious",
        "evitativo", "evitativa", "avoidant", "desorganizado",
        "desorganizada", "disorganized", "apego seguro", "secure attachment",
    )
    relationship_terms = (
        "yo", "soy", "me siento", "mi pareja", "pareja", "mi novia", "mi novio",
        "ella", "el ", "él", "my partner", "girlfriend", "boyfriend", "wife", "husband",
    )
    return any(term in lower for term in attachment_terms) and any(term in lower for term in relationship_terms)


def _looks_like_support_interest(lower: str) -> bool:
    support_terms = (
        "coach", "terapeuta", "psicologo", "psicólogo", "terapia", "sesion",
        "sesión", "curso", "libro", "recurso", "ejercicio", "recomendar",
        "recomiendas", "ayuda profesional", "coach", "therapist", "therapy",
        "book", "resource", "exercise", "recommend",
    )
    return any(term in lower for term in support_terms)


def _looks_like_knowledge_interest(lower: str) -> bool:
    knowledge_terms = (
        "apego", "attachment", "vagal", "somatico", "somático", "meditacion",
        "meditación", "masculinidad", "feminidad", "polaridad", "conciencia",
        "consciousness", "self improvement", "autoconocimiento", "relaciones",
        "relationship", "inner child", "niño interior", "herida", "trauma",
    )
    question_or_interest_terms = (
        "que es", "qué es", "como funciona", "cómo funciona", "quiero saber",
        "quiero entender", "me interesa", "explicame", "explícame", "what is",
        "how does", "i want to understand", "tell me about",
    )
    return any(term in lower for term in knowledge_terms) and any(term in lower for term in question_or_interest_terms)


def _looks_like_personal_context(lower: str) -> bool:
    personal_terms = (
        "yo", "me ", "mi ", "mis ", "conmigo", "mi pareja", "mi novia",
        "mi novio", "mi familia", "mi trabajo", "my ", "i ", "me ",
    )
    relational_or_inner_terms = (
        "relacion", "relación", "pareja", "novia", "novio", "familia",
        "amigo", "amiga", "trabajo", "siento", "pienso", "creo",
        "necesito", "quiero", "miedo", "ansiedad", "triste", "enfado",
        "culpa", "verguenza", "vergüenza", "relationship", "partner",
        "feel", "think", "need", "want", "fear", "anxiety", "sad",
    )
    return (
        len(lower) >= 24
        and any(term in lower for term in personal_terms)
        and any(term in lower for term in relational_or_inner_terms)
    )


def _dedupe_candidates(candidates: List[Dict]) -> List[Dict]:
    deduped = []
    seen = set()
    for candidate in candidates:
        key = (candidate["type"], _normalize(candidate["summary"])[:140])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _candidate(memory_type: str, summary: str, curated_summary: str, confidence: float) -> Dict:
    return {
        "type": memory_type,
        "summary": summary,
        "curated_summary": curated_summary,
        "confidence": confidence,
        "sensitivity": "normal",
    }


def _format_name(name: str) -> str:
    cleaned = name.strip(" .,;:!?")
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


def _looks_like_person_name(name: str) -> bool:
    lower = name.lower()
    non_names = {
        "de",
        "un",
        "una",
        "hombre",
        "mujer",
        "pareja",
        "ansioso",
        "ansiosa",
        "evitativo",
        "evitativa",
        "desorganizado",
        "desorganizada",
        "seguro",
        "segura",
        "anxious",
        "avoidant",
        "disorganized",
        "secure",
    }
    return lower not in non_names


async def _similar_memory_exists(db: AsyncSession, user_id: str, summary: str) -> bool:
    result = await db.execute(
        select(UserMemory.summary)
        .where(UserMemory.user_id == user_id)
        .order_by(UserMemory.updated_at.desc())
        .limit(50)
    )
    normalized = _normalize(summary)
    for row in result.all():
        existing = _normalize(row[0])
        if existing == normalized or normalized[:80] in existing:
            return True
    return False


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()
