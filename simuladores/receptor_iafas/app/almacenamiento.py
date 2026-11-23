"""Persistencia del simulador: SQLite local, no Postgres.

Este simulador es una aplicacion independiente y deterministica (Seccion 9)
cuyo unico consumidor es el propio portal y, indirectamente, el robot de
monitoreo de la Fase 12 via HTTP. No necesita el modelo relacional completo
del backend ni compartir su base de datos (Regla 0.5): una tabla en SQLite,
en un archivo dentro de un volumen del contenedor, alcanza y evita una
dependencia a Postgres solo para esto.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LoteRecibido:
    id: int
    nombre_archivo: str
    numero_lote: str | None
    codigo_iafas: str | None
    codigo_ipress: str | None
    recibido_en: str
    estado: str
    motivo: str | None


class AlmacenamientoReceptor:
    def __init__(self, ruta_base_datos: Path) -> None:
        self._ruta = ruta_base_datos
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as conexion:
            conexion.execute(
                """
                CREATE TABLE IF NOT EXISTS lote_recibido (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre_archivo TEXT NOT NULL UNIQUE,
                    numero_lote TEXT,
                    codigo_iafas TEXT,
                    codigo_ipress TEXT,
                    recibido_en TEXT NOT NULL,
                    estado TEXT NOT NULL,
                    motivo TEXT,
                    forzado INTEGER NOT NULL DEFAULT 0
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

    def registrar(
        self,
        nombre_archivo: str,
        estado: str,
        motivo: str | None,
        numero_lote: str | None,
        codigo_iafas: str | None,
        codigo_ipress: str | None,
    ) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                """
                INSERT INTO lote_recibido
                    (nombre_archivo, numero_lote, codigo_iafas, codigo_ipress,
                     recibido_en, estado, motivo, forzado)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(nombre_archivo) DO UPDATE SET
                    numero_lote=excluded.numero_lote,
                    codigo_iafas=excluded.codigo_iafas,
                    codigo_ipress=excluded.codigo_ipress,
                    recibido_en=excluded.recibido_en,
                    estado=excluded.estado,
                    motivo=excluded.motivo,
                    forzado=0
                """,
                (
                    nombre_archivo,
                    numero_lote,
                    codigo_iafas,
                    codigo_ipress,
                    datetime.now().isoformat(),
                    estado,
                    motivo,
                ),
            )

    def responder(self, nombre_archivo: str, estado: str, motivo: str | None) -> bool:
        """La respuesta de la IAFAS a un lote recibido. Se registra una
        sola vez: False si el lote no existe o ya fue respondido."""

        with self._conexion() as conexion:
            cursor = conexion.execute(
                "UPDATE lote_recibido SET estado = ?, motivo = ? "
                "WHERE nombre_archivo = ? AND estado = 'RECIBIDO'",
                (estado, motivo, nombre_archivo),
            )
            return cursor.rowcount > 0

    def listar(self) -> list[LoteRecibido]:
        with self._conexion() as conexion:
            conexion.row_factory = sqlite3.Row
            filas = conexion.execute(
                "SELECT * FROM lote_recibido ORDER BY recibido_en DESC"
            ).fetchall()
            return [
                LoteRecibido(
                    id=f["id"],
                    nombre_archivo=f["nombre_archivo"],
                    numero_lote=f["numero_lote"],
                    codigo_iafas=f["codigo_iafas"],
                    codigo_ipress=f["codigo_ipress"],
                    recibido_en=f["recibido_en"],
                    estado=f["estado"],
                    motivo=f["motivo"],
                )
                for f in filas
            ]

    def obtener(self, nombre_archivo: str) -> LoteRecibido | None:
        with self._conexion() as conexion:
            conexion.row_factory = sqlite3.Row
            f = conexion.execute(
                "SELECT * FROM lote_recibido WHERE nombre_archivo = ?", (nombre_archivo,)
            ).fetchone()
            if f is None:
                return None
            return LoteRecibido(
                id=f["id"],
                nombre_archivo=f["nombre_archivo"],
                numero_lote=f["numero_lote"],
                codigo_iafas=f["codigo_iafas"],
                codigo_ipress=f["codigo_ipress"],
                recibido_en=f["recibido_en"],
                estado=f["estado"],
                motivo=f["motivo"],
            )
