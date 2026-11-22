"""Fase 26: observaciones (glosas) -- catalogo parametrizable de motivos
y la tabla de observaciones (Seccion 5.2.4.2, Tabla 60; CU-08 a CU-10).

Revision ID: e0ec334770c5
Revises: 0483597a2ee3
Create Date: 2026-11-08 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0ec334770c5"
down_revision: str | Sequence[str] | None = "0483597a2ee3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabla 60: las "situaciones que comprende" cada naturaleza, una fila de
# catalogo por situacion mencionada. No es un catalogo oficial externo
# (a diferencia de CPMS/CIE-10/GTIN): lo parametriza la propia clinica
# (Seccion 5.2.4.2), estos siete son el punto de partida razonable a
# partir de los ejemplos que la propia tesis da en la Tabla 60.
_MOTIVOS_SEMILLA = [
    ("OBS-01", "Datos incompletos", "ADMINISTRATIVA"),
    ("OBS-02", "Ausencia de firma", "ADMINISTRATIVA"),
    ("OBS-03", "Paciente no activo en la cobertura", "ADMINISTRATIVA"),
    ("OBS-04", "Prestación no reconocida", "TECNICA"),
    ("OBS-05", "Incompatibilidad entre el diagnóstico y el procedimiento facturado", "TECNICA"),
    ("OBS-06", "Duplicidad de registros", "FINANCIERA"),
    ("OBS-07", "Prestaciones fuera de la cobertura del plan", "FINANCIERA"),
]

_tabla_catalogo_motivo = sa.table(
    "catalogo_motivo_observacion",
    sa.column("codigo", sa.String),
    sa.column("descripcion", sa.String),
    sa.column("naturaleza", sa.String),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "catalogo_motivo_observacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(10), nullable=False),
        sa.Column("descripcion", sa.String(300), nullable=False),
        sa.Column("naturaleza", sa.String(20), nullable=False),
        sa.UniqueConstraint("codigo", name="uq_catalogo_motivo_observacion_codigo"),
        sa.CheckConstraint(
            "naturaleza IN ('ADMINISTRATIVA','TECNICA','FINANCIERA')",
            name="ck_catalogo_motivo_observacion_naturaleza",
        ),
    )
    op.bulk_insert(
        _tabla_catalogo_motivo,
        [
            {"codigo": codigo, "descripcion": descripcion, "naturaleza": naturaleza}
            for codigo, descripcion, naturaleza in _MOTIVOS_SEMILLA
        ],
    )

    op.create_table(
        "observacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cuenta_medica_id", sa.Integer(), sa.ForeignKey("cuenta_medica.id"), nullable=False
        ),
        sa.Column(
            "motivo_codigo",
            sa.String(10),
            sa.ForeignKey("catalogo_motivo_observacion.codigo"),
            nullable=False,
        ),
        sa.Column("naturaleza", sa.String(20), nullable=False),
        sa.Column("es_parcial", sa.Boolean(), nullable=False),
        sa.Column("detalle_campo_objetado", sa.String(500), nullable=True),
        sa.Column("responsable_rol", sa.String(20), nullable=False),
        sa.Column(
            "responsable_usuario_id", sa.Integer(), sa.ForeignKey("usuario.id"), nullable=True
        ),
        sa.Column("estado", sa.String(20), nullable=False, server_default="ABIERTA"),
        sa.Column("respuesta_texto", sa.String(1000), nullable=True),
        sa.Column("respuesta_sustento", sa.String(500), nullable=True),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("respondido_en", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "naturaleza IN ('ADMINISTRATIVA','TECNICA','FINANCIERA')",
            name="ck_observacion_naturaleza",
        ),
        sa.CheckConstraint(
            "responsable_rol IN ('analista','auditor')", name="ck_observacion_responsable_rol"
        ),
        sa.CheckConstraint("estado IN ('ABIERTA','RESPONDIDA')", name="ck_observacion_estado"),
    )
    op.create_index("ix_observacion_cuenta_medica_id", "observacion", ["cuenta_medica_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_observacion_cuenta_medica_id", table_name="observacion")
    op.drop_table("observacion")
    op.drop_table("catalogo_motivo_observacion")
