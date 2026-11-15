"""siembra los cuatro roles fijos

Revision ID: 0001f0342f98
Revises: c7faa70c7dbc
Create Date: 2026-09-15 22:38:28.336994

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001f0342f98"
down_revision: str | Sequence[str] | None = "c7faa70c7dbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Conjunto cerrado de la Seccion 6.1. RF-19 administra la asignacion de
# estos roles a un usuario, no la creacion de roles nuevos (ver
# docs/DECISIONES.md).
_ROLES = ["analista", "auditor", "jefe", "administrador"]

_tabla_rol = sa.table("rol", sa.column("nombre", sa.String))


def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(_tabla_rol, [{"nombre": nombre} for nombre in _ROLES])


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(_tabla_rol.delete().where(_tabla_rol.c.nombre.in_(_ROLES)))
