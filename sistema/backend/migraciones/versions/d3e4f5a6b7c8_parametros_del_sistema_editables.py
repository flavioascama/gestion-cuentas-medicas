"""Parametros del sistema editables por el administrador: el valor que fija
reemplaza al de la configuracion del despliegue.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parametro_sistema",
        sa.Column("clave", sa.String(60), primary_key=True),
        sa.Column("valor", sa.Text(), nullable=False),
        sa.Column("actualizado_por", sa.String(100), nullable=False),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("parametro_sistema")
