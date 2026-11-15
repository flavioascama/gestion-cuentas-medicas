"""Persistencia del simulador: SQLite local (mismo patron que
simuladores/acredita_salud/app/almacenamiento.py y
simuladores/receptor_iafas/app/almacenamiento.py -- Regla 0.5, sin
compartir base de datos con el backend ni con otro simulador).

Estados de `lote` (Seccion 9.2): RECHAZADO_FORMA (no aparece en "Lotes por
Validar", solo queda para descargar sus observaciones), REGISTRADO,
VALIDANDO (segundo plano), VALIDADO (pasa a "Lotes por Enviar"),
OBSERVADO_DETALLADA (vuelve a "Lotes por Validar" con "Error de
Validacion-XLS"), ENVIADO, ELIMINADO. No incluye REENVIADO: la opcion
"Recargar" del validador queda fuera de esta version (Seccion 16, supuesto
4 del plan); toda correccion registra un lote nuevo.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.revision_forma import IdentidadLote, ObservacionForma
from app.validacion_detallada import ObservacionDetallada

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS lote (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruc TEXT NOT NULL,
    codigo_ipress TEXT NOT NULL,
    codigo_iafas TEXT NOT NULL,
    numero_lote TEXT NOT NULL,
    periodo TEXT NOT NULL,
    fecha TEXT NOT NULL,
    estado TEXT NOT NULL,
    registrado_en TEXT NOT NULL,
    usuario_registro TEXT NOT NULL,
    validar_listo_en TEXT,
    validado_en TEXT,
    enviado_en TEXT,
    eliminado_en TEXT,
    usuario_eliminacion TEXT,
    nombre_s01 TEXT,
    contenido_s01 BLOB,
    tamano_total_bytes INTEGER NOT NULL DEFAULT 0,
    total_registros INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS lote_archivo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id INTEGER NOT NULL REFERENCES lote(id) ON DELETE CASCADE,
    tabla TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    contenido BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS observacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id INTEGER NOT NULL REFERENCES lote(id) ON DELETE CASCADE,
    etapa TEXT NOT NULL,
    tabla TEXT,
    numero_linea INTEGER,
    campo_clave TEXT,
    campo TEXT,
    valor_observado TEXT,
    codigo_error TEXT NOT NULL,
    descripcion TEXT NOT NULL
);
"""

_ESTADOS_POR_VALIDAR = ("REGISTRADO", "VALIDANDO", "OBSERVADO_DETALLADA")


@dataclass(frozen=True, slots=True)
class LoteDB:
    id: int
    identidad: IdentidadLote
    estado: str
    registrado_en: str
    usuario_registro: str
    validar_listo_en: str | None
    nombre_s01: str | None
    tamano_total_bytes: int
    total_registros: int
    eliminado_en: str | None
    usuario_eliminacion: str | None


def _fila_a_lote(fila: sqlite3.Row) -> LoteDB:
    identidad = IdentidadLote(
        ruc=fila["ruc"],
        codigo_ipress=fila["codigo_ipress"],
        codigo_iafas=fila["codigo_iafas"],
        numero_lote=fila["numero_lote"],
        periodo=fila["periodo"],
        fecha=fila["fecha"],
    )
    return LoteDB(
        id=fila["id"],
        identidad=identidad,
        estado=fila["estado"],
        registrado_en=fila["registrado_en"],
        usuario_registro=fila["usuario_registro"],
        validar_listo_en=fila["validar_listo_en"],
        nombre_s01=fila["nombre_s01"],
        tamano_total_bytes=fila["tamano_total_bytes"],
        total_registros=fila["total_registros"],
        eliminado_en=fila["eliminado_en"],
        usuario_eliminacion=fila["usuario_eliminacion"],
    )


class AlmacenamientoTedefWeb:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as conexion:
            conexion.executescript(_ESQUEMA)

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        conexion = sqlite3.connect(self._ruta)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        try:
            yield conexion
            conexion.commit()
        finally:
            conexion.close()

    def existe_lote_activo(self, identidad: IdentidadLote) -> bool:
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT 1 FROM lote WHERE ruc = ? AND codigo_ipress = ? AND codigo_iafas = ? "
                "AND numero_lote = ? AND periodo = ? AND fecha = ? AND estado != 'ELIMINADO'",
                (
                    identidad.ruc,
                    identidad.codigo_ipress,
                    identidad.codigo_iafas,
                    identidad.numero_lote,
                    identidad.periodo,
                    identidad.fecha,
                ),
            ).fetchone()
            return fila is not None

    def registrar_intento(
        self,
        identidad: IdentidadLote,
        estado: str,
        archivos: dict[str, tuple[str, bytes]],
        usuario: str,
    ) -> int:
        total_bytes = sum(len(contenido) for _nombre, contenido in archivos.values())
        total_registros = sum(
            len(contenido.decode("ascii", errors="ignore").splitlines())
            for _nombre, contenido in archivos.values()
        )
        with self._conexion() as conexion:
            cursor = conexion.execute(
                "INSERT INTO lote (ruc, codigo_ipress, codigo_iafas, numero_lote, periodo, fecha, "
                "estado, registrado_en, usuario_registro, tamano_total_bytes, total_registros) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    identidad.ruc,
                    identidad.codigo_ipress,
                    identidad.codigo_iafas,
                    identidad.numero_lote,
                    identidad.periodo,
                    identidad.fecha,
                    estado,
                    datetime.now().isoformat(),
                    usuario,
                    total_bytes,
                    total_registros,
                ),
            )
            lote_id = int(cursor.lastrowid)  # type: ignore[arg-type]
            for tabla, (nombre, contenido) in archivos.items():
                conexion.execute(
                    "INSERT INTO lote_archivo (lote_id, tabla, nombre_archivo, contenido) "
                    "VALUES (?, ?, ?, ?)",
                    (lote_id, tabla, nombre, contenido),
                )
            return lote_id

    def registrar_observaciones_forma(
        self, lote_id: int, observaciones: tuple[ObservacionForma, ...]
    ) -> None:
        with self._conexion() as conexion:
            conexion.executemany(
                "INSERT INTO observacion (lote_id, etapa, tabla, codigo_error, descripcion) "
                "VALUES (?, 'FORMA', ?, ?, ?)",
                [(lote_id, obs.tabla, obs.codigo_error, obs.descripcion) for obs in observaciones],
            )

    def registrar_observaciones_detalladas(
        self, lote_id: int, observaciones: list[ObservacionDetallada]
    ) -> None:
        with self._conexion() as conexion:
            conexion.executemany(
                "INSERT INTO observacion (lote_id, etapa, tabla, numero_linea, campo_clave, "
                "campo, valor_observado, codigo_error, descripcion) "
                "VALUES (?, 'DETALLADA', ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        lote_id,
                        obs.tabla,
                        obs.numero_linea,
                        obs.campo_clave,
                        obs.campo,
                        obs.valor_observado,
                        obs.codigo_error,
                        obs.descripcion,
                    )
                    for obs in observaciones
                ],
            )

    def marcar_validando(self, lote_id: int, listo_en: datetime) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "UPDATE lote SET estado = 'VALIDANDO', validar_listo_en = ? WHERE id = ?",
                (listo_en.isoformat(), lote_id),
            )

    def marcar_validado(self, lote_id: int, nombre_s01: str, contenido_s01: bytes) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "UPDATE lote SET estado = 'VALIDADO', validado_en = ?, nombre_s01 = ?, "
                "contenido_s01 = ? WHERE id = ?",
                (datetime.now().isoformat(), nombre_s01, contenido_s01, lote_id),
            )

    def marcar_observado_detallada(self, lote_id: int) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "UPDATE lote SET estado = 'OBSERVADO_DETALLADA' WHERE id = ?", (lote_id,)
            )

    def marcar_enviado(self, lote_id: int) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "UPDATE lote SET estado = 'ENVIADO', enviado_en = ? WHERE id = ?",
                (datetime.now().isoformat(), lote_id),
            )

    def eliminar(self, lote_id: int, usuario: str) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "UPDATE lote SET estado = 'ELIMINADO', eliminado_en = ?, usuario_eliminacion = ? "
                "WHERE id = ?",
                (datetime.now().isoformat(), usuario, lote_id),
            )

    def obtener(self, lote_id: int) -> LoteDB | None:
        with self._conexion() as conexion:
            fila = conexion.execute("SELECT * FROM lote WHERE id = ?", (lote_id,)).fetchone()
            return _fila_a_lote(fila) if fila else None

    def _listar_por_estados(self, estados: tuple[str, ...]) -> list[LoteDB]:
        marcadores = ",".join("?" for _ in estados)
        with self._conexion() as conexion:
            filas = conexion.execute(
                f"SELECT * FROM lote WHERE estado IN ({marcadores}) ORDER BY registrado_en DESC",
                estados,
            ).fetchall()
            return [_fila_a_lote(f) for f in filas]

    def listar_por_validar(self) -> list[LoteDB]:
        return self._listar_por_estados(_ESTADOS_POR_VALIDAR)

    def listar_por_enviar(self) -> list[LoteDB]:
        return self._listar_por_estados(("VALIDADO",))

    def listar_enviados(self) -> list[LoteDB]:
        return self._listar_por_estados(("ENVIADO",))

    def listar_eliminados(self) -> list[LoteDB]:
        return self._listar_por_estados(("ELIMINADO",))

    def archivos_de(self, lote_id: int) -> list[tuple[str, str, bytes]]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                "SELECT tabla, nombre_archivo, contenido FROM lote_archivo WHERE lote_id = ? "
                "ORDER BY tabla",
                (lote_id,),
            ).fetchall()
            return [(f["tabla"], f["nombre_archivo"], f["contenido"]) for f in filas]

    def contenido_s01(self, lote_id: int) -> bytes | None:
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT contenido_s01 FROM lote WHERE id = ?", (lote_id,)
            ).fetchone()
            return fila["contenido_s01"] if fila else None

    def observaciones_de(self, lote_id: int, etapa: str) -> list[dict[str, Any]]:
        with self._conexion() as conexion:
            filas = conexion.execute(
                "SELECT * FROM observacion WHERE lote_id = ? AND etapa = ? ORDER BY id",
                (lote_id, etapa),
            ).fetchall()
            return [dict(f) for f in filas]
