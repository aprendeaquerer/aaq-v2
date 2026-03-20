from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid, utcnow


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    verification_code_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String, default="es")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    profile: Mapped[Optional["UserProfile"]] = relationship(back_populates="user", uselist=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), unique=True, nullable=False)
    nombre: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    edad: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tiene_pareja: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    nombre_pareja: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tiempo_pareja: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    attachment_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    partner_attachment_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    relationship_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_conversation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_affirmation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    affirmation_index: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")

    user: Mapped["User"] = relationship(back_populates="profile")
