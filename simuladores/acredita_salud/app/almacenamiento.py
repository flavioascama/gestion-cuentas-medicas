"""Persistencia del simulador: SQLite local (mismo patron que
simuladores/receptor_iafas/app/almacenamiento.py -- Regla 0.5, sin
compartir base de datos con el backend). Guarda lo que las pantallas de
'Auditoria, Trazabilidad y Descargas' necesitan listar despues:
acreditaciones generadas, declaraciones de siniestro, derivaciones y
cartas de garantia."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Acreditacion:
    codigo_autorizacion: str
    tipo_documento: str
    numero_documento: str
    nombre_asegurado: str
    iafas_codigo: str
    ipress_codigo: str
    condicion_cobertura: str
    tipo_copago: str | None
    monto_copago_fijo: float | None
    porcentaje_coaseguro: int | None
    generado_en: str


@dataclass(frozen=True, slots=True)
class CartaGarantia:
    numero_carta: str
    tipo_documento: str
    numero_documento: str
    nombre_asegurado: str
    monto: float
    estado: str
    fecha_emision: str
    fecha_vencimiento: str
    motivo: str


class Almacenamiento:
    def __init__(self, ruta: Path) -> None:
        self._ruta = ruta
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self._conexion() as conexion:
            conexion.executescript(
                """
                CREATE TABLE IF NOT EXISTS acreditacion (
                    codigo_autorizacion TEXT PRIMARY KEY,
                    tipo_documento TEXT NOT NULL,
                    numero_documento TEXT NOT NULL,
                    nombre_asegurado TEXT NOT NULL,
                    iafas_codigo TEXT NOT NULL,
                    ipress_codigo TEXT NOT NULL,
                    condicion_cobertura TEXT NOT NULL,
                    tipo_copago TEXT,
                    monto_copago_fijo REAL,
                    porcentaje_coaseguro INTEGER,
                    generado_en TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS siniestro (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo_documento TEXT NOT NULL,
                    numero_documento TEXT NOT NULL,
                    fecha_siniestro TEXT NOT NULL,
                    descripcion TEXT NOT NULL,
                    registrado_en TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS derivacion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo_documento TEXT NOT NULL,
                    numero_documento TEXT NOT NULL,
                    ipress_origen TEXT NOT NULL,
                    ipress_destino TEXT NOT NULL,
                    motivo TEXT NOT NULL,
                    registrado_en TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS carta_garantia (
                    numero_carta TEXT PRIMARY KEY,
                    tipo_documento TEXT NOT NULL,
                    numero_documento TEXT NOT NULL,
                    nombre_asegurado TEXT NOT NULL,
                    monto REAL NOT NULL,
                    estado TEXT NOT NULL,
                    fecha_emision TEXT NOT NULL,
                    fecha_vencimiento TEXT NOT NULL,
                    motivo TEXT NOT NULL
                );
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

    # --- acreditaciones ---------------------------------------------

    def registrar_acreditacion(self, acreditacion: Acreditacion) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                """
                INSERT INTO acreditacion
                    (codigo_autorizacion, tipo_documento, numero_documento,
                     nombre_asegurado, iafas_codigo, ipress_codigo,
                     condicion_cobertura, tipo_copago, monto_copago_fijo,
                     porcentaje_coaseguro, generado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    acreditacion.codigo_autorizacion,
                    acreditacion.tipo_documento,
                    acreditacion.numero_documento,
                    acreditacion.nombre_asegurado,
                    acreditacion.iafas_codigo,
                    acreditacion.ipress_codigo,
                    acreditacion.condicion_cobertura,
                    acreditacion.tipo_copago,
                    acreditacion.monto_copago_fijo,
                    acreditacion.porcentaje_coaseguro,
                    acreditacion.generado_en,
                ),
            )

    def contar_acreditaciones(self) -> int:
        with self._conexion() as conexion:
            (cantidad,) = conexion.execute("SELECT COUNT(*) FROM acreditacion").fetchone()
            return int(cantidad)

    def obtener_acreditacion(self, codigo_autorizacion: str) -> Acreditacion | None:
        with self._conexion() as conexion:
            conexion.row_factory = sqlite3.Row
            fila = conexion.execute(
                "SELECT * FROM acreditacion WHERE codigo_autorizacion = ?",
                (codigo_autorizacion,),
            ).fetchone()
            return _fila_a_acreditacion(fila) if fila else None

    def buscar_acreditaciones(
        self,
        ipress_codigo: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        codigo_autorizacion: str | None = None,
    ) -> list[Acreditacion]:
        condiciones = []
        parametros: list[object] = []
        if ipress_codigo:
            condiciones.append("ipress_codigo = ?")
            parametros.append(ipress_codigo)
        if desde:
            condiciones.append("date(generado_en) >= date(?)")
            parametros.append(desde.isoformat())
        if hasta:
            condiciones.append("date(generado_en) <= date(?)")
            parametros.append(hasta.isoformat())
        if codigo_autorizacion:
            condiciones.append("codigo_autorizacion = ?")
            parametros.append(codigo_autorizacion)

        consulta = "SELECT * FROM acreditacion"
        if condiciones:
            consulta += " WHERE " + " AND ".join(condiciones)
        consulta += " ORDER BY generado_en DESC"

        with self._conexion() as conexion:
            conexion.row_factory = sqlite3.Row
            filas = conexion.execute(consulta, parametros).fetchall()
            return [_fila_a_acreditacion(f) for f in filas]

    # --- atenciones accidentales y derivaciones ----------------------

    def registrar_siniestro(
        self, tipo_documento: str, numero_documento: str, fecha_siniestro: str, descripcion: str
    ) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT INTO siniestro "
                "(tipo_documento, numero_documento, fecha_siniestro, descripcion, registrado_en) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    tipo_documento,
                    numero_documento,
                    fecha_siniestro,
                    descripcion,
                    datetime.now().isoformat(),
                ),
            )

    def registrar_derivacion(
        self,
        tipo_documento: str,
        numero_documento: str,
        ipress_origen: str,
        ipress_destino: str,
        motivo: str,
    ) -> None:
        with self._conexion() as conexion:
            conexion.execute(
                "INSERT INTO derivacion "
                "(tipo_documento, numero_documento, ipress_origen, ipress_destino, motivo, "
                " registrado_en) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    tipo_documento,
                    numero_documento,
                    ipress_origen,
                    ipress_destino,
                    motivo,
                    datetime.now().isoformat(),
                ),
            )

    # --- cartas de garantia -------------------------------------------

    def sembrar_cartas_garantia_si_vacio(self, cartas: list[CartaGarantia]) -> None:
        with self._conexion() as conexion:
            (cantidad,) = conexion.execute("SELECT COUNT(*) FROM carta_garantia").fetchone()
            if cantidad > 0:
                return
            conexion.executemany(
                "INSERT INTO carta_garantia "
                "(numero_carta, tipo_documento, numero_documento, nombre_asegurado, monto, "
                " estado, fecha_emision, fecha_vencimiento, motivo) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        c.numero_carta,
                        c.tipo_documento,
                        c.numero_documento,
                        c.nombre_asegurado,
                        c.monto,
                        c.estado,
                        c.fecha_emision,
                        c.fecha_vencimiento,
                        c.motivo,
                    )
                    for c in cartas
                ],
            )

    def buscar_cartas_garantia(
        self, numero_documento: str | None = None, numero_carta: str | None = None
    ) -> list[CartaGarantia]:
        condiciones = []
        parametros: list[object] = []
        if numero_documento:
            condiciones.append("numero_documento = ?")
            parametros.append(numero_documento)
        if numero_carta:
            condiciones.append("numero_carta = ?")
            parametros.append(numero_carta)

        consulta = "SELECT * FROM carta_garantia"
        if condiciones:
            consulta += " WHERE " + " AND ".join(condiciones)
        consulta += " ORDER BY numero_carta"

        with self._conexion() as conexion:
            conexion.row_factory = sqlite3.Row
            filas = conexion.execute(consulta, parametros).fetchall()
            return [
                CartaGarantia(
                    numero_carta=f["numero_carta"],
                    tipo_documento=f["tipo_documento"],
                    numero_documento=f["numero_documento"],
                    nombre_asegurado=f["nombre_asegurado"],
                    monto=f["monto"],
                    estado=f["estado"],
                    fecha_emision=f["fecha_emision"],
                    fecha_vencimiento=f["fecha_vencimiento"],
                    motivo=f["motivo"],
                )
                for f in filas
            ]


def _fila_a_acreditacion(fila: sqlite3.Row) -> Acreditacion:
    return Acreditacion(
        codigo_autorizacion=fila["codigo_autorizacion"],
        tipo_documento=fila["tipo_documento"],
        numero_documento=fila["numero_documento"],
        nombre_asegurado=fila["nombre_asegurado"],
        iafas_codigo=fila["iafas_codigo"],
        ipress_codigo=fila["ipress_codigo"],
        condicion_cobertura=fila["condicion_cobertura"],
        tipo_copago=fila["tipo_copago"],
        monto_copago_fijo=fila["monto_copago_fijo"],
        porcentaje_coaseguro=fila["porcentaje_coaseguro"],
        generado_en=fila["generado_en"],
    )
