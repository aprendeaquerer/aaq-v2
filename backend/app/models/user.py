from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid, utcnow


class User(Base):
    __tablename__ = "users"

    # Matches existing production schema: primary key is "user_id"
    user_id: Mapped[str] = mapped_column("user_id", String, primary_key=True, default=generate_uuid)
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email_verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    verification_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    verification_code_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_premium: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    preferred_language: Mapped[Optional[str]] = mapped_column(String, default="es")

    @property
    def id(self) -> str:
        return self.user_id

    profile: Mapped[Optional["UserProfile"]] = relationship(back_populates="user", uselist=False, foreign_keys="UserProfile.user_id")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.user_id"), unique=True, nullable=False)
    nombre: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    edad: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    genero: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tiene_pareja: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    nombre_pareja: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    edad_pareja: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    genero_pareja: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tiempo_pareja: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    orientacion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tipo_relacion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    convive_con_pareja: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    tiene_hijos: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    attachment_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    partner_attachment_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    relationship_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_conversation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_affirmation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    affirmation_index: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")

    user: Mapped["User"] = relationship(back_populates="profile")
