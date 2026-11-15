"""carta de garantia por cuenta

RF-13 y CU-06 (verificacion de cumplimiento, 2026-11-12): la carta de
garantia de la IAFAS como documento, con numero, vigencia y monto. Una por
cuenta. El rol de aplicacion recibe sus permisos por los privilegios por
defecto de la migracion d5e6f7a8b9c0.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-11-13 14:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: str | Sequence[str] | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "carta_garantia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cuenta_medica_id",
            sa.Integer(),
            sa.ForeignKey("cuenta_medica.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("numero", sa.String(30), nullable=False),
        sa.Column("vigente_desde", sa.Date(), nullable=False),
        sa.Column("vigente_hasta", sa.Date(), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registrado_por", sa.String(100), nullable=False),
        sa.CheckConstraint("vigente_hasta >= vigente_desde", name="ck_carta_garantia_vigencia"),
        sa.CheckConstraint("monto > 0", name="ck_carta_garantia_monto"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("carta_garantia")
