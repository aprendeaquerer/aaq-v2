from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UserMemoryResponse(BaseModel):
    id: str
    type: str
    summary: str
    curated_summary: Optional[str] = None
    visibility: str
    sensitivity: str
    confidence: float
    status: str
    created_at: datetime
    updated_at: datetime


class UserMemoryListResponse(BaseModel):
    memories: List[UserMemoryResponse]


class UserMemoryUpdate(BaseModel):
    curated_summary: Optional[str] = None
    visibility: Optional[str] = None
    status: Optional[str] = None
