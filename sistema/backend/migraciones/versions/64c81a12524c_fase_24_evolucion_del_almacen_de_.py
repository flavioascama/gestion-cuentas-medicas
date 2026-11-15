"""Fase 24: evolucion del almacen de eventos hacia el modelo generico de
agregado (R3.2/R3.3, Seccion 6.2.2, Tabla 68) -- tipo_agregado, agregado_id,
version por agregado, version_esquema y encadenamiento con valor resumen
con clave (hash_evento); ademas, separacion de roles del gestor de base de
datos y disparador que bloquea el vaciado de la tabla (AD-11, RAS-11,
RNF-18, control C-10).

Revision ID: 64c81a12524c
Revises: de94aaa2d321
Create Date: 2026-11-08 00:00:00.000000

"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "64c81a12524c"
down_revision: str | Sequence[str] | None = "de94aaa2d321"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Mismo patron que CLAVE_CIFRADO_SESIONES (Fase 15): la clave de
# encadenamiento reside fuera de la base de datos (AD-11). Para el
# backfill de las filas existentes se necesita el mismo valor con el que
# el backend firmara los eventos nuevos a partir de esta migracion, por
# eso se lee de la misma variable de entorno que leera la aplicacion.
_CLAVE_HMAC_EVENTOS = os.environ.get(
    "CLAVE_HMAC_EVENTOS", ""
).encode("utf-8")
_GENESIS = "0" * 64


def _instante_canonico(instante: datetime) -> str:
    """Misma normalizacion que
    app/infraestructura/persistencia/cadena_eventos.py::_instante_canonico
    (duplicada a proposito: las migraciones de este proyecto no importan
    codigo de la aplicacion, para quedar fijas en el tiempo aunque ese
    codigo cambie despues) -- sin ella, dos calculos del mismo evento con
    tzinfo representado distinto producirian hashes distintos."""

    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(UTC).isoformat()


def _hash_evento(hash_anterior: str, fila: dict[str, object]) -> str:
    base = "|".join(
        str(fila[campo]) if campo != "ocurrido_en" else _instante_canonico(fila[campo])  # type: ignore[arg-type]
        for campo in (
            "tipo_agregado",
            "agregado_id",
            "version",
            "tipo_evento",
            "actor",
            "estado_previo",
            "estado_nuevo",
            "ocurrido_en",
        )
    )
    mensaje = f"{hash_anterior}|{base}".encode()
    return hmac.new(_CLAVE_HMAC_EVENTOS, mensaje, hashlib.sha256).hexdigest()


def _backfill_agregado(conexion: sa.Connection) -> None:
    """Deriva tipo_agregado/agregado_id de las filas ya existentes, a
    partir de las columnas y del payload con los que ya se escribian
    (cuenta_medica_id, o "lote_id" dentro de datos). Las dos categorias
    de eventos de sesion que no llevaban ningun identificador propio
    (SESION_CERRADA, SESION_PLATAFORMA_*) quedan con agregado_id=0 como
    marca explicita de dato preexistente a esta fase -- son datos
    sinteticos de desarrollo, no se reconstruyen con precision retroactiva."""

    conexion.execute(
        sa.text(
            "UPDATE evento SET tipo_agregado = 'CUENTA', agregado_id = cuenta_medica_id "
            "WHERE cuenta_medica_id IS NOT NULL"
        )
    )
    conexion.execute(
        sa.text(
            "UPDATE evento SET tipo_agregado = 'LOTE', "
            "agregado_id = (datos->>'lote_id')::integer "
            "WHERE cuenta_medica_id IS NULL AND datos::jsonb ? 'lote_id'"
        )
    )
    conexion.execute(
        sa.text(
            "UPDATE evento SET tipo_agregado = 'SESION_USUARIO', agregado_id = 0 "
            "WHERE tipo_agregado IS NULL AND tipo_evento = 'SESION_CERRADA'"
        )
    )
    conexion.execute(
        sa.text(
            "UPDATE evento SET tipo_agregado = 'SESION_PLATAFORMA', agregado_id = 0 "
            "WHERE tipo_agregado IS NULL AND tipo_evento LIKE 'SESION_PLATAFORMA_%'"
        )
    )
    # Cualquier fila que no haya calzado en ninguna regla anterior (no se
    # esperan, es una red de seguridad para no dejar NULL).
    conexion.execute(
        sa.text(
            "UPDATE evento SET tipo_agregado = 'SESION_USUARIO', agregado_id = 0 "
            "WHERE tipo_agregado IS NULL"
        )
    )


def _backfill_version_y_hash(conexion: sa.Connection) -> None:
    filas = (
        conexion.execute(
            sa.text(
                "SELECT id, tipo_agregado, agregado_id, tipo_evento, actor, "
                "estado_previo, estado_nuevo, ocurrido_en FROM evento ORDER BY id"
            )
        )
        .mappings()
        .all()
    )

    ultimo_hash: dict[tuple[str, int], str] = {}
    ultima_version: dict[tuple[str, int], int] = {}
    for fila in filas:
        clave = (fila["tipo_agregado"], fila["agregado_id"])
        version = ultima_version.get(clave, 0) + 1
        hash_anterior = ultimo_hash.get(clave, _GENESIS)
        hash_nuevo = _hash_evento(hash_anterior, dict(fila) | {"version": version})
        conexion.execute(
            sa.text("UPDATE evento SET version = :version, hash_evento = :hash WHERE id = :id"),
            {"version": version, "hash": hash_nuevo, "id": fila["id"]},
        )
        ultima_version[clave] = version
        ultimo_hash[clave] = hash_nuevo


def upgrade() -> None:
    """Upgrade schema."""
    conexion = op.get_bind()

    # 1. Columnas del modelo generico de agregado (Tabla 68). El backfill
    # de mas abajo necesita recorrer la tabla en el orden de insercion
    # original, por eso corre mientras la columna "id" (entero,
    # autoincremental) todavia existe -- el cambio de "id" a "evento_id"
    # (UUID) es el paso 3, al final.
    op.add_column("evento", sa.Column("tipo_agregado", sa.String(30), nullable=True))
    op.add_column("evento", sa.Column("agregado_id", sa.Integer(), nullable=True))
    op.add_column("evento", sa.Column("version", sa.Integer(), nullable=True))
    op.add_column(
        "evento",
        sa.Column("version_esquema", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("evento", sa.Column("hash_evento", sa.String(64), nullable=True))

    # Los disparadores de la Fase 7 (trg_evento_sin_update/sin_delete)
    # bloquearian tambien el UPDATE del backfill de abajo, que no es una
    # alteracion de un evento ya firmado sino la migracion unica que lo
    # completa con las columnas nuevas; se desactivan solo para este
    # tramo de la propia migracion.
    op.execute("ALTER TABLE evento DISABLE TRIGGER trg_evento_sin_update")
    _backfill_agregado(conexion)
    _backfill_version_y_hash(conexion)

    op.alter_column("evento", "tipo_agregado", nullable=False)
    op.alter_column("evento", "agregado_id", nullable=False)
    op.alter_column("evento", "version", nullable=False)
    op.alter_column("evento", "hash_evento", nullable=False)

    op.create_check_constraint(
        "ck_evento_tipo_agregado",
        "evento",
        "tipo_agregado IN ('CUENTA','LOTE','SESION_USUARIO','SESION_PLATAFORMA')",
    )
    op.create_check_constraint("ck_evento_version_positiva", "evento", "version > 0")
    op.create_unique_constraint(
        "uq_evento_agregado_version", "evento", ["tipo_agregado", "agregado_id", "version"]
    )
    op.create_index("ix_evento_agregado", "evento", ["tipo_agregado", "agregado_id"], unique=False)

    # cuenta_medica_id se conserva como columna de conveniencia para las
    # consultas existentes de OE1 (bandeja de cuentas, etc.), pero deja de
    # ser la fuente de verdad del agregado: ahora se recalcula desde las
    # columnas genericas, para que un evento de tipo LOTE no quede con un
    # valor NULL inconsistente con tipo_agregado/agregado_id.
    op.execute(
        "UPDATE evento SET cuenta_medica_id = agregado_id WHERE tipo_agregado = 'CUENTA' "
        "AND cuenta_medica_id IS NULL"
    )
    op.execute("ALTER TABLE evento ENABLE TRIGGER trg_evento_sin_update")

    # 2. evento_id generico (UUID), ahora que el backfill ya uso "id" para
    # ordenar: ninguna otra tabla referencia evento.id por clave foranea,
    # asi que el cambio de tipo es seguro.
    op.add_column(
        "evento",
        sa.Column(
            "evento_id",
            sa.Uuid(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.execute("ALTER TABLE evento DROP CONSTRAINT evento_pkey")
    op.execute("ALTER TABLE evento ADD PRIMARY KEY (evento_id)")
    op.drop_column("evento", "id")

    # 3. Disparador que bloquea tambien el vaciado de la tabla (TRUNCATE),
    # el tercer mecanismo de inmutabilidad que la Fase 7 no cubria (solo
    # UPDATE y DELETE).
    op.execute(
        """
        CREATE TRIGGER trg_evento_sin_truncate
        BEFORE TRUNCATE ON evento
        FOR EACH STATEMENT EXECUTE FUNCTION fn_evento_inmutable();
        """
    )

    # 4. Separacion de roles del gestor de base de datos (AD-11, RAS-11):
    # un rol dueño del esquema, distinto de la cuenta de aplicacion, y un
    # rol de administracion operativa sin privilegios sobre la tabla.
    # Idempotente (DO/EXCEPTION) porque CREATE ROLE no admite IF NOT
    # EXISTS en todas las versiones y esta migracion puede correr sobre
    # una base ya preparada en un entorno de desarrollo reiniciado.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'oe1_dueno_esquema') THEN
                CREATE ROLE oe1_dueno_esquema NOLOGIN;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'oe1_administracion_operativa'
            ) THEN
                CREATE ROLE oe1_administracion_operativa NOLOGIN;
            END IF;
        END
        $$;
        """
    )
    op.execute("ALTER TABLE evento OWNER TO oe1_dueno_esquema")
    op.execute("REVOKE ALL ON evento FROM PUBLIC")
    op.execute("REVOKE ALL ON evento FROM oe1_administracion_operativa")
    _rol_aplicacion = os.environ.get("POSTGRES_USER", "gestion_cuentas")
    op.execute(f"GRANT SELECT, INSERT ON evento TO {_rol_aplicacion}")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_evento_sin_truncate ON evento;")
    _rol_aplicacion = os.environ.get("POSTGRES_USER", "gestion_cuentas")
    op.execute(f"ALTER TABLE evento OWNER TO {_rol_aplicacion}")
    op.drop_index("ix_evento_agregado", table_name="evento")
    op.drop_constraint("uq_evento_agregado_version", "evento", type_="unique")
    op.drop_constraint("ck_evento_version_positiva", "evento", type_="check")
    op.drop_constraint("ck_evento_tipo_agregado", "evento", type_="check")
    op.drop_column("evento", "hash_evento")
    op.drop_column("evento", "version_esquema")
    op.drop_column("evento", "version")
    op.drop_column("evento", "agregado_id")
    op.drop_column("evento", "tipo_agregado")
    op.execute("ALTER TABLE evento DROP CONSTRAINT evento_pkey")
    op.add_column("evento", sa.Column("id", sa.Integer(), autoincrement=True))
    op.execute("ALTER TABLE evento ADD PRIMARY KEY (id)")
    op.drop_column("evento", "evento_id")
