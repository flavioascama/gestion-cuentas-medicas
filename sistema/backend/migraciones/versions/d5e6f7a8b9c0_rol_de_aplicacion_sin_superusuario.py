"""rol de aplicacion sin superusuario

C-10 y RAS-11 (verificacion de cumplimiento, 2026-11-12): la aplicacion se
conectaba con POSTGRES_USER, que es superusuario y por lo tanto ignora
cualquier permiso. Se crea un rol de aplicacion con LOGIN y sin
superusuario, con lectura y escritura sobre las tablas operativas y, sobre
`evento`, solo SELECT e INSERT: no puede modificar ni borrar eventos ni
desactivar los disparadores de inmutabilidad (no es dueno de la tabla).

`SELECT ... FOR UPDATE` (RegistroEventosSql serializa por agregado con un
bloqueo de fila) exige permiso UPDATE sobre al menos una columna: se
concede solo sobre `version`, y el disparador `trg_evento_sin_update`
sigue rechazando cualquier UPDATE real.

El nombre del rol y su clave vienen del entorno (USUARIO_APLICACION_BD,
CLAVE_USUARIO_APLICACION_BD), nunca del codigo versionado (C-06).

Revision ID: d5e6f7a8b9c0
Revises: c4e5f6a7b8d9
Create Date: 2026-11-13 12:00:00.000000

"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4e5f6a7b8d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rol() -> str:
    rol = os.environ.get("USUARIO_APLICACION_BD", "gestion_cuentas_app")
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", rol):
        raise RuntimeError(f"USUARIO_APLICACION_BD no es un nombre de rol valido: {rol!r}")
    return rol


def upgrade() -> None:
    """Upgrade schema."""
    rol = _rol()
    clave = os.environ.get("CLAVE_USUARIO_APLICACION_BD", "")
    if not clave:
        raise RuntimeError("Falta CLAVE_USUARIO_APLICACION_BD en el entorno (.env).")
    clave_sql = clave.replace("'", "''")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{rol}') THEN
                CREATE ROLE {rol} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                    PASSWORD '{clave_sql}';
            ELSE
                ALTER ROLE {rol} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
                    PASSWORD '{clave_sql}';
            END IF;
        END
        $$;
        """
    )
    op.execute(f'GRANT CONNECT ON DATABASE "{_base_actual()}" TO {rol}')
    op.execute(f"GRANT USAGE ON SCHEMA public TO {rol}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {rol}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {rol}")
    # El almacen de eventos: solo lectura e insercion.
    op.execute(f"REVOKE UPDATE, DELETE, TRUNCATE ON evento FROM {rol}")
    op.execute(f"GRANT UPDATE (version) ON evento TO {rol}")
    # alembic_version es del dueno del esquema.
    op.execute(f"REVOKE ALL ON alembic_version FROM {rol}")
    # Tablas y secuencias de migraciones futuras, creadas por el dueno.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {rol}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {rol}"
    )


def _base_actual() -> str:
    conexion = op.get_bind()
    return str(conexion.exec_driver_sql("SELECT current_database()").scalar_one())


def downgrade() -> None:
    """Downgrade schema."""
    rol = _rol()
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {rol}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM {rol}"
    )
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {rol}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {rol}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {rol}")
    op.execute(f'REVOKE CONNECT ON DATABASE "{_base_actual()}" FROM {rol}')
    op.execute(f"DROP ROLE IF EXISTS {rol}")
