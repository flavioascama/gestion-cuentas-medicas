"""proyeccion de lectura del ciclo de la cuenta

RNF-04, RAS-04, AD-04 y RF-15 (verificacion de cumplimiento, 2026-11-12):
los indicadores del panel salen de una proyeccion que se actualiza al
registrar cada evento de la cuenta, no del recorrido del almacen en cada
consulta. Se llena con herramientas/reconstruir_proyecciones.py.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-11-13 20:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "proyeccion_ciclo_cuenta",
        sa.Column("cuenta_medica_id", sa.Integer(), primary_key=True),
        sa.Column("estado", sa.String(20), nullable=True),
        sa.Column("primer_cambio_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_cambio_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cerrada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("glosada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tiempos", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("version_evento", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("proyeccion_ciclo_cuenta")
