"""add_user_memories

Revision ID: 3c8b7d2a1f49
Revises: 78ae09ec21b6
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "3c8b7d2a1f49"
down_revision: Union[str, None] = "78ae09ec21b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_knowledge_language_tags", table_name="knowledge")
    op.drop_table("knowledge")

    op.create_table(
        "user_memories",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("curated_summary", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(), nullable=False),
        sa.Column("sensitivity", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("source_message_ids", sa.Text(), nullable=True),
        sa.Column("memory_metadata", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_memories_user_id", "user_memories", ["user_id"])
    op.create_index(
        "ix_user_memories_user_status_type",
        "user_memories",
        ["user_id", "status", "type"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_memories_user_status_type", table_name="user_memories")
    op.drop_index("ix_user_memories_user_id", table_name="user_memories")
    op.drop_table("user_memories")
    op.create_table(
        "knowledge",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.Text(), nullable=False),
        sa.Column("book", sa.String(), nullable=True),
        sa.Column("chapter", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_language_tags", "knowledge", ["language", "tags"])
