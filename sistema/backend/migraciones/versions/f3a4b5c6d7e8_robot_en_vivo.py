"""vista en vivo del robot, sin imagenes guardadas

Desde el 2026-11-18 el robot ya no guarda una captura por paso: `paso_robot`
queda como registro (que hizo, donde y cuando) y pierde la columna de la
imagen. `cuadro_robot` tiene, mientras un trabajo esta en curso, lo que el
navegador del robot muestra en ese momento, cifrado (C-05, C-12); el
trabajador borra la fila al terminar. El rol de aplicacion recibe sus
permisos por los privilegios por defecto de la migracion d5e6f7a8b9c0.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-11-18 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("paso_robot", "captura")
    op.create_table(
        "cuadro_robot",
        sa.Column(
            "trabajo_id",
            sa.Integer(),
            sa.ForeignKey("trabajo.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("url", sa.String(300), nullable=False),
        sa.Column("cuadro", sa.LargeBinary(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("cuadro_robot")
    # Las capturas borradas no se recuperan: los pasos que existan quedan
    # sin imagen.
    op.execute("DELETE FROM paso_robot")
    op.add_column("paso_robot", sa.Column("captura", sa.LargeBinary(), nullable=False))
