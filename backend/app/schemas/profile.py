from typing import Optional

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    nombre: Optional[str] = None
    edad: Optional[int] = None
    tiene_pareja: Optional[bool] = None
    nombre_pareja: Optional[str] = None
    tiempo_pareja: Optional[str] = None
    attachment_style: Optional[str] = None
    partner_attachment_style: Optional[str] = None
    relationship_status: Optional[str] = None
    preferred_language: str = "es"
    is_premium: bool = False
    email_verified: bool = False


class UserProfileUpdate(BaseModel):
    nombre: Optional[str] = None
    edad: Optional[int] = None
    tiene_pareja: Optional[bool] = None
    nombre_pareja: Optional[str] = None
    tiempo_pareja: Optional[str] = None
    preferred_language: Optional[str] = None
