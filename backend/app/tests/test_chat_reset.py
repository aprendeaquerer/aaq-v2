"""Tests for handle_reset ("Reiniciar memoria" in the demo UI).

Regression coverage for a bug reported 2026-08-08: the button always failed with a
500. The old implementation ran every table's delete in a single transaction with
one commit at the end — if any single delete raised, nothing committed and the
whole request crashed with no memory actually cleared. These tests pin the fixed
behaviour: each table is deleted and committed independently, so one bad table
can't block the others, and the response always reports what happened instead of
crashing.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models import affirmation, coaching_plan, conversation, test_state, user, user_memory  # noqa: F401
from app.models.coaching_plan import CoachingPlan
from app.models.conversation import Conversation
from app.models.test_state import TestState
from app.models.user_memory import UserMemory
from app.services.chat_service import handle_reset


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


async def _seed(db: AsyncSession, user_id: str) -> None:
    db.add(UserMemory(user_id=user_id, type="fact", summary="le gusta el senderismo"))
    db.add(Conversation(user_id=user_id, role="user", content="hola"))
    db.add(CoachingPlan(user_id=user_id, plan_json="{}"))
    db.add(TestState(user_id=user_id, test_type="self", state="greeting"))
    await db.commit()


@pytest.mark.asyncio
async def test_reset_without_user_id_is_a_no_op(db_session: AsyncSession):
    response = await handle_reset(db_session, None, guest_id=None)

    assert response.data == {"success": False, "reason": "no_user"}


@pytest.mark.asyncio
async def test_reset_clears_every_table_for_a_guest(db_session: AsyncSession):
    guest_id = "guest_test_1"
    await _seed(db_session, guest_id)

    response = await handle_reset(db_session, None, guest_id=guest_id)

    assert response.data == {"success": True}
    for model in (UserMemory, Conversation, CoachingPlan, TestState):
        remaining = (await db_session.execute(select(model).where(model.user_id == guest_id))).scalars().all()
        assert remaining == []


@pytest.mark.asyncio
async def test_reset_survives_one_table_failing(db_session: AsyncSession, monkeypatch):
    """One broken table (a stray type/constraint mismatch, a schema drift — this app's
    tables were built across several migration generations) must not stop the others
    from being cleared, and must not surface as an opaque 500."""
    guest_id = "guest_test_2"
    await _seed(db_session, guest_id)

    real_execute = db_session.execute

    async def flaky_execute(statement, *args, **kwargs):
        table = getattr(statement, "table", None)
        if table is not None and table.name == "test_states":
            raise RuntimeError("simulated schema drift on test_states")
        return await real_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db_session, "execute", flaky_execute)

    response = await handle_reset(db_session, None, guest_id=guest_id)

    assert response.data["success"] is False
    assert response.data["failed_tables"] == ["test_states"]

    # The tables that didn't fail were still cleared — this is the actual fix.
    monkeypatch.undo()
    for model in (UserMemory, Conversation, CoachingPlan):
        remaining = (await db_session.execute(select(model).where(model.user_id == guest_id))).scalars().all()
        assert remaining == []
    # The one that failed is untouched, not half-deleted.
    remaining_states = (
        (await db_session.execute(select(TestState).where(TestState.user_id == guest_id))).scalars().all()
    )
    assert len(remaining_states) == 1
