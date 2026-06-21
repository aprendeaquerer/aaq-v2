"""add_profile_demographics

Revision ID: 9f1d2e3c4b5a
Revises: 3c8b7d2a1f49
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9f1d2e3c4b5a"
down_revision: Union[str, None] = "3c8b7d2a1f49"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("genero", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("edad_pareja", sa.Integer(), nullable=True))
    op.add_column("user_profiles", sa.Column("genero_pareja", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("orientacion", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("tipo_relacion", sa.String(), nullable=True))
    op.add_column("user_profiles", sa.Column("convive_con_pareja", sa.Boolean(), nullable=True))
    op.add_column("user_profiles", sa.Column("tiene_hijos", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "tiene_hijos")
    op.drop_column("user_profiles", "convive_con_pareja")
    op.drop_column("user_profiles", "tipo_relacion")
    op.drop_column("user_profiles", "orientacion")
    op.drop_column("user_profiles", "genero_pareja")
    op.drop_column("user_profiles", "edad_pareja")
    op.drop_column("user_profiles", "genero")

