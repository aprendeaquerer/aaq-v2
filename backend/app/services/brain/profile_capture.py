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
    "orientacion",
    "tipo_relacion",
    "convive_con_pareja",
    "tiene_hijos",
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
            r"\b(?:me llamo|mi nombre es|soy)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ][\wáéíóúñ-]+)\b",
            r"\b(?:my name is|i am|i'm)\s+([A-Za-z][\w-]+)\b",
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

    if any(phrase in lower for phrase in ("mi pareja", "mi novia", "mi novio", "my partner", "girlfriend", "boyfriend")):
        updates.setdefault("tiene_pareja", True)

    if any(phrase in lower for phrase in ("vivo con mi pareja", "vivimos juntos", "convivo con", "we live together", "live with my partner")):
        updates["convive_con_pareja"] = True
    if any(phrase in lower for phrase in ("no vivimos juntos", "no vivo con mi pareja", "we do not live together", "we don't live together")):
        updates["convive_con_pareja"] = False

    if any(phrase in lower for phrase in ("tengo hijos", "tenemos hijos", "soy padre", "soy madre", "i have kids", "i have children")):
        updates["tiene_hijos"] = True
    if any(phrase in lower for phrase in ("no tengo hijos", "no tenemos hijos", "i don't have kids", "i do not have children")):
        updates["tiene_hijos"] = False

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
            return _format_name(match.group(1))
    return None


def _format_name(name: str) -> str:
    cleaned = name.strip(" .,;:!?")
    if not cleaned:
        return cleaned
    return cleaned[0].upper() + cleaned[1:]


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
