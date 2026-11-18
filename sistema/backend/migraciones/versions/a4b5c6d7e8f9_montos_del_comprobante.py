"""montos del comprobante de pago

Desde el 2026-11-18 el comprobante guarda lo que factura: valor de venta,
IGV y total, calculados al emitirlo con la misma regla que la tabla T1 del
lote. Las tres columnas admiten nulo: los comprobantes anteriores no lo
guardaron y su monto se calcula al consultarlos.

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-11-18 20:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: str | Sequence[str] | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNAS = ("valor_venta", "igv", "total")


def upgrade() -> None:
    """Upgrade schema."""
    for columna in _COLUMNAS:
        op.add_column("documento_facturador", sa.Column(columna, sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for columna in reversed(_COLUMNAS):
        op.drop_column("documento_facturador", columna)
