"""condicion de cobertura completa

ACREDITA SALUD responde textos como "ACREDITABLE CON RESTRICCION:
diagnostico en periodo de carencia" o "NO ACREDITABLE: afiliacion
cancelada", que no cabian en los 20 caracteres de la columna: el guardado
fallaba y el caso terminaba como si la plataforma no hubiera respondido.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-11-19 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: str | Sequence[str] | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "acreditacion",
        "condicion_cobertura",
        existing_type=sa.String(length=20),
        type_=sa.String(length=120),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "acreditacion",
        "condicion_cobertura",
        existing_type=sa.String(length=120),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
