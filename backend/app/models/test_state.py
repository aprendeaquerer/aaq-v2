from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, generate_uuid, utcnow


class TestState(Base):
    __tablename__ = "test_states"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    test_type: Mapped[str] = mapped_column(String, nullable=False, default="self")  # "self" or "partner"
    state: Mapped[str] = mapped_column(String, nullable=False, default="greeting")
    answers: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")  # JSON string
    scores: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
