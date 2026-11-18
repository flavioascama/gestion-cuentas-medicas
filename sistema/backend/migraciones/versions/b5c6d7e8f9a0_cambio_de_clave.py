"""cambio de clave en el primer ingreso

Desde el 2026-11-18 quien recibe una clave puesta por el administrador debe
cambiarla en su primer ingreso. Los usuarios que ya existen no quedan
obligados: la columna nace en falso.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-11-18 23:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: str | Sequence[str] | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "usuario",
        sa.Column("debe_cambiar_clave", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("usuario", "debe_cambiar_clave")
