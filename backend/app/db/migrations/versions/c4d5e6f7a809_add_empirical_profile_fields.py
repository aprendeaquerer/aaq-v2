"""add_empirical_profile_fields

Revision ID: c4d5e6f7a809
Revises: b7c2d9e8f104
Create Date: 2026-06-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4d5e6f7a809"
down_revision: Union[str, None] = "b7c2d9e8f104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("trabajo_profesion", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("convivencia", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("ex_pareja_relevante", sa.Boolean(), nullable=True))
    op.add_column("user_profiles", sa.Column("ex_pareja_contexto", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("estructura_familiar_relevante", sa.Text(), nullable=True))
    op.add_column("user_profiles", sa.Column("hijos_detalle", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "hijos_detalle")
    op.drop_column("user_profiles", "estructura_familiar_relevante")
    op.drop_column("user_profiles", "ex_pareja_contexto")
    op.drop_column("user_profiles", "ex_pareja_relevante")
    op.drop_column("user_profiles", "convivencia")
    op.drop_column("user_profiles", "trabajo_profesion")
