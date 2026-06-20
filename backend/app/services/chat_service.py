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
from app.services.brain.prompt_composer import compose_brain_prompt
from app.services import state_machine as sm
from app.services import test_service
from app.data.test_questions import get_style_description, get_relationship_description

# Guest message limit
GUEST_MESSAGE_LIMIT = 15

# Track guest message counts (in-memory, resets on restart)
_guest_counts: Dict[str, int] = {}


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
        return ChatResponse(
            type="conversation",
            data={"message": _get_greeting_message(language)},
            language=language,
        )

    # Load user state
    current_state = await _get_current_state(db, user_id)
    profile = await _get_profile(db, user_id) if user else None
    message = request.message.strip()

    # Route based on state
    if current_state == sm.ChatState.GREETING:
        response = await _handle_greeting(db, user_id, message, language, profile)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state)

    if sm.is_test_state(current_state):
        response = await _handle_test_answer(db, user_id, current_state, message, language)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state)

    if current_state == sm.ChatState.SELF_RESULTS:
        response = await _handle_post_results(db, user_id, message, language, user)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state)

    if current_state == sm.ChatState.PARTNER_OFFER:
        response = await _handle_partner_offer(db, user_id, message, language)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state)

    if current_state == sm.ChatState.PARTNER_RESULTS:
        response = await _handle_partner_results(db, user_id, language)
        return _attach_state_debug(response, request.debug, message, language, user_id, current_state)

    if current_state == sm.ChatState.PAYWALL:
        # User is at paywall, check if they should proceed
        if user and user.is_premium:
            await _set_state(db, user_id, sm.ChatState.CONVERSATION)
            current_state = sm.ChatState.CONVERSATION
        else:
            response = ChatResponse(
                type="paywall",
                data={"message": _get_paywall_message(language)},
                language=language,
            )
            return _attach_state_debug(response, request.debug, message, language, user_id, current_state)

    # Default: conversation mode with AI
    return await _handle_conversation(db, user_id, message, language, profile, request.debug, current_state)


async def _handle_greeting(
    db: AsyncSession, user_id: str, message: str, language: str, profile: Optional[UserProfile]
) -> ChatResponse:
    """Handle the initial greeting state."""
    # If user sends a valid choice (A/B/C), advance the state
    choice_upper = message.strip().upper()[:1]
    if choice_upper in ("A", "B", "C"):
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
            data={"message": _get_chat_start_message(language, profile)},
            language=language,
        )

    # No valid choice yet — show the welcome message with options
    return ChatResponse(
        type="greeting",
        data={
            "message": _get_welcome_message(language, profile),
            "options": [
                {"id": "A", "text": _t("take_test", language)},
                {"id": "B", "text": _t("chat_now", language)},
                {"id": "C", "text": _t("learn_more", language)},
            ],
            "is_first_visit": True,
        },
        language=language,
    )


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
        if profile.attachment_style:
            context_parts.append(f"Su estilo de apego es: {profile.attachment_style}.")
        if profile.nombre_pareja:
            context_parts.append(f"Su pareja se llama {profile.nombre_pareja}.")
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

    captured_memories = await capture_candidate_memories(db, user_id, message, language) if debug else []

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
            "stage": "memory_capture",
            "title": "Candidate memories captured",
            "detail": f"{len(captured_memories)} candidate memories were written to the user memory brain.",
            "payload": {"candidates": captured_memories},
        })
        data["debug"] = trace

    return ChatResponse(
        type="conversation",
        data=data,
        language=language,
    )


# --- Helper functions ---

async def _get_current_state(db: AsyncSession, user_id: str) -> str:
    result = await db.execute(
        select(TestState.state).where(TestState.user_id == user_id).order_by(TestState.created_at.desc())
    )
    row = result.first()
    return row[0] if row else sm.ChatState.GREETING


async def _set_state(db: AsyncSession, user_id: str, state: str) -> None:
    result = await db.execute(select(TestState).where(TestState.user_id == user_id).order_by(TestState.created_at.desc()))
    test_state = result.scalar_one_or_none()
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
    return response


# --- i18n strings ---

_TRANSLATIONS = {
    "take_test": {"es": "Hacer el test de apego", "en": "Take the attachment test", "ru": "Пройти тест привязанности"},
    "chat_now": {"es": "Prefiero charlar", "en": "I prefer to chat", "ru": "Я предпочитаю поговорить"},
    "learn_more": {"es": "Quiero saber mas sobre el apego", "en": "I want to learn about attachment", "ru": "Хочу узнать о привязанности"},
    "invalid_option": {"es": "Por favor, elige una opcion (A, B, C o D)", "en": "Please choose an option (A, B, C, or D)", "ru": "Пожалуйста, выберите вариант (A, B, C или D)"},
    "partner_test_offer": {"es": "Ahora puedes hacer el test sobre tu pareja para conocer su estilo de apego y la dinamica de tu relacion.", "en": "Now you can take the test about your partner to learn their attachment style and your relationship dynamic.", "ru": "Теперь вы можете пройти тест о вашем партнере."},
    "yes_partner_test": {"es": "Si, quiero hacer el test de mi pareja", "en": "Yes, I want to take the partner test", "ru": "Да, хочу пройти тест партнера"},
    "no_chat_instead": {"es": "No, prefiero charlar", "en": "No, I prefer to chat", "ru": "Нет, предпочитаю поговорить"},
    "lets_chat": {"es": "Perfecto, charlemos! Cuentame, como van las cosas?", "en": "Perfect, let's chat! Tell me, how are things going?", "ru": "Отлично, давай поговорим! Расскажи, как дела?"},
}


def _t(key: str, language: str) -> str:
    return _TRANSLATIONS.get(key, {}).get(language, _TRANSLATIONS.get(key, {}).get("es", key))


def _get_welcome_message(language: str, profile: Optional[UserProfile] = None) -> str:
    name = profile.nombre if profile and profile.nombre else ""
    messages = {
        "es": f"Hola{' ' + name if name else ''}! Soy Eldric, tu coach emocional. Estoy aqui para ayudarte a entender mejor tus relaciones y tu estilo de apego. Que te gustaria hacer?",
        "en": f"Hi{' ' + name if name else ''}! I'm Eldric, your emotional coach. I'm here to help you better understand your relationships and attachment style. What would you like to do?",
        "ru": f"Привет{' ' + name if name else ''}! Я Эльдрик, ваш эмоциональный коуч. Я здесь, чтобы помочь вам лучше понять ваши отношения. Что бы вы хотели сделать?",
    }
    return messages.get(language, messages["es"])


def _get_chat_start_message(language: str, profile: Optional[UserProfile] = None) -> str:
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
