"""promote_direct_fact_memories

Revision ID: b7c2d9e8f104
Revises: 9f1d2e3c4b5a
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7c2d9e8f104"
down_revision: Union[str, None] = "9f1d2e3c4b5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE user_memories
        SET confidence = 1.0,
            status = 'active'
        WHERE type IN ('profile_fact', 'relationship_context', 'important_person')
          AND (
            summary LIKE 'The user''s name is %'
            OR summary LIKE 'The user is % years old.'
            OR summary LIKE 'The user''s partner is named %'
            OR summary LIKE 'The user''s partner is % years old.'
            OR summary LIKE 'The user mentioned % named %'
          )
        """
    )


def downgrade() -> None:
    pass
