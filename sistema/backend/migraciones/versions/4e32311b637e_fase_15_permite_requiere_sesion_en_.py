"""fase 15: permite REQUIERE_SESION en trabajo.estado

Revision ID: 4e32311b637e
Revises: db49fbfc13ff
Create Date: 2026-09-25 13:01:11.896253

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e32311b637e"
down_revision: str | Sequence[str] | None = "db49fbfc13ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Alembic autogenerate no detecta cambios de CHECK CONSTRAINT (ya paso en
# la Fase 13, docs/DECISIONES.md): esta migracion se escribe a mano.
_ESTADOS_ANTERIORES = "estado IN ('PENDIENTE','EN_PROCESO','COMPLETADO','AGOTADO')"
_ESTADOS_NUEVOS = "estado IN ('PENDIENTE','EN_PROCESO','COMPLETADO','AGOTADO','REQUIERE_SESION')"


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_trabajo_estado", "trabajo", type_="check")
    op.create_check_constraint("ck_trabajo_estado", "trabajo", _ESTADOS_NUEVOS)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE trabajo SET estado = 'PENDIENTE' WHERE estado = 'REQUIERE_SESION'")
    op.drop_constraint("ck_trabajo_estado", "trabajo", type_="check")
    op.create_check_constraint("ck_trabajo_estado", "trabajo", _ESTADOS_ANTERIORES)
