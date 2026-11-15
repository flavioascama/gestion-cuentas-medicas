"""fase 22: control C-01 (bloqueo de cuenta y revocacion de sesion)

Revision ID: a2f5ccc12d05
Revises: 6c145ea72e3d
Create Date: 2026-10-27 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2f5ccc12d05"
down_revision: str | Sequence[str] | None = "6c145ea72e3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "usuario",
        sa.Column("intentos_fallidos", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "usuario", sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "token_revocado",
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revocado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("jti"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("token_revocado")
    op.drop_column("usuario", "bloqueado_hasta")
    op.drop_column("usuario", "intentos_fallidos")
