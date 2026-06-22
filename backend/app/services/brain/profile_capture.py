"""Lightweight structured profile capture from chat messages."""

import re
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserProfile


PROFILE_FIELDS = {
    "nombre",
    "edad",
    "genero",
    "tiene_pareja",
    "nombre_pareja",
    "edad_pareja",
    "genero_pareja",
    "tiempo_pareja",
    "orientacion",
    "tipo_relacion",
    "convive_con_pareja",
    "tiene_hijos",
    "trabajo_profesion",
    "convivencia",
    "ex_pareja_relevante",
    "ex_pareja_contexto",
    "estructura_familiar_relevante",
    "hijos_detalle",
}


async def capture_profile_fields(
    db: AsyncSession,
    user_id: Optional[str],
    message: str,
) -> Dict[str, object]:
    if not user_id:
        return {}

    user_result = await db.execute(select(User.user_id).where(User.user_id == user_id))
    if not user_result.scalar_one_or_none():
        return {}

    updates = _extract_profile_updates(message)
    if not updates:
        return {}

    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)

    applied: Dict[str, object] = {}
    for field, value in updates.items():
        current = getattr(profile, field)
        if current in (None, "", "unknown") or field in {"edad", "edad_pareja"}:
            setattr(profile, field, value)
            applied[field] = value

    if applied:
        await db.commit()

    return applied


def _extract_profile_updates(message: str) -> Dict[str, object]:
    text = " ".join(message.strip().split())
    lower = text.lower()
    updates: Dict[str, object] = {}

    user_name = _first_name_match(
        text,
        (
            r"\b(?:me llamo|mi nombre es)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)\b",
            r"^\s*soy\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)(?=\s*(?:,|\.|;|y tengo|tengo|$))",
            r"\b(?:my name is)\s+([A-Za-z][\w-]+)\b",
            r"^\s*(?:i am|i'm)\s+([A-Za-z][\w-]+)(?=\s*(?:,|\.|;|and i am|i am|$))",
        ),
    )
    if user_name:
        updates["nombre"] = user_name

    partner_name = _first_name_match(
        text,
        (
            r"\b(?:mi pareja|mi novia|mi novio|mi mujer|mi marido|mi esposa|mi esposo)\s+(?:se llama|es)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)\b",
            r"\b(?:my partner|my girlfriend|my boyfriend|my wife|my husband)\s+(?:is|is called|is named|name is)\s+([A-Za-z][\w-]+)\b",
        ),
    )
    if partner_name:
        updates["nombre_pareja"] = partner_name
        updates["tiene_pareja"] = True

    user_age = _first_int_match(
        lower,
        (
            r"\b(?:tengo|yo tengo|i am|i'm)\s+(\d{1,2})\s*(?:anos|años|years old|yo)?\b",
            r"\b(?:mi edad es|my age is)\s+(\d{1,2})\b",
        ),
    )
    if user_age and 13 <= user_age <= 100:
        updates["edad"] = user_age

    partner_age = _first_int_match(
        lower,
        (
            r"\b(?:mi pareja|mi novia|mi novio|mi mujer|mi marido|ella|el|él)\s+(?:tiene|tendra|tendrá)\s+(\d{1,2})\s*(?:anos|años|years old)?\b",
            r"\b(?:se llama|es)\s+[\wáéíóúñ-]+\s+y\s+tiene\s+(\d{1,2})\s*(?:anos|años)?\b",
            r"\b(?:my partner|my girlfriend|my boyfriend|my wife|my husband|she|he)\s+(?:is)\s+(\d{1,2})\s*(?:years old)?\b",
        ),
    )
    if partner_age and 13 <= partner_age <= 100:
        updates["edad_pareja"] = partner_age
        updates["tiene_pareja"] = True

    user_gender = _detect_user_gender(lower)
    if user_gender:
        updates["genero"] = user_gender

    partner_gender = _detect_partner_gender(lower)
    if partner_gender:
        updates["genero_pareja"] = partner_gender
        updates["tiene_pareja"] = True

    orientation = _detect_orientation(lower)
    if orientation:
        updates["orientacion"] = orientation

    relationship_type = _detect_relationship_type(lower)
    if relationship_type:
        updates["tipo_relacion"] = relationship_type
        updates["tiene_pareja"] = True

    relationship_duration = _detect_relationship_duration(text)
    if relationship_duration:
        updates["tiempo_pareja"] = relationship_duration
        updates["tiene_pareja"] = True

    work = _detect_work(text)
    if work:
        updates["trabajo_profesion"] = work

    living = _detect_living_situation(lower)
    if living:
        updates["convivencia"] = living

    if any(phrase in lower for phrase in ("mi pareja", "mi novia", "mi novio", "my partner", "girlfriend", "boyfriend")):
        updates.setdefault("tiene_pareja", True)

    does_not_live_with_partner = any(
        phrase in lower
        for phrase in ("no vivimos juntos", "no vivo con mi pareja", "we do not live together", "we don't live together")
    )
    if not does_not_live_with_partner and any(
        phrase in lower for phrase in ("vivo con mi pareja", "vivimos juntos", "convivo con", "we live together", "live with my partner")
    ):
        updates["convive_con_pareja"] = True
        updates.setdefault("convivencia", "pareja")
    if does_not_live_with_partner:
        updates["convive_con_pareja"] = False

    if any(phrase in lower for phrase in ("no tengo hijos", "no tenemos hijos", "i don't have kids", "i do not have children")):
        updates["tiene_hijos"] = False
    elif _has_children_signal(lower):
        updates["tiene_hijos"] = True
        children_detail = _detect_children_detail(text)
        if children_detail:
            updates["hijos_detalle"] = children_detail

    ex_context = _detect_ex_context(text)
    if ex_context:
        updates["ex_pareja_relevante"] = True
        updates["ex_pareja_contexto"] = ex_context

    family_structure = _detect_family_structure(text)
    if family_structure:
        updates["estructura_familiar_relevante"] = family_structure

    return {field: value for field, value in updates.items() if field in PROFILE_FIELDS}


def _first_int_match(text: str, patterns: tuple[str, ...]) -> Optional[int]:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return None


def _first_name_match(text: str, patterns: tuple[str, ...]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            name = _format_name(match.group(1))
            if _looks_like_person_name(name):
                return name
    return None


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


def _detect_user_gender(lower: str) -> Optional[str]:
    if any(phrase in lower for phrase in ("soy mujer", "me identifico como mujer", "i am a woman", "i'm a woman")):
        return "mujer"
    if any(phrase in lower for phrase in ("soy hombre", "me identifico como hombre", "i am a man", "i'm a man")):
        return "hombre"
    if any(phrase in lower for phrase in ("soy no binario", "soy no binaria", "non-binary", "nonbinary")):
        return "no_binario"
    return None


def _detect_partner_gender(lower: str) -> Optional[str]:
    if any(phrase in lower for phrase in ("mi novia", "mi mujer", "mi esposa", "mi pareja es mujer", "my girlfriend", "my wife")):
        return "mujer"
    if any(phrase in lower for phrase in ("mi novio", "mi marido", "mi esposo", "mi pareja es hombre", "my boyfriend", "my husband")):
        return "hombre"
    if any(phrase in lower for phrase in ("mi pareja es no binaria", "mi pareja es no binario", "my partner is non-binary", "my partner is nonbinary")):
        return "no_binario"
    return None


def _detect_orientation(lower: str) -> Optional[str]:
    if any(phrase in lower for phrase in ("soy heterosexual", "i am straight", "i'm straight")):
        return "heterosexual"
    if any(phrase in lower for phrase in ("soy gay", "soy homosexual", "i am gay", "i'm gay")):
        return "gay"
    if any(phrase in lower for phrase in ("soy lesbiana", "i am lesbian", "i'm lesbian")):
        return "lesbiana"
    if any(phrase in lower for phrase in ("soy bisexual", "i am bisexual", "i'm bisexual")):
        return "bisexual"
    if any(phrase in lower for phrase in ("soy pansexual", "i am pansexual", "i'm pansexual")):
        return "pansexual"
    return None


def _detect_relationship_type(lower: str) -> Optional[str]:
    if any(phrase in lower for phrase in ("estamos casados", "estoy casado", "estoy casada", "we are married", "i am married", "i'm married")):
        return "matrimonio"
    if any(phrase in lower for phrase in ("somos novios", "es mi novia", "es mi novio", "we are dating", "girlfriend", "boyfriend")):
        return "noviazgo"
    if any(phrase in lower for phrase in ("relacion abierta", "relación abierta", "open relationship")):
        return "relacion_abierta"
    if any(phrase in lower for phrase in ("poliamor", "polyamory", "polyamorous")):
        return "poliamor"
    return None


def _detect_relationship_duration(text: str) -> Optional[str]:
    patterns = (
        r"\b(?:llevamos|estamos juntos desde hace|llevamos juntos|tenemos una relacion de|tenemos una relación de)\s+([^.,;!?]+)",
        r"\b(?:mi relacion lleva|mi relación lleva|nuestra relacion lleva|nuestra relación lleva)\s+([^.,;!?]+)",
        r"\b(?:we have been together for|we've been together for|our relationship is)\s+([^.,;!?]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_short_fact(match.group(1), max_words=8)
    return None


def _detect_work(text: str) -> Optional[str]:
    patterns = (
        r"\b(?:trabajo como|me dedico a|soy profesionalmente|mi trabajo es)\s+([^.,;!?]+)",
        r"\b(?:trabajo en)\s+([^.,;!?]+)",
        r"\b(?:i work as|my job is)\s+([^.,;!?]+)",
        r"\b(?:i work in)\s+([^.,;!?]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_work_fact(match.group(1))
    return None


def _detect_living_situation(lower: str) -> Optional[str]:
    if any(phrase in lower for phrase in ("no vivimos juntos", "no vivo con mi pareja", "we do not live together", "we don't live together")):
        return None
    if any(phrase in lower for phrase in ("vivo solo", "vivo sola", "i live alone")):
        return "solo"
    if any(phrase in lower for phrase in ("vivo con mi pareja", "vivimos juntos", "we live together", "live with my partner")):
        return "pareja"
    if any(phrase in lower for phrase in ("vivo con mis padres", "vivo con mi madre", "vivo con mi padre", "vivo con mi familia")):
        return "familia"
    if any(phrase in lower for phrase in ("vivo con amigos", "vivo con roommates", "vivo con companeros", "vivo con compañeros", "i live with roommates")):
        return "compartida"
    return None


def _has_children_signal(lower: str) -> bool:
    if any(phrase in lower for phrase in ("soy padre", "soy madre", "i have kids", "i have children")):
        return True
    return bool(re.search(r"\b(?:tengo|tenemos)\s+[^.,;!?]{0,40}\b(?:hijo|hija|hijos|hijas)\b", lower))


def _detect_children_detail(text: str) -> Optional[str]:
    if any(phrase in text.lower() for phrase in ("no tengo hijos", "no tenemos hijos", "i don't have kids", "i do not have children")):
        return None
    patterns = (
        r"\b(?:tengo|tenemos)\s+([^.,;!?]*(?:hijo|hija|hijos|hijas)[^.,;!?]*)",
        r"\b(?:mi hijo|mi hija|mis hijos|mis hijas)\s+([^.,;!?]+)",
        r"\b(?:i have|we have)\s+([^.,;!?]*(?:kid|kids|child|children|son|daughter)[^.,;!?]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_short_fact(match.group(0), max_words=16)
    return None


def _detect_ex_context(text: str) -> Optional[str]:
    lower = text.lower()
    if not any(term in lower for term in ("mi ex", "ex pareja", "ex novia", "ex novio", "my ex", "ex partner")):
        return None
    for segment in re.split(r"(?<=[.!?])\s+|[;]", text):
        segment_lower = segment.lower()
        if any(term in segment_lower for term in ("mi ex", "ex pareja", "ex novia", "ex novio", "my ex", "ex partner")):
            return _clean_short_fact(segment, max_words=20)
    return _clean_short_fact(text, max_words=20)


def _detect_family_structure(text: str) -> Optional[str]:
    lower = text.lower()
    family_terms = (
        "mi madre", "mi padre", "mis padres", "mi hermano", "mi hermana",
        "mis hermanos", "mi familia", "mi hijo", "mi hija", "mis hijos",
        "my mother", "my father", "my parents", "my brother", "my sister",
        "my family", "my son", "my daughter", "my children",
    )
    factual_terms = (
        "vive", "viven", "vivo con", "tengo", "tenemos", "se llama",
        "estoy a cargo", "cuido", "depende de mi", "depende de mí",
        "lives", "live", "i have", "we have", "i care for",
    )
    if not any(term in lower for term in family_terms):
        return None
    if not any(term in lower for term in factual_terms):
        return None
    return _clean_short_fact(text, max_words=22)


def _clean_short_fact(value: str, max_words: int = 12) -> str:
    cleaned = " ".join(value.strip(" .,;:!?").split())
    words = cleaned.split()
    if len(words) > max_words:
        cleaned = " ".join(words[:max_words])
    return cleaned


def _clean_work_fact(value: str) -> str:
    cleaned = re.split(
        r"\s+(?:y vivo|y vivimos|and i live|and we live)\b",
        value.strip(" .,;:!?"),
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return _clean_short_fact(cleaned, max_words=10)


def _detect_user_attachment_style(lower: str) -> Optional[str]:
    patterns = (
        r"\b(?:mi estilo de apego es|mi apego es|soy de apego|creo que soy de apego|creo que soy|i think i am|my attachment style is)\s+([a-záéíóúñ_-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            style = _normalize_attachment_style(match.group(1))
            if style:
                return style
    return None


def _detect_partner_attachment_style(lower: str) -> Optional[str]:
    patterns = (
        r"\b(?:mi pareja|mi novia|mi novio|mi mujer|mi marido|mi esposa|mi esposo)\s+(?:es|sea|parece|se muestra|tiene apego|creo que es|creo que tiene apego|quizas es|quizás es)\s+([a-záéíóúñ_-]+)",
        r"\b(?:my partner|my girlfriend|my boyfriend|my wife|my husband)\s+(?:is|seems|has attachment|i think is)\s+([a-z_-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            style = _normalize_attachment_style(match.group(1))
            if style:
                return style
    return None


def _normalize_attachment_style(value: str) -> Optional[str]:
    lower = value.lower().strip(" .,;:!?")
    if lower in ("desorganizado", "desorganizada", "disorganized"):
        return "disorganized"
    if lower in ("evitativo", "evitativa", "avoidant"):
        return "avoidant"
    if lower in ("ansioso", "ansiosa", "anxious"):
        return "anxious"
    if lower in ("seguro", "segura", "secure"):
        return "secure"
    return None


def _detect_relationship_status(
    user_attachment: object,
    partner_attachment: object,
) -> Optional[str]:
    pair = {str(user_attachment or ""), str(partner_attachment or "")}
    if "anxious" in pair and "avoidant" in pair:
        return "anxious_avoidant_dynamic"
    if "disorganized" in pair:
        return "disorganized_dynamic"
    if pair == {"secure"}:
        return "secure_dynamic"
    return None
