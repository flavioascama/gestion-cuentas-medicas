"""notas de credito y debito y comprobantes reemplazados

RI-11 (notas de credito y debito, Tabla 1 campos 25 a 29) y CU-10
(comprobante de reemplazo al refacturar), verificacion de cumplimiento
del 2026-11-12. El rol de aplicacion recibe sus permisos por los
privilegios por defecto de la migracion d5e6f7a8b9c0.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-11-13 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: str | Sequence[str] | None = "e6f7a8b9c0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "nota_documento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "documento_facturador_id",
            sa.Integer(),
            sa.ForeignKey("documento_facturador.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("tipo", sa.String(1), nullable=False),
        sa.Column("serie", sa.String(4), nullable=False),
        sa.Column("numero", sa.String(8), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("motivo", sa.String(1), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registrado_por", sa.String(100), nullable=False),
        sa.CheckConstraint("tipo IN ('C','D')", name="ck_nota_documento_tipo"),
        sa.CheckConstraint("motivo IN ('R','A','D')", name="ck_nota_documento_motivo"),
        sa.CheckConstraint("monto > 0", name="ck_nota_documento_monto"),
    )
    op.create_table(
        "comprobante_reemplazado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "documento_facturador_id",
            sa.Integer(),
            sa.ForeignKey("documento_facturador.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("tipo_documento_pago", sa.String(2), nullable=False),
        sa.Column("serie", sa.String(4), nullable=False),
        sa.Column("numero", sa.String(8), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("reemplazado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reemplazado_por", sa.String(100), nullable=False),
        sa.Column("motivo", sa.String(300), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("comprobante_reemplazado")
    op.drop_table("nota_documento")
