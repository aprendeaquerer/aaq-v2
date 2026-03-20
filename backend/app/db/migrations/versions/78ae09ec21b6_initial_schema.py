"""initial_schema

Revision ID: 78ae09ec21b6
Revises:
Create Date: 2026-03-19

Safe migration: Only creates new v2 tables alongside existing ones.
Does NOT modify or drop existing tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '78ae09ec21b6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create new v2 tables alongside existing ones

    # user_profiles (new name, different from existing user_profile)
    op.create_table('user_profiles',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('nombre', sa.String(), nullable=True),
        sa.Column('edad', sa.Integer(), nullable=True),
        sa.Column('tiene_pareja', sa.Boolean(), nullable=True),
        sa.Column('nombre_pareja', sa.String(), nullable=True),
        sa.Column('tiempo_pareja', sa.String(), nullable=True),
        sa.Column('attachment_style', sa.String(), nullable=True),
        sa.Column('partner_attachment_style', sa.String(), nullable=True),
        sa.Column('relationship_status', sa.String(), nullable=True),
        sa.Column('last_conversation_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_affirmation_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('affirmation_index', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )

    # test_states (new name, different from existing test_state)
    op.create_table('test_states',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('test_type', sa.String(), nullable=False),
        sa.Column('state', sa.String(), nullable=False),
        sa.Column('answers', sa.Text(), nullable=True),
        sa.Column('scores', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_test_states_user_id', 'test_states', ['user_id'])

    # knowledge (unified, replaces eldric_knowledge_*)
    op.create_table('knowledge',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('tags', sa.Text(), nullable=False),
        sa.Column('book', sa.String(), nullable=True),
        sa.Column('chapter', sa.String(), nullable=True),
        sa.Column('language', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_knowledge_language_tags', 'knowledge', ['language', 'tags'])


def downgrade() -> None:
    op.drop_index('ix_knowledge_language_tags', table_name='knowledge')
    op.drop_table('knowledge')
    op.drop_index('ix_test_states_user_id', table_name='test_states')
    op.drop_table('test_states')
    op.drop_table('user_profiles')
