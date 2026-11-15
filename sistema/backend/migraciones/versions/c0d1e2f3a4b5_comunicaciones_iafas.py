"""comunicaciones de la IAFAS recibidas por portal o correo

Automatizacion de la recepcion de la conformidad, la observacion (glosa),
la liquidacion y el aviso de pago que la aseguradora comunica por su
portal o por correo electronico (2026-11-13). Cada comunicacion se guarda
una vez, con la cuenta a la que se aplico y el resultado. El rol de
aplicacion recibe sus permisos por los privilegios por defecto de la
migracion d5e6f7a8b9c0.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-11-13 23:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c0d1e2f3a4b5"
down_revision: str | Sequence[str] | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "comunicacion_iafas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(20), nullable=False, unique=True),
        sa.Column("canal", sa.String(10), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("codigo_iafas", sa.String(5), nullable=False),
        sa.Column("codigo_ipress", sa.String(8), nullable=False),
        sa.Column("documento", sa.String(12), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("emitida_en", sa.String(30), nullable=False),
        sa.Column(
            "cuenta_medica_id", sa.Integer(), sa.ForeignKey("cuenta_medica.id"), nullable=True
        ),
        sa.Column("resultado", sa.String(15), nullable=False),
        sa.Column("detalle", sa.String(500), nullable=True),
        sa.Column("observacion_id", sa.Integer(), nullable=True),
        sa.Column("recibida_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("respuesta_remitida_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("canal IN ('PORTAL','CORREO')", name="ck_comunicacion_iafas_canal"),
        sa.CheckConstraint(
            "resultado IN ('APLICADA','NO_APLICADA')", name="ck_comunicacion_iafas_resultado"
        ),
    )
    op.create_index(
        "ix_comunicacion_iafas_cuenta_medica_id", "comunicacion_iafas", ["cuenta_medica_id"]
    )
    op.create_index(
        "ix_comunicacion_iafas_observacion_id", "comunicacion_iafas", ["observacion_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_comunicacion_iafas_observacion_id", table_name="comunicacion_iafas")
    op.drop_index("ix_comunicacion_iafas_cuenta_medica_id", table_name="comunicacion_iafas")
    op.drop_table("comunicacion_iafas")
