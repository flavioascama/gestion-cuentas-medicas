"""permite SIN_RESULTADO en trabajo.estado

La plataforma respondio, pero con un resultado definitivo negativo (por
ejemplo, ACREDITA SALUD no encontro al asegurado): no es una falla que
convenga reintentar ni una indisponibilidad que habilite la contingencia
(rediseno del 2026-11-12, docs/DECISIONES.md).

Revision ID: 9b1c2d3e4f50
Revises: 5c3ec027eddb
Create Date: 2026-11-12 19:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b1c2d3e4f50"
down_revision: str | Sequence[str] | None = "5c3ec027eddb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Alembic autogenerate no detecta cambios de CHECK CONSTRAINT (Fase 13 y
# Fase 15, docs/DECISIONES.md): esta migracion se escribe a mano.
_ESTADOS_ANTERIORES = (
    "estado IN ('PENDIENTE','EN_PROCESO','COMPLETADO','AGOTADO','REQUIERE_SESION')"
)
_ESTADOS_NUEVOS = (
    "estado IN ('PENDIENTE','EN_PROCESO','COMPLETADO','AGOTADO','REQUIERE_SESION','SIN_RESULTADO')"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("ck_trabajo_estado", "trabajo", type_="check")
    op.create_check_constraint("ck_trabajo_estado", "trabajo", _ESTADOS_NUEVOS)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE trabajo SET estado = 'AGOTADO' WHERE estado = 'SIN_RESULTADO'")
    op.drop_constraint("ck_trabajo_estado", "trabajo", type_="check")
    op.create_check_constraint("ck_trabajo_estado", "trabajo", _ESTADOS_ANTERIORES)
