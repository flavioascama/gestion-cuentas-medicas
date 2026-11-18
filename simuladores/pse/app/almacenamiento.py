"""Persistencia del simulador: SQLite local, no Postgres (mismo criterio
que simuladores/receptor_iafas/app/almacenamiento.py: aplicacion
independiente y deterministica, sin dependencia a Postgres).

Solo guarda contadores: el numero de comprobante emitido crece de uno en
uno y nunca se reutiliza, incluso si el contenedor se reinicia (evita
choques contra la restriccion unique (ipress_id, tipo_documento_pago,
serie, numero) de documento_facturador en el backend). Las notas de
credito y de debito llevan su propio contador, uno por serie."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class AlmacenamientoPse:
    def __init__(self, ruta_base_datos: Path) -> None:
        self._ruta = ruta_base_datos
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as conexion:
            conexion.execute(
                """
                CREATE TABLE IF NOT EXISTS contador_comprobante (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    ultimo_numero INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conexion.execute(
                "INSERT OR IGNORE INTO contador_comprobante (id, ultimo_numero) VALUES (1, 0)"
            )
            conexion.execute(
                """
                CREATE TABLE IF NOT EXISTS contador_nota (
                    serie TEXT PRIMARY KEY,
                    ultimo_numero INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        conexion = sqlite3.connect(self._ruta)
        try:
            yield conexion
            conexion.commit()
        finally:
            conexion.close()

    def siguiente_numero(self) -> str:
        with self._conexion() as conexion:
            conexion.execute(
                "UPDATE contador_comprobante SET ultimo_numero = ultimo_numero + 1 WHERE id = 1"
            )
            (ultimo_numero,) = conexion.execute(
                "SELECT ultimo_numero FROM contador_comprobante WHERE id = 1"
            ).fetchone()
        return f"{ultimo_numero:08d}"

    def siguiente_numero_nota(self, serie: str) -> str:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT OR IGNORE INTO contador_nota (serie, ultimo_numero) VALUES (?, 0)",
                (serie,),
            )
            conexion.execute(
                "UPDATE contador_nota SET ultimo_numero = ultimo_numero + 1 WHERE serie = ?",
                (serie,),
            )
            (ultimo_numero,) = conexion.execute(
                "SELECT ultimo_numero FROM contador_nota WHERE serie = ?", (serie,)
            ).fetchone()
        return f"{ultimo_numero:08d}"
