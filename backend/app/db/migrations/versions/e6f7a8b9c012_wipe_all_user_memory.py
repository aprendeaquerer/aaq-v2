"""wipe_all_user_memory

Reset total decidido por la propietaria el 2026-08-12: se borran todas las
memorias, planes, conversaciones, estados de test y perfiles acumulados durante
las pruebas. Las cuentas de usuario (tabla users) se conservan. Corre una sola
vez, en el siguiente despliegue.

Revision ID: e6f7a8b9c012
Revises: d5e6f7a8b901
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e6f7a8b9c012"
down_revision: Union[str, None] = "d5e6f7a8b901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "user_memories",
    "coaching_plans",
    "conversations",
    "test_states",
    "user_profiles",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f'DELETE FROM "{table}"')


def downgrade() -> None:
    # Data deletion is irreversible.
    pass
