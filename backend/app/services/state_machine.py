"""Chat state machine - manages transitions between conversation states."""

from enum import Enum
from typing import Optional


class ChatState(str, Enum):
    GREETING = "greeting"
    SELF_Q1 = "self_q1"
    SELF_Q2 = "self_q2"
    SELF_Q3 = "self_q3"
    SELF_Q4 = "self_q4"
    SELF_Q5 = "self_q5"
    SELF_Q6 = "self_q6"
    SELF_Q7 = "self_q7"
    SELF_Q8 = "self_q8"
    SELF_Q9 = "self_q9"
    SELF_Q10 = "self_q10"
    SELF_RESULTS = "self_results"
    PAYWALL = "paywall"
    PARTNER_OFFER = "partner_offer"
    PARTNER_Q1 = "partner_q1"
    PARTNER_Q2 = "partner_q2"
    PARTNER_Q3 = "partner_q3"
    PARTNER_Q4 = "partner_q4"
    PARTNER_Q5 = "partner_q5"
    PARTNER_Q6 = "partner_q6"
    PARTNER_Q7 = "partner_q7"
    PARTNER_Q8 = "partner_q8"
    PARTNER_Q9 = "partner_q9"
    PARTNER_Q10 = "partner_q10"
    PARTNER_RESULTS = "partner_results"
    CONVERSATION = "conversation"


# Map question states to question numbers
SELF_QUESTIONS = [
    ChatState.SELF_Q1, ChatState.SELF_Q2, ChatState.SELF_Q3, ChatState.SELF_Q4,
    ChatState.SELF_Q5, ChatState.SELF_Q6, ChatState.SELF_Q7, ChatState.SELF_Q8,
    ChatState.SELF_Q9, ChatState.SELF_Q10,
]

PARTNER_QUESTIONS = [
    ChatState.PARTNER_Q1, ChatState.PARTNER_Q2, ChatState.PARTNER_Q3, ChatState.PARTNER_Q4,
    ChatState.PARTNER_Q5, ChatState.PARTNER_Q6, ChatState.PARTNER_Q7, ChatState.PARTNER_Q8,
    ChatState.PARTNER_Q9, ChatState.PARTNER_Q10,
]


def is_test_state(state: str) -> bool:
    return state.startswith("self_q") or state.startswith("partner_q")


def is_self_test(state: str) -> bool:
    return state.startswith("self_q")


def is_partner_test(state: str) -> bool:
    return state.startswith("partner_q")


def get_question_number(state: str) -> Optional[int]:
    """Extract question number from state like 'self_q3' -> 3."""
    for prefix in ("self_q", "partner_q"):
        if state.startswith(prefix):
            try:
                return int(state[len(prefix):])
            except ValueError:
                return None
    return None


def get_next_test_state(current_state: str) -> str:
    """Get the next state after answering a test question."""
    q_num = get_question_number(current_state)
    if q_num is None:
        return ChatState.CONVERSATION

    if is_self_test(current_state):
        if q_num >= 10:
            return ChatState.SELF_RESULTS
        return f"self_q{q_num + 1}"
    elif is_partner_test(current_state):
        if q_num >= 10:
            return ChatState.PARTNER_RESULTS
        return f"partner_q{q_num + 1}"

    return ChatState.CONVERSATION


def get_greeting_next_state(user_choice: str) -> str:
    """Determine next state from greeting menu choice."""
    choice = user_choice.strip().upper()
    if choice.startswith(("A", "B", "C", "D")):
        return ChatState.CONVERSATION
    return ChatState.CONVERSATION


def is_valid_option(answer: str) -> bool:
    """Check if the answer starts with a valid option letter."""
    return answer.strip().upper()[:1] in ("A", "B", "C", "D")


def extract_option_id(answer: str) -> str:
    """Extract the option ID (A, B, C, D) from an answer."""
    return answer.strip().upper()[:1]
