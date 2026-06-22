"""Chat service - orchestrates state machine, AI calls, knowledge injection, and conversation persistence."""

import json
from typing import Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.test_state import TestState
from app.models.user import User, UserProfile
from app.schemas.message import ChatRequest, ChatResponse
from app.services.ai.factory import get_ai_provider
from app.services.ai.prompts import get_eldric_prompt
from app.services.brain import build_brain_context
from app.services.brain.debug_trace import build_conversation_debug, build_state_debug
from app.services.brain.memory_capture import capture_candidate_memories
from app.services.brain.profile_capture import capture_profile_fields
from app.services.brain.prompt_composer import compose_brain_prompt
from app.services import state_machine as sm
from app.services import test_service
from app.data.test_questions import get_style_description, get_relationship_description

# Guest message limit
GUEST_MESSAGE_LIMIT = 15

# Track guest message counts (in-memory, resets on restart)
_guest_counts: Dict[str, int] = {}


async def handle_session(
    db: AsyncSession,
    user: Optional[User],
    language: str = "es",
    guest_id: Optional[str] = None,
    debug: bool = False,
) -> ChatResponse:
    """Return the opening UI state without creating a chat message."""
    user_id = user.user_id if user else guest_id
    profile = await _get_profile(db, user_id) if user and user_id else None

    if not user_id:
        response = _build_greeting_response(language, profile)
        return _attach_state_debug(response, debug, "session_start", language, user_id, sm.ChatState.GREETING)

    current_state = await _get_current_state(db, user_id)
    if current_state == sm.ChatState.GREETING:
        response = _build_greeting_response(language, profile)
        return _attach_state_debug(response, debug, "session_start", language, user_id, current_state)

    history = await _load_history(db, user_id, limit=30)
    response = ChatResponse(
        type="session",
        data={
            "state": current_state,
            "message": "",
            "recap_message": _build_session_recap(history, language),
            "history_count": len(history),
        },
        language=language,
    )
    return _attach_state_debug(response, debug, "session_resume", language, user_id, current_state)


async def handle_message(db: AsyncSession, user: Optional[User], request: ChatRequest) -> ChatResponse:
    """Main chat orchestrator."""
    language = request.language or "es"
    user_id = user.user_id if user else request.guest_id

    # Enforce guest limit
    if not user and user_id:
        _guest_counts.setdefault(user_id, 0)
        _guest_counts[user_id] += 1
        if _guest_counts[user_id] > GUEST_MESSAGE_LIMIT:
            return ChatResponse(
                type="paywall",
                data={
                    "message": _get_guest_limit_message(language),
                    "reason": "guest_limit",
                },
                language=language,
            )

    if not user_id:
        return _build_greeting_response(language)

    # Load user state
    current_state = await _get_current_state(db, user_id)
    profile = await _get_profile(db, user_id) if user else None
    message = request.message.strip()

    if _is_initial_greeting_message(message):
        response = await _handle_greeting(db, user_id, "", language, profile)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state)

    # Route based on state
    if current_state == sm.ChatState.GREETING:
        if _is_greeting_choice(message):
            response = await _handle_greeting(db, user_id, message, language, profile)
            return _attach_state_debug(response, request.debug, message, language, user_id, current_state)
        await _set_state(db, user_id, sm.ChatState.CONVERSATION)
        return await _handle_conversation(db, user_id, message, language, profile, request.debug, current_state)

    if sm.is_test_state(current_state):
        capture_info = await _capture_guided_message_data(db, user_id, message, language)
        response = await _handle_test_answer(db, user_id, current_state, message, language)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state, capture_info)

    if current_state == sm.ChatState.SELF_RESULTS:
        capture_info = await _capture_guided_message_data(db, user_id, message, language)
        response = await _handle_post_results(db, user_id, message, language, user)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state, capture_info)

    if current_state == sm.ChatState.PARTNER_OFFER:
        capture_info = await _capture_guided_message_data(db, user_id, message, language)
        response = await _handle_partner_offer(db, user_id, message, language)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state, capture_info)

    if current_state == sm.ChatState.PARTNER_RESULTS:
        response = await _handle_partner_results(db, user_id, language)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state)

    if current_state == sm.ChatState.PAYWALL:
        # User is at paywall, check if they should proceed
        if user and user.is_premium:
            await _set_state(db, user_id, sm.ChatState.CONVERSATION)
            current_state = sm.ChatState.CONVERSATION
        else:
            capture_info = await _capture_guided_message_data(db, user_id, message, language)
            response = ChatResponse(
                type="paywall",
                data={"message": _get_paywall_message(language)},
                language=language,
            )
            return _attach_state_debug(response, request.debug, message, language, user_id, current_state, capture_info)

    # Default: conversation mode with AI
    return await _handle_conversation(db, user_id, message, language, profile, request.debug, current_state)


async def _handle_greeting(
    db: AsyncSession, user_id: str, message: str, language: str, profile: Optional[UserProfile]
) -> ChatResponse:
    """Handle the initial greeting state."""
    # If user sends a valid choice (A-D), move into conversation with a tailored opening.
    choice_upper = message.strip().upper()[:1]
    if choice_upper in ("A", "B", "C", "D"):
        next_state = sm.get_greeting_next_state(message)
        await _set_state(db, user_id, next_state)

        if next_state == sm.ChatState.SELF_Q1:
            question = test_service.get_question(1, "self", language)
            return ChatResponse(
                type="test_question",
                data={
                    "question_number": 1,
                    "total_questions": 10,
                    "question_text": question["question"],
                    "options": question["options"],
                    "test_type": "self",
                },
                language=language,
            )

        # Chat mode
        return ChatResponse(
            type="conversation",
            data={"message": _get_chat_start_message(language, profile, choice_upper)},
            language=language,
        )

    # No valid choice yet — show the welcome message with options
    return _build_greeting_response(language, profile)


async def _handle_test_answer(
    db: AsyncSession, user_id: str, current_state: str, message: str, language: str
) -> ChatResponse:
    """Handle a test question answer and advance to next question or results."""
    if not sm.is_valid_option(message):
        q_num = sm.get_question_number(current_state)
        test_type = "self" if sm.is_self_test(current_state) else "partner"
        question = test_service.get_question(q_num, test_type, language)
        return ChatResponse(
            type="test_question",
            data={
                "question_number": q_num,
                "total_questions": 10,
                "question_text": question["question"],
                "options": question["options"],
                "test_type": test_type,
                "error": _t("invalid_option", language),
            },
            language=language,
        )

    option_id = sm.extract_option_id(message)
    q_num = sm.get_question_number(current_state)
    test_type = "self" if sm.is_self_test(current_state) else "partner"

    # Save the answer
    answers = await _get_test_answers(db, user_id, test_type)
    answers[f"q{q_num}"] = option_id
    await _save_test_answers(db, user_id, test_type, answers)

    # Get next state
    next_state = sm.get_next_test_state(current_state)
    await _set_state(db, user_id, next_state)

    # If results, calculate and return
    if next_state in (sm.ChatState.SELF_RESULTS, sm.ChatState.PARTNER_RESULTS):
        style, scores = await test_service.save_test_results(db, user_id, test_type, answers, language)
        description = get_style_description(style, language)

        return ChatResponse(
            type="test_results",
            data={
                "attachment_style": style,
                "scores": scores,
                "description": description,
                "test_type": test_type,
            },
            language=language,
        )

    # Next question
    next_q_num = sm.get_question_number(next_state)
    question = test_service.get_question(next_q_num, test_type, language)
    return ChatResponse(
        type="test_question",
        data={
            "question_number": next_q_num,
            "total_questions": 10,
            "question_text": question["question"],
            "options": question["options"],
            "test_type": test_type,
        },
        language=language,
    )


async def _handle_post_results(
    db: AsyncSession, user_id: str, message: str, language: str, user: Optional[User]
) -> ChatResponse:
    """Handle state after self-test results - offer partner test or move to conversation."""
    if user and user.is_premium:
        await _set_state(db, user_id, sm.ChatState.PARTNER_OFFER)
        return ChatResponse(
            type="partner_offer",
            data={
                "message": _t("partner_test_offer", language),
                "options": [
                    {"id": "A", "text": _t("yes_partner_test", language)},
                    {"id": "B", "text": _t("no_chat_instead", language)},
                ],
            },
            language=language,
        )

    # Non-premium: show paywall
    await _set_state(db, user_id, sm.ChatState.CONVERSATION)
    return ChatResponse(
        type="paywall",
        data={"message": _get_paywall_message(language)},
        language=language,
    )


async def _handle_partner_offer(
    db: AsyncSession, user_id: str, message: str, language: str
) -> ChatResponse:
    """Handle partner test offer response."""
    choice = message.strip().upper()[:1]
    if choice == "A":
        await _set_state(db, user_id, sm.ChatState.PARTNER_Q1)
        question = test_service.get_question(1, "partner", language)
        return ChatResponse(
            type="test_question",
            data={
                "question_number": 1,
                "total_questions": 10,
                "question_text": question["question"],
                "options": question["options"],
                "test_type": "partner",
            },
            language=language,
        )

    await _set_state(db, user_id, sm.ChatState.CONVERSATION)
    return ChatResponse(
        type="conversation",
        data={"message": _t("lets_chat", language)},
        language=language,
    )


async def _handle_partner_results(
    db: AsyncSession, user_id: str, language: str
) -> ChatResponse:
    """Handle partner test results and show relationship dynamic."""
    profile = await _get_profile(db, user_id)
    rel_status = profile.relationship_status if profile else "unknown"
    description = get_relationship_description(rel_status, language)

    await _set_state(db, user_id, sm.ChatState.CONVERSATION)

    return ChatResponse(
        type="test_results",
        data={
            "attachment_style": profile.partner_attachment_style if profile else "unknown",
            "relationship_status": rel_status,
            "relationship_description": description,
            "test_type": "partner",
        },
        language=language,
    )


async def _handle_conversation(
    db: AsyncSession,
    user_id: str,
    message: str,
    language: str,
    profile: Optional[UserProfile],
    debug: bool = False,
    current_state: str = sm.ChatState.CONVERSATION,
) -> ChatResponse:
    """Handle free conversation with AI."""
    # Save user message
    await _save_message(db, user_id, "user", message, language)
    profile_updates = {}
    profile_capture_error = None
    try:
        profile_updates = await capture_profile_fields(db, user_id, message)
    except Exception as exc:
        await db.rollback()
        profile_capture_error = f"{type(exc).__name__}: {str(exc)[:300]}"

    if profile_updates:
        profile = await _get_profile(db, user_id)

    # Load conversation history
    history = await _load_history(db, user_id, limit=50)
    history_characters = sum(len(msg["content"]) for msg in history)

    # Retrieve file-backed knowledge brain and database-backed user memory brain
    brain_context = await build_brain_context(db, user_id, message, language)

    # Build system prompt
    base_prompt = get_eldric_prompt(language)

    # Add user context to prompt
    if profile:
        context_parts = []
        if profile.nombre:
            context_parts.append(f"El usuario se llama {profile.nombre}.")
        if profile.edad:
            context_parts.append(f"Edad del usuario: {profile.edad}.")
        if profile.genero:
            context_parts.append(f"Genero del usuario: {profile.genero}.")
        if profile.attachment_style:
            context_parts.append(f"Su estilo de apego es: {profile.attachment_style}.")
        if profile.tiene_pareja is not None:
            context_parts.append(f"Tiene pareja: {'si' if profile.tiene_pareja else 'no'}.")
        if profile.nombre_pareja:
            context_parts.append(f"Su pareja se llama {profile.nombre_pareja}.")
        if profile.edad_pareja:
            context_parts.append(f"Edad de su pareja: {profile.edad_pareja}.")
        if profile.genero_pareja:
            context_parts.append(f"Genero de su pareja: {profile.genero_pareja}.")
        if profile.tiempo_pareja:
            context_parts.append(f"Tiempo de relacion: {profile.tiempo_pareja}.")
        if profile.orientacion:
            context_parts.append(f"Orientacion del usuario: {profile.orientacion}.")
        if profile.tipo_relacion:
            context_parts.append(f"Tipo de relacion: {profile.tipo_relacion}.")
        if profile.convive_con_pareja is not None:
            context_parts.append(f"Convive con su pareja: {'si' if profile.convive_con_pareja else 'no'}.")
        if profile.tiene_hijos is not None:
            context_parts.append(f"Tiene hijos: {'si' if profile.tiene_hijos else 'no'}.")
        if profile.partner_attachment_style:
            context_parts.append(f"El estilo de apego de su pareja es: {profile.partner_attachment_style}.")
        if profile.relationship_status and profile.relationship_status != "unknown":
            context_parts.append(f"Dinamica de relacion: {profile.relationship_status}.")
        if context_parts:
            base_prompt += "\n\nCONTEXTO DEL USUARIO:\n" + "\n".join(context_parts)

    system_prompt = compose_brain_prompt(base_prompt, brain_context)

    # Call AI
    ai = get_ai_provider()
    ai_error = None
    try:
        response_text = await ai.chat(
            system_prompt=system_prompt,
            messages=history,
            temperature=0.7,
            max_tokens=1000,
        )
    except Exception as exc:
        ai_error = f"{type(exc).__name__}: {str(exc)[:500]}"
        response_text = _get_ai_error_message(language)

    # Save assistant message
    await _save_message(db, user_id, "assistant", response_text, language)

    captured_memories = []
    memory_capture_error = None
    try:
        captured_memories = await capture_candidate_memories(db, user_id, message, language)
    except Exception as exc:
        await db.rollback()
        memory_capture_error = f"{type(exc).__name__}: {str(exc)[:300]}"

    data = {"message": response_text}
    if debug:
        trace = build_conversation_debug(
            user_message=message,
            language=language,
            user_id=user_id,
            current_state=current_state,
            history_count=len(history),
            history_characters=history_characters,
            brain_context=brain_context,
            system_prompt=system_prompt,
            response_text=response_text,
            ai_error=ai_error,
        )
        trace["steps"].append({
            "stage": "profile_capture",
            "title": "Structured profile fields captured",
            "detail": (
                f"{len(profile_updates)} structured profile fields were updated from the user message."
                if not profile_capture_error
                else "Profile capture failed, so the chat response continued without profile updates."
            ),
            "payload": {"updates": profile_updates, "error": profile_capture_error},
        })
        trace["steps"].append({
            "stage": "memory_capture",
            "title": "Memory candidates captured or reinforced",
            "detail": (
                f"{len(captured_memories)} memory candidates were created or reinforced in the user memory brain."
                if not memory_capture_error
                else "Memory capture failed, so the chat response continued without new memories."
            ),
            "payload": {"candidates": captured_memories, "error": memory_capture_error},
        })
        data["debug"] = trace

    return ChatResponse(
        type="conversation",
        data=data,
        language=language,
    )


# --- Helper functions ---

async def _capture_guided_message_data(
    db: AsyncSession,
    user_id: str,
    message: str,
    language: str,
) -> Dict[str, object]:
    profile_updates = {}
    profile_capture_error = None
    memory_candidates = []
    memory_capture_error = None

    try:
        profile_updates = await capture_profile_fields(db, user_id, message)
    except Exception as exc:
        await db.rollback()
        profile_capture_error = f"{type(exc).__name__}: {str(exc)[:300]}"

    try:
        memory_candidates = await capture_candidate_memories(db, user_id, message, language)
    except Exception as exc:
        await db.rollback()
        memory_capture_error = f"{type(exc).__name__}: {str(exc)[:300]}"

    return {
        "profile_updates": profile_updates,
        "profile_capture_error": profile_capture_error,
        "memory_candidates": memory_candidates,
        "memory_capture_error": memory_capture_error,
    }

async def _get_current_state(db: AsyncSession, user_id: str) -> str:
    result = await db.execute(
        select(TestState.state).where(TestState.user_id == user_id).order_by(TestState.created_at.desc())
    )
    row = result.first()
    return row[0] if row else sm.ChatState.GREETING


async def _set_state(db: AsyncSession, user_id: str, state: str) -> None:
    result = await db.execute(select(TestState).where(TestState.user_id == user_id).order_by(TestState.created_at.desc()))
    test_state = result.scalars().first()
    if test_state:
        test_state.state = state
    else:
        test_state = TestState(user_id=user_id, state=state)
        db.add(test_state)
    await db.commit()


async def _get_test_answers(db: AsyncSession, user_id: str, test_type: str) -> dict:
    result = await db.execute(
        select(TestState).where(TestState.user_id == user_id, TestState.test_type == test_type)
    )
    ts = result.scalar_one_or_none()
    if ts and ts.answers:
        return json.loads(ts.answers)
    return {}


async def _save_test_answers(db: AsyncSession, user_id: str, test_type: str, answers: dict) -> None:
    result = await db.execute(
        select(TestState).where(TestState.user_id == user_id, TestState.test_type == test_type)
    )
    ts = result.scalar_one_or_none()
    if ts:
        ts.answers = json.dumps(answers)
    else:
        ts = TestState(user_id=user_id, test_type=test_type, answers=json.dumps(answers))
        db.add(ts)
    await db.commit()


async def _count_messages(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
    )
    return result.scalar() or 0


async def _save_message(db: AsyncSession, user_id: str, role: str, content: str, language: str) -> None:
    msg = Conversation(user_id=user_id, role=role, content=content)
    db.add(msg)
    await db.commit()


async def _load_history(db: AsyncSession, user_id: str, limit: int = 50) -> List[Dict[str, str]]:
    result = await db.execute(
        select(Conversation.role, Conversation.content)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.timestamp.desc())
        .limit(limit)
    )
    rows = result.all()
    # Reverse to chronological order
    messages = [{"role": row.role, "content": row.content} for row in reversed(rows)]
    # Cap total characters
    total = 0
    trimmed = []
    for msg in reversed(messages):
        total += len(msg["content"])
        if total > 8000:
            break
        trimmed.insert(0, msg)
    return trimmed


async def _get_profile(db: AsyncSession, user_id: str) -> Optional[UserProfile]:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    return result.scalar_one_or_none()


def _attach_state_debug(
    response: ChatResponse,
    debug: bool,
    message: str,
    language: str,
    user_id: Optional[str],
    current_state: str,
    capture_info: Optional[Dict[str, object]] = None,
) -> ChatResponse:
    if not debug:
        return response
    response.data["debug"] = build_state_debug(
        user_message=message,
        language=language,
        user_id=user_id,
        current_state=current_state,
        response_type=response.type,
    )
    if capture_info:
        response.data["debug"]["steps"].append({
            "stage": "profile_capture",
            "title": "Structured profile fields captured",
            "detail": (
                f"{len(capture_info.get('profile_updates') or {})} structured profile fields were updated from the user message."
                if not capture_info.get("profile_capture_error")
                else "Profile capture failed, so the guided response continued without profile updates."
            ),
            "payload": {
                "updates": capture_info.get("profile_updates") or {},
                "error": capture_info.get("profile_capture_error"),
            },
        })
        response.data["debug"]["steps"].append({
            "stage": "memory_capture",
            "title": "Memory candidates captured or reinforced",
            "detail": (
                f"{len(capture_info.get('memory_candidates') or [])} memory candidates were created or reinforced in the user memory brain."
                if not capture_info.get("memory_capture_error")
                else "Memory capture failed, so the guided response continued without new memories."
            ),
            "payload": {
                "candidates": capture_info.get("memory_candidates") or [],
                "error": capture_info.get("memory_capture_error"),
            },
        })
    return response


def _build_session_recap(history: List[Dict[str, str]], language: str) -> str:
    user_messages = [
        _shorten_for_recap(message["content"])
        for message in history
        if message.get("role") == "user" and message.get("content")
    ]
    user_messages = [message for message in user_messages if message]
    recent_topics = user_messages[-3:]

    if language == "en":
        if recent_topics:
            topics = "; ".join(recent_topics)
            return (
                "To pick up where we left off: in our last conversation we were talking about "
                f"{topics}. I have that context loaded internally, but I won't paste the whole old "
                "conversation here. Do you want to continue from there, or start with something new?"
            )
        return "I have your previous context loaded. Do you want to continue from where we left off, or start with something new?"

    if language == "ru":
        if recent_topics:
            topics = "; ".join(recent_topics)
            return (
                "Чтобы продолжить с того места, где мы остановились: в прошлый раз мы говорили о "
                f"{topics}. Этот контекст у меня загружен, но я не буду вставлять сюда всю старую "
                "переписку. Хотите продолжить оттуда или начать новую тему?"
            )
        return "У меня загружен предыдущий контекст. Хотите продолжить с того места, где остановились, или начать новую тему?"

    if recent_topics:
        topics = "; ".join(recent_topics)
        return (
            "Para retomar: en nuestra última conversación estuvimos hablando de "
            f"{topics}. Tengo ese contexto cargado internamente, pero no voy a pegar toda la "
            "conversación antigua aquí. ¿Quieres seguir desde ahí o empezar con algo nuevo?"
        )
    return "Tengo cargado tu contexto anterior. ¿Quieres seguir desde donde lo dejamos o empezar con algo nuevo?"


def _shorten_for_recap(content: str, limit: int = 120) -> str:
    normalized = " ".join(content.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _is_initial_greeting_message(message: str) -> bool:
    return message.strip().lower() in {"saludo inicial", "initial greeting"}


def _is_greeting_choice(message: str) -> bool:
    return message.strip().upper()[:1] in {"A", "B", "C", "D"}


# --- i18n strings ---

_TRANSLATIONS = {
    "tell_me_about_you": {"es": "Cuéntame sobre ti", "en": "Tell me about yourself", "ru": "Расскажите мне о себе"},
    "ask_me_questions": {"es": "Hacerme preguntas", "en": "Ask me questions", "ru": "Задать мне вопросы"},
    "share_goals": {"es": "Darme tus objetivos", "en": "Give me your goals", "ru": "Рассказать мне о ваших целях"},
    "just_talk": {"es": "Solo quiero hablar", "en": "I just want to talk", "ru": "Я просто хочу поговорить"},
    "invalid_option": {"es": "Por favor, elige una opcion (A, B, C o D)", "en": "Please choose an option (A, B, C, or D)", "ru": "Пожалуйста, выберите вариант (A, B, C или D)"},
    "partner_test_offer": {"es": "Ahora puedes hacer el test sobre tu pareja para conocer su estilo de apego y la dinamica de tu relacion.", "en": "Now you can take the test about your partner to learn their attachment style and your relationship dynamic.", "ru": "Теперь вы можете пройти тест о вашем партнере."},
    "yes_partner_test": {"es": "Si, quiero hacer el test de mi pareja", "en": "Yes, I want to take the partner test", "ru": "Да, хочу пройти тест партнера"},
    "no_chat_instead": {"es": "No, prefiero charlar", "en": "No, I prefer to chat", "ru": "Нет, предпочитаю поговорить"},
    "lets_chat": {"es": "Perfecto, charlemos! Cuentame, como van las cosas?", "en": "Perfect, let's chat! Tell me, how are things going?", "ru": "Отлично, давай поговорим! Расскажи, как дела?"},
}


def _t(key: str, language: str) -> str:
    return _TRANSLATIONS.get(key, {}).get(language, _TRANSLATIONS.get(key, {}).get("es", key))


def _build_greeting_response(language: str, profile: Optional[UserProfile] = None) -> ChatResponse:
    return ChatResponse(
        type="greeting",
        data={
            "message": _get_welcome_message(language, profile),
            "options": [
                {"id": "A", "text": _t("tell_me_about_you", language)},
                {"id": "B", "text": _t("ask_me_questions", language)},
                {"id": "C", "text": _t("share_goals", language)},
                {"id": "D", "text": _t("just_talk", language)},
            ],
            "is_first_visit": True,
        },
        language=language,
    )


def _get_welcome_message(language: str, profile: Optional[UserProfile] = None) -> str:
    name = profile.nombre if profile and profile.nombre else ""
    es_intro = f"{name}, soy Eldric." if name else "Soy Eldric."
    en_intro = f"{name}, I'm Eldric." if name else "I'm Eldric."
    ru_intro = f"{name}, я Эльдрик." if name else "Я Эльдрик."
    messages = {
        "es": f"{es_intro} Estoy aquí para enseñarte a mejorar tus relaciones, con otras personas y contigo mismo/a. Cuanto más te conozca, más te podré ayudar. ¿Qué quieres hacer ahora?",
        "en": f"{en_intro} I'm here to help you improve your relationships, with other people and with yourself. The more I know you, the more I can help. What would you like to do now?",
        "ru": f"{ru_intro} Я здесь, чтобы помочь вам улучшить отношения с другими людьми и с собой. Чем лучше я вас узнаю, тем точнее смогу помочь. Что вы хотите сделать сейчас?",
    }
    return messages.get(language, messages["es"])


def _get_chat_start_message(language: str, profile: Optional[UserProfile] = None, choice: str = "") -> str:
    name = profile.nombre if profile and profile.nombre else ""
    choice = choice.upper()
    by_choice = {
        "A": {
            "es": f"Me encantará conocerte{' ' + name if name else ''}. Cuéntame lo que sientas importante: quién eres, qué estás viviendo ahora, y qué te gustaría entender o cambiar.",
            "en": f"I'd love to get to know you{' ' + name if name else ''}. Tell me what feels important: who you are, what you're living through, and what you'd like to understand or change.",
            "ru": f"Мне будет радостно узнать вас лучше{' ' + name if name else ''}. Расскажите, что кажется важным: кто вы, что сейчас происходит и что вы хотите понять или изменить.",
        },
        "B": {
            "es": "Claro. Empezamos suave: ¿qué área de tu vida relacional te gustaría entender mejor ahora mismo?",
            "en": "Of course. Let's start gently: what area of your relational life would you like to understand better right now?",
            "ru": "Конечно. Начнем мягко: какую часть вашей жизни в отношениях вы хотите лучше понять прямо сейчас?",
        },
        "C": {
            "es": "Perfecto. Dame tus objetivos en tus palabras. Pueden ser concretos o todavía confusos; yo te ayudo a ordenarlos.",
            "en": "Perfect. Give me your goals in your own words. They can be concrete or still messy; I'll help you organize them.",
            "ru": "Отлично. Расскажите о целях своими словами. Они могут быть конкретными или пока неясными; я помогу их упорядочить.",
        },
        "D": {
            "es": "Estoy contigo. Escribe como te salga, sin tener que ordenarlo perfecto.",
            "en": "I'm with you. Write however it comes out; it doesn't need to be perfectly organized.",
            "ru": "Я с вами. Пишите так, как получается; не нужно сразу все идеально формулировать.",
        },
    }
    if choice in by_choice:
        return by_choice[choice].get(language, by_choice[choice]["es"])

    messages = {
        "es": "Genial! Cuentame, como van las cosas? Estoy aqui para lo que necesites.",
        "en": "Great! Tell me, how are things going? I'm here for whatever you need.",
        "ru": "Отлично! Расскажите, как дела? Я здесь для вас.",
    }
    return messages.get(language, messages["es"])


def _get_guest_limit_message(language: str) -> str:
    messages = {
        "es": "Has alcanzado el limite de mensajes como invitado. Registrate para seguir charlando conmigo!",
        "en": "You've reached the guest message limit. Register to keep chatting with me!",
        "ru": "Вы достигли лимита сообщений для гостей. Зарегистрируйтесь, чтобы продолжить!",
    }
    return messages.get(language, messages["es"])


def _get_paywall_message(language: str) -> str:
    messages = {
        "es": "Para acceder al test de pareja, afirmaciones diarias personalizadas, y chat ilimitado, hazte premium por solo $9.99!",
        "en": "To access the partner test, personalized daily affirmations, and unlimited chat, go premium for just $9.99!",
        "ru": "Для доступа к тесту партнера и персональным аффирмациям оформите премиум за $9.99!",
    }
    return messages.get(language, messages["es"])


def _get_ai_error_message(language: str) -> str:
    messages = {
        "es": "Ahora mismo tengo un problema conectando con el modelo de IA, pero he dejado el proceso en el panel de debug para que puedas verlo.",
        "en": "I'm having trouble connecting to the AI model right now, but I left the process in the debug panel so you can inspect it.",
        "ru": "Сейчас есть проблема с подключением к модели ИИ, но процесс оставлен в панели debug для проверки.",
    }
    return messages.get(language, messages["es"])
