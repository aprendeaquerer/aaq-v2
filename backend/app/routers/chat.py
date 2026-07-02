from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_optional_user
from app.models.user import User
from app.schemas.message import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/session", response_model=ChatResponse)
async def get_session(
    language: str = Query("es"),
    guest_id: Optional[str] = Query(None),
    debug: bool = Query(False),
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.chat_service import handle_session
    return await handle_session(db, user, language=language, guest_id=guest_id, debug=debug)


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.chat_service import handle_message
    return await handle_message(db, user, request)


@router.post("/reset", response_model=ChatResponse)
async def reset_session(
    guest_id: Optional[str] = Query(None),
    user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.chat_service import handle_reset
    return await handle_reset(db, user, guest_id=guest_id)
