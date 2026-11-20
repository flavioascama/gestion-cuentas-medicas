"""atencion importada del sistema hospitalario

La cuenta puede nacer de la atencion cerrada en el sistema hospitalario de
la clinica (2026-11-19). La cuenta guarda el tipo de atencion (las ya
registradas quedan AMBULATORIA, lo que viajaba fijo en la trama), la
atencion de origen (unica: no se importa dos veces), el medico, los
diagnosticos secundarios (cifrados como el principal) y las fechas de
hospitalizacion. Dos tablas nuevas: los procedimientos por codificar y el
copago cobrado. El rol de aplicacion recibe sus permisos por los
privilegios por defecto de la migracion d5e6f7a8b9c0.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-11-19 16:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: str | Sequence[str] | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Ancho de las columnas cifradas (cifrado_columnas.LONGITUD_COLUMNA_CIFRADA).
_LONGITUD_CIFRADA = 500


def _columnas_cuenta() -> None:
    op.add_column(
        "cuenta_medica",
        sa.Column("tipo_atencion", sa.String(15), nullable=False, server_default="AMBULATORIA"),
    )
    op.add_column("cuenta_medica", sa.Column("atencion_origen_id", sa.String(40), nullable=True))
    op.add_column("cuenta_medica", sa.Column("colegiatura_medico", sa.String(6), nullable=True))
    op.add_column("cuenta_medica", sa.Column("nombre_medico", sa.String(200), nullable=True))
    op.add_column(
        "cuenta_medica",
        sa.Column("diagnosticos_secundarios_cie10", sa.String(_LONGITUD_CIFRADA), nullable=True),
    )
    op.add_column(
        "cuenta_medica", sa.Column("fecha_ingreso_hospitalario", sa.Date(), nullable=True)
    )
    op.add_column("cuenta_medica", sa.Column("fecha_alta_hospitalaria", sa.Date(), nullable=True))
    op.create_unique_constraint(
        "uq_cuenta_medica_atencion_origen_id", "cuenta_medica", ["atencion_origen_id"]
    )
    op.create_check_constraint(
        "ck_cuenta_medica_tipo_atencion",
        "cuenta_medica",
        "tipo_atencion IN ('AMBULATORIA','EMERGENCIA','HOSPITALIZACION')",
    )


def upgrade() -> None:
    """Upgrade schema."""
    _columnas_cuenta()
    op.create_table(
        "procedimiento_por_codificar",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cuenta_medica_id",
            sa.Integer(),
            sa.ForeignKey("cuenta_medica.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("descripcion", sa.String(500), nullable=False),
        sa.Column("area", sa.String(15), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("monto_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column(
            "procedimiento_facturado_id",
            sa.Integer(),
            sa.ForeignKey("procedimiento_facturado.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.CheckConstraint(
            "area IN ('PROCEDIMIENTO','LABORATORIO','IMAGENES')", name="ck_por_codificar_area"
        ),
        sa.CheckConstraint("cantidad > 0", name="ck_por_codificar_cantidad"),
        sa.CheckConstraint("monto_unitario > 0", name="ck_por_codificar_monto"),
    )
    op.create_table(
        "copago_cobrado",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cuenta_medica_id",
            sa.Integer(),
            sa.ForeignKey("cuenta_medica.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("referencia", sa.String(60), nullable=False),
        sa.Column("origen", sa.String(30), nullable=False),
        sa.Column("registrado_por", sa.String(100), nullable=False),
        sa.Column(
            "registrado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("monto > 0", name="ck_copago_cobrado_monto"),
        sa.CheckConstraint(
            "origen IN ('sistema_hospitalario','manual')", name="ck_copago_cobrado_origen"
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("copago_cobrado")
    op.drop_table("procedimiento_por_codificar")
    op.drop_constraint("ck_cuenta_medica_tipo_atencion", "cuenta_medica", type_="check")
    op.drop_constraint("uq_cuenta_medica_atencion_origen_id", "cuenta_medica", type_="unique")
    for columna in (
        "fecha_alta_hospitalaria",
        "fecha_ingreso_hospitalario",
        "diagnosticos_secundarios_cie10",
        "nombre_medico",
        "colegiatura_medico",
        "atencion_origen_id",
        "tipo_atencion",
    ):
        op.drop_column("cuenta_medica", columna)
