from typing import Any, Dict, Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    language: str = "es"
    guest_id: Optional[str] = None


class ChatResponse(BaseModel):
    type: str  # "greeting", "test_question", "test_results", "conversation", "paywall", "partner_offer", "affirmation", "collecting_info"
    data: Dict[str, Any]
    language: str = "es"
