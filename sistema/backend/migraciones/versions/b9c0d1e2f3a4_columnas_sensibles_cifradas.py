"""columnas sensibles cifradas en reposo

C-05, RNF-16 y Ley 29733 art. 16 (verificacion de cumplimiento,
2026-11-12): la identidad del asegurado y los datos clinicos de la cuenta
se cifran con Fernet (clave CLAVE_CIFRADO_DATOS, fuera de la base). La
unicidad del documento pasa a un indice ciego (HMAC-SHA256), porque el
texto cifrado no es determinista. Los datos ya registrados se cifran aqui.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-11-13 21:00:00.000000

"""

from __future__ import annotations

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.infraestructura.persistencia.cifrado_columnas import (
    LONGITUD_COLUMNA_CIFRADA,
    cifrar_texto,
    descifrar_texto,
    indice_ciego,
)

# revision identifiers, used by Alembic.
revision: str = "b9c0d1e2f3a4"
down_revision: str | Sequence[str] | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ASEGURADO = ("numero_documento", "nombres", "apellidos")
_CUENTA = ("numero_historia_clinica", "diagnostico_principal_cie10")


def _clave() -> str:
    clave = os.environ.get("CLAVE_CIFRADO_DATOS", "")
    if not clave:
        raise RuntimeError("Falta CLAVE_CIFRADO_DATOS en el entorno (.env).")
    return clave


def _ensanchar(tabla: str, columnas: tuple[str, ...], longitud: int) -> None:
    for columna in columnas:
        op.alter_column(tabla, columna, type_=sa.String(longitud))


def _transformar(tabla: str, columnas: tuple[str, ...], funcion: object) -> None:
    conexion = op.get_bind()
    filas = conexion.execute(sa.text(f"SELECT id, {', '.join(columnas)} FROM {tabla}")).all()
    for fila in filas:
        valores = {
            columna: (None if valor is None else funcion(valor))  # type: ignore[operator]
            for columna, valor in zip(columnas, fila[1:], strict=True)
        }
        asignaciones = ", ".join(f"{columna} = :{columna}" for columna in columnas)
        conexion.execute(
            sa.text(f"UPDATE {tabla} SET {asignaciones} WHERE id = :id"), {**valores, "id": fila[0]}
        )


def upgrade() -> None:
    """Upgrade schema."""
    clave = _clave()
    _ensanchar("asegurado", _ASEGURADO, LONGITUD_COLUMNA_CIFRADA)
    _ensanchar("cuenta_medica", _CUENTA, LONGITUD_COLUMNA_CIFRADA)
    op.add_column("asegurado", sa.Column("documento_indice", sa.String(64), nullable=True))
    conexion = op.get_bind()
    for id_, tipo, numero in conexion.execute(
        sa.text("SELECT id, tipo_documento, numero_documento FROM asegurado")
    ).all():
        conexion.execute(
            sa.text("UPDATE asegurado SET documento_indice = :indice WHERE id = :id"),
            {"indice": indice_ciego(tipo, numero, clave=clave), "id": id_},
        )
    _transformar("asegurado", _ASEGURADO, lambda valor: cifrar_texto(valor, clave))
    _transformar("cuenta_medica", _CUENTA, lambda valor: cifrar_texto(valor, clave))
    op.drop_constraint("uq_asegurado_documento", "asegurado", type_="unique")
    op.alter_column("asegurado", "documento_indice", nullable=False)
    op.create_unique_constraint("uq_asegurado_documento_indice", "asegurado", ["documento_indice"])


def downgrade() -> None:
    """Downgrade schema."""
    clave = _clave()
    _transformar("asegurado", _ASEGURADO, lambda valor: descifrar_texto(valor, clave))
    _transformar("cuenta_medica", _CUENTA, lambda valor: descifrar_texto(valor, clave))
    op.drop_constraint("uq_asegurado_documento_indice", "asegurado", type_="unique")
    op.drop_column("asegurado", "documento_indice")
    op.create_unique_constraint(
        "uq_asegurado_documento", "asegurado", ["tipo_documento", "numero_documento"]
    )
    for columna, longitud in (("numero_documento", 15), ("nombres", 150), ("apellidos", 150)):
        op.alter_column("asegurado", columna, type_=sa.String(longitud))
    op.alter_column("cuenta_medica", "numero_historia_clinica", type_=sa.String(8))
    op.alter_column("cuenta_medica", "diagnostico_principal_cie10", type_=sa.String(5))
