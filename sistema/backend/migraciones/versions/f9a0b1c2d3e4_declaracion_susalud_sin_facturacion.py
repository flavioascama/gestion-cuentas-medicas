"""declaracion jurada de meses sin facturacion a SUSALUD

Los meses en que la clinica no remitio lotes a las IAFAS se declaran a
SUSALUD dentro del mismo plazo del reporte mensual (Resolucion
043-2025-SUSALUD/S). El sistema guarda solo la constancia: el periodo
(unico), cuando se registro y quien. El rol de aplicacion recibe sus
permisos por los privilegios por defecto de la migracion d5e6f7a8b9c0.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-11-19 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9a0b1c2d3e4"
down_revision: str | Sequence[str] | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "declaracion_susalud_sin_facturacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("periodo", sa.String(6), nullable=False, unique=True),
        sa.Column(
            "registrada_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("registrada_por", sa.String(100), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("declaracion_susalud_sin_facturacion")
