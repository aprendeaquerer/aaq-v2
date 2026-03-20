from datetime import datetime

from sqlalchemy import Index, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow


class Knowledge(Base):
    __tablename__ = "knowledge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(Text, nullable=False)
    book: Mapped[str] = mapped_column(String, nullable=True)
    chapter: Mapped[str] = mapped_column(String, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False, default="es")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        Index("ix_knowledge_language_tags", "language", "tags"),
    )
