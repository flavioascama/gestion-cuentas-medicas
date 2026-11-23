"""Tres tablas del 2026-11-22: el PDF adjunto a la respuesta de una
observacion, la respuesta de la clinica a un correo de la IAFAS y las
atenciones del sistema hospitalario cargadas con un Excel. Los contenidos
con datos del asegurado se guardan cifrados (C-05), por eso son binarios.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

_INSTANTE = sa.DateTime(timezone=True)
# Columnas cifradas: el texto corto, el texto largo y el binario.
_CIFRADO_NOMBRE = sa.String(500)
_CIFRADO_TEXTO = sa.Text
_CIFRADO_BINARIO = sa.LargeBinary


def upgrade() -> None:
    op.create_table(
        "adjunto_respuesta_observacion",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "observacion_id",
            sa.Integer,
            sa.ForeignKey("observacion.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("nombre", _CIFRADO_NOMBRE, nullable=False),
        sa.Column("tamano", sa.Integer, nullable=False),
        sa.Column("contenido", _CIFRADO_BINARIO, nullable=False),
        sa.Column("subido_por", sa.String(60), nullable=False),
        sa.Column("subido_en", _INSTANTE, nullable=False),
    )
    op.create_table(
        "respuesta_correo_iafas",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "correo_id", sa.Integer, sa.ForeignKey("correo_iafas.id"), nullable=False, index=True
        ),
        sa.Column("texto", _CIFRADO_TEXTO, nullable=False),
        sa.Column("respondido_por", sa.String(60), nullable=False),
        sa.Column("respondido_en", _INSTANTE, nullable=False),
        sa.Column("enviada_en", _INSTANTE, nullable=True),
    )
    op.create_table(
        "atencion_cargada",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("atencion_id", sa.String(40), nullable=False, unique=True),
        sa.Column("datos", _CIFRADO_TEXTO, nullable=False),
        sa.Column("cargado_por", sa.String(60), nullable=False),
        sa.Column("cargado_en", _INSTANTE, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("atencion_cargada")
    op.drop_table("respuesta_correo_iafas")
    op.drop_table("adjunto_respuesta_observacion")
