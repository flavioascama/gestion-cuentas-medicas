"""agrega diagnostico principal provisional a cuenta medica

Revision ID: 4e9de803e3f4
Revises: ab8ce7d4a79e
Create Date: 2026-09-16 02:24:46.503211

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e9de803e3f4"
down_revision: str | Sequence[str] | None = "ab8ce7d4a79e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "cuenta_medica",
        sa.Column("diagnostico_principal_cie10", sa.String(length=5), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("cuenta_medica", "diagnostico_principal_cie10")
