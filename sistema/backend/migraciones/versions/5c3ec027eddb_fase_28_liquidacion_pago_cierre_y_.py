"""Fase 28: liquidacion, pago, cierre y anulacion de la cuenta (R2.5,
Seccion 5.2.4.1, Tabla 58 T-10 a T-13; CU-12 y CU-13).

Dos tablas nuevas. `liquidacion`: una fila por cuenta (unica, FK unique)
que nace con el monto comunicado por la aseguradora (T-10) y se
completa despues con el monto pagado y la diferencia cuando tesoreria
concilia el pago (T-11) -- mismo patron "nace incompleta, se completa
despues" que `observacion` (Fase 26). `solicitud_anulacion`: el
analista solicita, el jefe de cuentas medicas aprueba o rechaza
(RF-21); a lo sumo una solicitud PENDIENTE por cuenta a la vez.

Revision ID: 5c3ec027eddb
Revises: a900765e4e0d
Create Date: 2026-11-08 23:40:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c3ec027eddb"
down_revision: str | Sequence[str] | None = "a900765e4e0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "liquidacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cuenta_medica_id", sa.Integer(), sa.ForeignKey("cuenta_medica.id"), nullable=False
        ),
        sa.Column("es_parcial", sa.Boolean(), nullable=False),
        sa.Column("monto_liquidado", sa.Numeric(12, 2), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("monto_pagado", sa.Numeric(12, 2), nullable=True),
        sa.Column("diferencia", sa.Numeric(12, 2), nullable=True),
        sa.Column("conciliado_en", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("cuenta_medica_id", name="uq_liquidacion_cuenta_medica_id"),
    )
    op.create_table(
        "solicitud_anulacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cuenta_medica_id", sa.Integer(), sa.ForeignKey("cuenta_medica.id"), nullable=False
        ),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="PENDIENTE"),
        sa.Column("solicitado_por", sa.String(100), nullable=False),
        sa.Column("solicitado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resuelto_por", sa.String(100), nullable=True),
        sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "estado IN ('PENDIENTE','APROBADA','RECHAZADA')",
            name="ck_solicitud_anulacion_estado",
        ),
    )
    op.create_index(
        "ix_solicitud_anulacion_cuenta_medica_id", "solicitud_anulacion", ["cuenta_medica_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_solicitud_anulacion_cuenta_medica_id", table_name="solicitud_anulacion")
    op.drop_table("solicitud_anulacion")
    op.drop_table("liquidacion")
