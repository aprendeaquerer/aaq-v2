"""Test scoring and management service."""

import json
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.test_questions import (
    PARTNER_TEST_QUESTIONS,
    STYLE_DESCRIPTIONS,
    TEST_QUESTIONS,
    calculate_attachment_style,
    calculate_relationship_status,
    get_relationship_description,
    get_style_description,
)
from app.models.test_state import TestState
from app.models.user import UserProfile


def get_question(question_number: int, test_type: str = "self", language: str = "es") -> Optional[dict]:
    """Get a test question by number (1-10)."""
    questions = TEST_QUESTIONS if test_type == "self" else PARTNER_TEST_QUESTIONS
    lang_questions = questions.get(language, questions.get("es", []))
    if 1 <= question_number <= len(lang_questions):
        return lang_questions[question_number - 1]
    return None


def score_answer(question_number: int, option_id: str, test_type: str = "self", language: str = "es") -> Optional[Dict[str, int]]:
    """Get the scores for a specific answer."""
    question = get_question(question_number, test_type, language)
    if not question:
        return None
    for option in question["options"]:
        if option["id"] == option_id:
            return option["scores"]
    return None


def calculate_total_scores(answers: Dict[str, str], test_type: str = "self", language: str = "es") -> Dict[str, float]:
    """Calculate total attachment style scores from all answers."""
    totals = {"secure": 0, "anxious": 0, "avoidant": 0, "disorganized": 0}
    for q_key, option_id in answers.items():
        try:
            q_num = int(q_key.replace("q", ""))
        except ValueError:
            continue
        scores = score_answer(q_num, option_id, test_type, language)
        if scores:
            for style, value in scores.items():
                # Map "desorganizado" from legacy to "disorganized"
                mapped = "disorganized" if style == "desorganizado" else style
                if mapped in totals:
                    totals[mapped] += value
    return totals


async def save_test_results(
    db: AsyncSession,
    user_id: str,
    test_type: str,
    answers: Dict[str, str],
    language: str = "es",
) -> Tuple[str, Dict[str, float]]:
    """Calculate scores, save to DB, and update user profile."""
    scores = calculate_total_scores(answers, test_type, language)
    style = calculate_attachment_style(scores)

    # Update or create test state
    result = await db.execute(
        select(TestState).where(TestState.user_id == user_id, TestState.test_type == test_type)
    )
    test_state = result.scalar_one_or_none()
    if test_state:
        test_state.answers = json.dumps(answers)
        test_state.scores = json.dumps(scores)
        test_state.state = f"{test_type}_results" if test_type == "self" else "partner_results"
    else:
        test_state = TestState(
            user_id=user_id,
            test_type=test_type,
            state=f"{test_type}_results" if test_type == "self" else "partner_results",
            answers=json.dumps(answers),
            scores=json.dumps(scores),
        )
        db.add(test_state)

    # Update user profile
    profile_result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = profile_result.scalar_one_or_none()
    if profile:
        if test_type == "self":
            profile.attachment_style = style
        else:
            profile.partner_attachment_style = style
            if profile.attachment_style:
                profile.relationship_status = calculate_relationship_status(
                    profile.attachment_style, style
                )

    await db.commit()
    return style, scores
