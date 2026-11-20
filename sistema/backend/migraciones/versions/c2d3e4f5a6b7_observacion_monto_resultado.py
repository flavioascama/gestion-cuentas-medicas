"""La observacion guarda cuanto se observo y en que termino: el monto
glosado (si la aseguradora lo comunica) y el resultado LEVANTADA o
MANTENIDA con su fecha.

Revision ID: c2d3e4f5a6b7
Revises: a0b1c2d3e4f5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c2d3e4f5a6b7"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("observacion", sa.Column("monto_observado", sa.Numeric(12, 2), nullable=True))
    op.add_column("observacion", sa.Column("resultado", sa.String(10), nullable=True))
    op.add_column(
        "observacion", sa.Column("resultado_en", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_observacion_resultado",
        "observacion",
        "resultado IS NULL OR resultado IN ('LEVANTADA','MANTENIDA')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_observacion_resultado", "observacion", type_="check")
    op.drop_column("observacion", "resultado_en")
    op.drop_column("observacion", "resultado")
    op.drop_column("observacion", "monto_observado")
