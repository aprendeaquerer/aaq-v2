from typing import Optional

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    nombre: Optional[str] = None
    edad: Optional[int] = None
    genero: Optional[str] = None
    tiene_pareja: Optional[bool] = None
    nombre_pareja: Optional[str] = None
    edad_pareja: Optional[int] = None
    genero_pareja: Optional[str] = None
    tiempo_pareja: Optional[str] = None
    orientacion: Optional[str] = None
    tipo_relacion: Optional[str] = None
    convive_con_pareja: Optional[bool] = None
    tiene_hijos: Optional[bool] = None
    attachment_style: Optional[str] = None
    partner_attachment_style: Optional[str] = None
    relationship_status: Optional[str] = None
    preferred_language: str = "es"
    is_premium: bool = False
    email_verified: bool = False


class UserProfileUpdate(BaseModel):
    nombre: Optional[str] = None
    edad: Optional[int] = None
    genero: Optional[str] = None
    tiene_pareja: Optional[bool] = None
    nombre_pareja: Optional[str] = None
    edad_pareja: Optional[int] = None
    genero_pareja: Optional[str] = None
    tiempo_pareja: Optional[str] = None
    orientacion: Optional[str] = None
    tipo_relacion: Optional[str] = None
    convive_con_pareja: Optional[bool] = None
    tiene_hijos: Optional[bool] = None
    preferred_language: Optional[str] = None
