"""El motivo con que el jefe de cuentas medicas resuelve una solicitud de
anulacion: obligatorio al rechazar, visible para quien la pidio.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e4f5a6b7c8d9"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "solicitud_anulacion",
        sa.Column("motivo_resolucion", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("solicitud_anulacion", "motivo_resolucion")
