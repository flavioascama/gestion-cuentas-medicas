"""Una cuenta puede tener varias acreditaciones (nueva consulta de la
cobertura mientras la cuenta esta REGISTRADA y sin comprobante); la
vigente es la mas reciente y las anteriores se conservan.

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
"""

from __future__ import annotations

from alembic import op

revision = "a0b1c2d3e4f5"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("acreditacion_cuenta_id_key", "acreditacion", type_="unique")
    op.create_index("ix_acreditacion_cuenta_id", "acreditacion", ["cuenta_id"])


def downgrade() -> None:
    # Vuelve a una por cuenta: se queda la vigente (la mas reciente).
    op.execute(
        "DELETE FROM acreditacion a USING acreditacion b "
        "WHERE a.cuenta_id = b.cuenta_id AND a.id < b.id"
    )
    op.drop_index("ix_acreditacion_cuenta_id", table_name="acreditacion")
    op.create_unique_constraint("acreditacion_cuenta_id_key", "acreditacion", ["cuenta_id"])
