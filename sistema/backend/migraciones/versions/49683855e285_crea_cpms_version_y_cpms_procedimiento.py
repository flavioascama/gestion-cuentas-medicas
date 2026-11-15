"""crea cpms_version y cpms_procedimiento

Revision ID: 49683855e285
Revises: 0001f0342f98
Create Date: 2026-09-15 23:46:00.607582

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "49683855e285"
down_revision: str | Sequence[str] | None = "0001f0342f98"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "cpms_version",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("etiqueta", sa.String(length=50), nullable=False),
        sa.Column("archivos_origen", sa.JSON(), nullable=False),
        sa.Column("conteo", sa.Integer(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cpms_procedimiento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cpms_version_id", sa.Integer(), nullable=False),
        sa.Column("codigo_grupo", sa.String(length=20), nullable=False),
        sa.Column("nombre_grupo", sa.String(length=200), nullable=False),
        sa.Column("codigo_seccion", sa.String(length=20), nullable=False),
        sa.Column("nombre_seccion", sa.String(length=200), nullable=False),
        sa.Column("codigo_subseccion", sa.String(length=20), nullable=False),
        sa.Column("nombre_subseccion", sa.String(length=200), nullable=False),
        sa.Column("codigo_procedimiento", sa.String(length=20), nullable=False),
        sa.Column("denominacion_procedimiento", sa.String(length=1000), nullable=False),
        sa.ForeignKeyConstraint(["cpms_version_id"], ["cpms_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cpms_procedimiento_codigo_procedimiento"),
        "cpms_procedimiento",
        ["codigo_procedimiento"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cpms_procedimiento_cpms_version_id"),
        "cpms_procedimiento",
        ["cpms_version_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_cpms_procedimiento_cpms_version_id"), table_name="cpms_procedimiento")
    op.drop_index(
        op.f("ix_cpms_procedimiento_codigo_procedimiento"), table_name="cpms_procedimiento"
    )
    op.drop_table("cpms_procedimiento")
    op.drop_table("cpms_version")
