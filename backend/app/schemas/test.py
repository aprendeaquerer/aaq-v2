from typing import List, Optional

from pydantic import BaseModel


class TestOption(BaseModel):
    id: str  # "A", "B", "C", "D"
    text: str


class TestQuestionResponse(BaseModel):
    question_number: int
    total_questions: int
    question_text: str
    options: List[TestOption]
    test_type: str = "self"


class TestAnswerRequest(BaseModel):
    question_number: int
    option_id: str  # "A", "B", "C", "D"
    test_type: str = "self"


class AttachmentScores(BaseModel):
    secure: float
    anxious: float
    avoidant: float
    disorganized: float


class TestResultsResponse(BaseModel):
    attachment_style: str
    scores: AttachmentScores
    description: str
    test_type: str = "self"
