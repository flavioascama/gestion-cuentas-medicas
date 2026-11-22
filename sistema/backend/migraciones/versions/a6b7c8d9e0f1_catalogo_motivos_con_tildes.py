"""Descripciones del catalogo de motivos de observacion con tildes, para las
bases que ya cargaron la semilla sin ellas.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None

# (codigo, descripcion anterior, descripcion corregida)
_CORRECCIONES = [
    ("OBS-04", "Prestacion no reconocida", "Prestación no reconocida"),
    (
        "OBS-05",
        "Incompatibilidad entre el diagnostico y el procedimiento facturado",
        "Incompatibilidad entre el diagnóstico y el procedimiento facturado",
    ),
]

_SENTENCIA = sa.text(
    "UPDATE catalogo_motivo_observacion SET descripcion = :nueva "
    "WHERE codigo = :codigo AND descripcion = :anterior"
)


def upgrade() -> None:
    for codigo, anterior, nueva in _CORRECCIONES:
        op.execute(_SENTENCIA.bindparams(codigo=codigo, anterior=anterior, nueva=nueva))


def downgrade() -> None:
    for codigo, anterior, nueva in _CORRECCIONES:
        op.execute(_SENTENCIA.bindparams(codigo=codigo, anterior=nueva, nueva=anterior))
