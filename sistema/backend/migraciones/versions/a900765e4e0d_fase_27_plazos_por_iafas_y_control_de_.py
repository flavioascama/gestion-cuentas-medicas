"""Fase 27: plazos por IAFAS para el control de vencimientos (R2.5,
Seccion 5.2.4.3, Tabla 61). Tres de los cinco hitos controlados son
"parametro asociado a la aseguradora, con origen en el convenio
suscrito con ella" -- se agregan como columnas de `iafas`, junto a
`periodicidad_remision_dias` y `ventana_monitoreo_horas`, ya existentes
desde el OE1 con el mismo patron. Los otros dos hitos (reenvio de un
lote rechazado, parametro del sistema; vigencia de la carta de
garantia, que ya se registra en `acreditacion.vigente_hasta`) no
necesitan columna nueva.

Revision ID: a900765e4e0d
Revises: e0ec334770c5
Create Date: 2026-11-08 23:13:59.337171

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a900765e4e0d"
down_revision: str | Sequence[str] | None = "e0ec334770c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Anexo C, Tabla 3 / seccion 2.2: "la respuesta a una observacion toma
# entre tres y siete dias" en la practica real relevada -- el valor por
# defecto de la columna nueva se fija en el extremo mas exigente de ese
# rango para las cuentas ya existentes, sin convenio especifico que lo
# sustituya. Para los otros dos hitos por IAFAS, la tesis no releva un
# numero de referencia: se adopta 30 dias (un ciclo mensual de
# facturacion) como valor por defecto, documentado como supuesto en
# docs/DECISIONES.md.
_DEFAULT_DIAS_PLAZO_RESPUESTA_OBSERVACION = 7
_DEFAULT_DIAS_PLAZO_COMUNICACION_AUDITORIA = 30
_DEFAULT_DIAS_PLAZO_PAGO_LIQUIDACION = 30


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "iafas",
        sa.Column(
            "dias_plazo_respuesta_observacion",
            sa.Integer(),
            nullable=False,
            server_default=str(_DEFAULT_DIAS_PLAZO_RESPUESTA_OBSERVACION),
        ),
    )
    op.add_column(
        "iafas",
        sa.Column(
            "dias_plazo_comunicacion_auditoria",
            sa.Integer(),
            nullable=False,
            server_default=str(_DEFAULT_DIAS_PLAZO_COMUNICACION_AUDITORIA),
        ),
    )
    op.add_column(
        "iafas",
        sa.Column(
            "dias_plazo_pago_liquidacion",
            sa.Integer(),
            nullable=False,
            server_default=str(_DEFAULT_DIAS_PLAZO_PAGO_LIQUIDACION),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("iafas", "dias_plazo_pago_liquidacion")
    op.drop_column("iafas", "dias_plazo_comunicacion_auditoria")
    op.drop_column("iafas", "dias_plazo_respuesta_observacion")
