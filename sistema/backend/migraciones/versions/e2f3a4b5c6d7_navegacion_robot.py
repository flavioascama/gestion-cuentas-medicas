"""opcion del sistema y capturas de la navegacion del robot

El administrador puede activar que el robot guarde una captura de su
navegador en cada paso (2026-11-17), para que quien opera el sistema vea que
el robot entra a las plataformas y hace el flujo. `opcion_sistema` guarda esa
opcion; `paso_robot`, una captura por paso de cada trabajo. La captura puede
mostrar datos del asegurado y se guarda cifrada (C-05, C-12). El rol de
aplicacion recibe sus permisos por los privilegios por defecto de la
migracion d5e6f7a8b9c0.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-11-17 19:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "opcion_sistema",
        sa.Column("clave", sa.String(60), primary_key=True),
        sa.Column("valor", sa.String(200), nullable=False),
        sa.Column("actualizado_por", sa.String(100), nullable=False),
        sa.Column(
            "actualizado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "paso_robot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "trabajo_id",
            sa.Integer(),
            sa.ForeignKey("trabajo.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("orden", sa.Integer(), nullable=False),
        sa.Column("plataforma", sa.String(20), nullable=False),
        sa.Column("descripcion", sa.String(150), nullable=False),
        sa.Column("url", sa.String(300), nullable=False),
        sa.Column(
            "capturado_en",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("captura", sa.LargeBinary(), nullable=False),
        sa.UniqueConstraint("trabajo_id", "orden", name="uq_paso_robot_trabajo_orden"),
    )
    op.create_index("ix_paso_robot_capturado_en", "paso_robot", ["capturado_en"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_paso_robot_capturado_en", table_name="paso_robot")
    op.drop_table("paso_robot")
    op.drop_table("opcion_sistema")
