"""perfil jefe completo

La pantalla trabaja con cuatro perfiles (analista, auditor, jefe y
administrador) y el perfil Jefe reune los roles jefe, tesoreria y gerente.
Quien ya tenia el rol jefe recibe los otros dos. Los roles del servidor
siguen siendo los seis de siempre.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-11-19 14:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "c6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        INSERT INTO usuario_rol (usuario_id, rol_id)
        SELECT ur.usuario_id, adicional.id
        FROM usuario_rol ur
        JOIN rol jefe ON jefe.id = ur.rol_id AND jefe.nombre = 'jefe'
        CROSS JOIN rol adicional
        WHERE adicional.nombre IN ('tesoreria', 'gerente')
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    """Downgrade schema. No se revierte: no se sabe quien tenia ya esos
    roles antes de la migracion."""
