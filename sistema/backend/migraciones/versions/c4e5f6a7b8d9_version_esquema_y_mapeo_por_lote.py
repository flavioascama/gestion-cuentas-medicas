"""version del estandar TEDEF y del diccionario de mapeo por lote

RT-06: "version del estandar, del diccionario de mapeo y de los catalogos
CPMS y GTIN por cuenta y lote". CPMS y GTIN ya se registran por
procedimiento y producto; faltaba la version del esquema TEDEF y del
diccionario de mapeo en el lote (verificacion de cumplimiento,
2026-11-12). Nulas en los lotes ya generados: no se reconstruye un dato
que no se registro en su momento.

Revision ID: c4e5f6a7b8d9
Revises: 9b1c2d3e4f50
Create Date: 2026-11-13 10:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4e5f6a7b8d9"
down_revision: str | Sequence[str] | None = "9b1c2d3e4f50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "lote_facturacion", sa.Column("version_esquema_tedef", sa.String(20), nullable=True)
    )
    op.add_column("lote_facturacion", sa.Column("version_mapeo", sa.String(64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("lote_facturacion", "version_mapeo")
    op.drop_column("lote_facturacion", "version_esquema_tedef")
