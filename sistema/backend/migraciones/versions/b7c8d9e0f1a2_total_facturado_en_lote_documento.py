"""Total facturado por cada comprobante al generar el lote: el lote muestra
lo que remitio aunque despues se reemplace el comprobante (segunda auditoria
final, hallazgo 1). Las filas existentes se rellenan con el total actual de
su comprobante.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lote_documento",
        sa.Column("total_facturado", sa.Numeric(12, 2), nullable=True),
    )
    op.execute(
        "UPDATE lote_documento SET total_facturado = ("
        "SELECT documento_facturador.total FROM documento_facturador "
        "WHERE documento_facturador.id = lote_documento.documento_id)"
    )


def downgrade() -> None:
    op.drop_column("lote_documento", "total_facturado")
