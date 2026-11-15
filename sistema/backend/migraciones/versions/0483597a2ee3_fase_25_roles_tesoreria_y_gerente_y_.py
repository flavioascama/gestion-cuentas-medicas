"""Fase 25: roles tesoreria y gerente (Tabla 45), y ampliacion del
conjunto cerrado de estados de cuenta_medica de los cuatro del OE1 a los
catorce del motor de orquestacion (R2.4/R2.5, Seccion 5.2.4, Tabla 58).

Revision ID: 0483597a2ee3
Revises: 64c81a12524c
Create Date: 2026-11-08 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0483597a2ee3"
down_revision: str | Sequence[str] | None = "64c81a12524c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLES_NUEVOS = ["tesoreria", "gerente"]

_tabla_rol = sa.table("rol", sa.column("nombre", sa.String))

# Seccion 5.2.4, Tabla 58 (ver tambien 6.2.2, Tablas 65/66): los catorce
# estados del ciclo. CERRADA y ANULADA son terminales.
_ESTADOS_CUENTA_MEDICA = (
    "REGISTRADA",
    "FACTURADA",
    "ENVIADA",
    "EN_AUDITORIA",
    "GLOSADA",
    "GLOSADA_PARCIAL",
    "SUBSANADA",
    "LIQUIDADA",
    "LIQUIDADA_PARCIAL",
    "PAGADA",
    "PAGADA_PARCIAL",
    "RECHAZADA",
    "CERRADA",
    "ANULADA",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(_tabla_rol, [{"nombre": nombre} for nombre in _ROLES_NUEVOS])

    lista_estados = ", ".join("'" + estado + "'" for estado in _ESTADOS_CUENTA_MEDICA)
    op.drop_constraint("ck_cuenta_medica_estado", "cuenta_medica", type_="check")
    op.create_check_constraint(
        "ck_cuenta_medica_estado",
        "cuenta_medica",
        f"estado IN ({lista_estados})",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("ck_cuenta_medica_estado", "cuenta_medica", type_="check")
    op.create_check_constraint(
        "ck_cuenta_medica_estado",
        "cuenta_medica",
        "estado IN ('REGISTRADA','FACTURADA','ENVIADA','RECHAZADA')",
    )
    op.execute(_tabla_rol.delete().where(_tabla_rol.c.nombre.in_(_ROLES_NUEVOS)))
