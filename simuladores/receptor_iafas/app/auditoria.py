"""Auditoria de la IAFAS sobre los lotes aceptados y sus comunicaciones a la
IPRESS: lo que en la realidad llega a la clinica por el portal de la
aseguradora o por correo (Tabla 42 de la tesis, actividades 10, 13 y 14 del
proceso actual: recepcion de la glosa, de la liquidacion y del pago).

Cada comprobante de un lote aceptado queda pendiente de auditoria. La
decision la toma el auditor de la IAFAS (en el portal o por la ruta de
administracion, para las pruebas): conformidad, glosa total o glosa
parcial. De cada decision salen comunicaciones con un codigo propio:

- conformidad: AUDITORIA_CONFORME, LIQUIDACION (monto facturado) y PAGO;
- glosa: OBSERVACION; al responder la IPRESS por el portal, la IAFAS acepta
  la respuesta (LIQUIDACION y PAGO) o, si asi se decidio, la mantiene una
  vez (nueva OBSERVACION, T-09 del sistema);
- glosa parcial: OBSERVACION parcial; con la respuesta, LIQUIDACION por lo
  no objetado y PAGO.

Cada comunicacion sale por el canal que se elija: el portal (siempre queda
publicada ahi) y, si el canal es CORREO, ademas un correo a la IPRESS con
la comunicacion adjunta en JSON."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

RESULTADOS_AUDITORIA = ("CONFORME", "GLOSA", "GLOSA_PARCIAL")
CANALES = ("PORTAL", "CORREO")
DECISIONES_RESPUESTA = ("ACEPTAR", "MANTENER")


@dataclass(frozen=True, slots=True)
class DocumentoAuditado:
    documento: str
    nombre_archivo: str
    codigo_iafas: str
    codigo_ipress: str
    monto_facturado: Decimal
    estado: str
    canal: str
    decision_respuesta: str
    # El comprobante que reemplazo al del lote, si la IPRESS refacturo.
    documento_vigente: str | None = None


@dataclass(frozen=True, slots=True)
class Comunicacion:
    codigo: str
    codigo_iafas: str
    codigo_ipress: str
    documento: str
    tipo: str
    datos: dict[str, Any]
    canal: str
    emitida_en: str
    respuesta_texto: str | None
    respondida_en: str | None
    # Nombre del documento que la IPRESS adjunto a su respuesta.
    respuesta_adjunto: str | None = None


class AuditoriaInvalidaError(Exception):
    pass


EnviarCorreo = Callable[[Comunicacion], None]


class AuditoriaIafas:
    def __init__(self, ruta_base_datos: Path, enviar_correo: EnviarCorreo | None = None) -> None:
        self._ruta = ruta_base_datos
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        self._enviar_correo = enviar_correo
        with self._conexion() as conexion:
            conexion.executescript(
                """
                CREATE TABLE IF NOT EXISTS documento_auditoria (
                    documento TEXT PRIMARY KEY,
                    nombre_archivo TEXT NOT NULL,
                    codigo_iafas TEXT NOT NULL,
                    codigo_ipress TEXT NOT NULL,
                    monto_facturado TEXT NOT NULL,
                    estado TEXT NOT NULL,
                    canal TEXT NOT NULL DEFAULT 'PORTAL',
                    decision_respuesta TEXT NOT NULL DEFAULT 'ACEPTAR',
                    observaciones_mantenidas INTEGER NOT NULL DEFAULT 0,
                    monto_glosado TEXT,
                    motivo_codigo TEXT
                );
                CREATE TABLE IF NOT EXISTS comunicacion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo TEXT UNIQUE,
                    codigo_iafas TEXT NOT NULL,
                    codigo_ipress TEXT NOT NULL,
                    documento TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    datos TEXT NOT NULL,
                    canal TEXT NOT NULL,
                    emitida_en TEXT NOT NULL,
                    respuesta_texto TEXT,
                    respuesta_sustento TEXT,
                    respondida_en TEXT
                );
                """
            )
            en_comunicacion = conexion.execute("PRAGMA table_info(comunicacion)").fetchall()
            if "respuesta_adjunto" not in [columna["name"] for columna in en_comunicacion]:
                conexion.execute(
                    "ALTER TABLE comunicacion ADD COLUMN respuesta_adjunto_nombre TEXT"
                )
                conexion.execute("ALTER TABLE comunicacion ADD COLUMN respuesta_adjunto BLOB")
            columnas = conexion.execute("PRAGMA table_info(documento_auditoria)").fetchall()
            if "documento_vigente" not in [columna["name"] for columna in columnas]:
                conexion.execute(
                    "ALTER TABLE documento_auditoria ADD COLUMN documento_vigente TEXT"
                )

    @contextmanager
    def _conexion(self) -> Iterator[sqlite3.Connection]:
        conexion = sqlite3.connect(self._ruta)
        conexion.row_factory = sqlite3.Row
        try:
            yield conexion
            conexion.commit()
        finally:
            conexion.close()

    # --- Comprobantes del lote aceptado ------------------------------------

    def registrar_documentos(
        self,
        nombre_archivo: str,
        codigo_iafas: str,
        codigo_ipress: str,
        documentos: list[tuple[str, Decimal]],
    ) -> None:
        """Un comprobante reenviado en otro lote vuelve a quedar pendiente."""
        with self._conexion() as conexion:
            for documento, monto in documentos:
                conexion.execute(
                    """
                    INSERT INTO documento_auditoria
                        (documento, nombre_archivo, codigo_iafas, codigo_ipress,
                         monto_facturado, estado)
                    VALUES (?, ?, ?, ?, ?, 'PENDIENTE')
                    ON CONFLICT(documento) DO UPDATE SET
                        nombre_archivo = excluded.nombre_archivo,
                        monto_facturado = excluded.monto_facturado,
                        documento_vigente = NULL,
                        estado = 'PENDIENTE',
                        observaciones_mantenidas = 0
                    """,
                    (documento, nombre_archivo, codigo_iafas, codigo_ipress, str(monto)),
                )

    def documentos(self, estado: str | None = None) -> list[DocumentoAuditado]:
        consulta = "SELECT * FROM documento_auditoria"
        parametros: tuple[str, ...] = ()
        if estado is not None:
            consulta += " WHERE estado = ?"
            parametros = (estado,)
        with self._conexion() as conexion:
            filas = conexion.execute(consulta + " ORDER BY documento", parametros).fetchall()
        return [_a_documento(fila) for fila in filas]

    def _documento(self, conexion: sqlite3.Connection, documento: str) -> sqlite3.Row:
        fila = conexion.execute(
            "SELECT * FROM documento_auditoria WHERE documento = ?", (documento,)
        ).fetchone()
        if fila is None:
            raise AuditoriaInvalidaError(
                f"El comprobante {documento} no esta en ningun lote aceptado."
            )
        return fila

    # --- Decision del auditor de la IAFAS ----------------------------------

    def auditar(  # noqa: PLR0913 - formulario del auditor
        self,
        documento: str,
        resultado: str,
        canal: str = "PORTAL",
        motivo_codigo: str | None = None,
        monto_glosado: Decimal | None = None,
        detalle: str | None = None,
        decision_respuesta: str = "ACEPTAR",
    ) -> list[Comunicacion]:
        if resultado not in RESULTADOS_AUDITORIA or canal not in CANALES:
            raise AuditoriaInvalidaError("Resultado o canal fuera de los definidos.")
        if decision_respuesta not in DECISIONES_RESPUESTA:
            raise AuditoriaInvalidaError("Decision sobre la respuesta fuera de las definidas.")
        with self._conexion() as conexion:
            fila = self._documento(conexion, documento)
            if fila["estado"] != "PENDIENTE":
                raise AuditoriaInvalidaError(f"El comprobante {documento} ya fue auditado.")
            facturado = Decimal(fila["monto_facturado"])
            if resultado == "CONFORME":
                conexion.execute(
                    "UPDATE documento_auditoria SET estado = 'PAGADO', canal = ? "
                    "WHERE documento = ?",
                    (canal, documento),
                )
                return self._emitir(
                    conexion,
                    fila,
                    canal,
                    [
                        ("AUDITORIA_CONFORME", {}),
                        ("LIQUIDACION", {"monto_liquidado": str(facturado), "es_parcial": False}),
                        ("PAGO", {"monto_pagado": str(facturado)}),
                    ],
                )
            if not motivo_codigo:
                raise AuditoriaInvalidaError("Una glosa necesita el codigo de motivo.")
            es_parcial = resultado == "GLOSA_PARCIAL"
            glosado = monto_glosado if es_parcial and monto_glosado is not None else facturado
            if es_parcial and not Decimal("0") < glosado < facturado:
                raise AuditoriaInvalidaError(
                    "El monto glosado parcial debe ser menor que el facturado."
                )
            conexion.execute(
                """UPDATE documento_auditoria SET estado = ?, canal = ?, decision_respuesta = ?,
                       monto_glosado = ?, motivo_codigo = ? WHERE documento = ?""",
                (
                    "GLOSADO_PARCIAL" if es_parcial else "GLOSADO",
                    canal,
                    decision_respuesta,
                    str(glosado),
                    motivo_codigo,
                    documento,
                ),
            )
            return self._emitir(
                conexion,
                fila,
                canal,
                [("OBSERVACION", _datos_observacion(motivo_codigo, es_parcial, glosado, detalle))],
            )

    # --- Respuesta de la IPRESS (portal) ------------------------------------

    def responder(
        self,
        codigo: str,
        codigo_ipress: str,
        texto: str,
        sustento: str | None,
        refacturado: tuple[str, Decimal] | None = None,
    ) -> list[Comunicacion]:
        """`refacturado`: el comprobante vigente y su monto, si la IPRESS
        refacturo al responder; la IAFAS liquida sobre ese monto."""
        if not texto.strip():
            raise AuditoriaInvalidaError("La respuesta no puede estar vacia.")
        with self._conexion() as conexion:
            comunicacion = conexion.execute(
                "SELECT * FROM comunicacion WHERE codigo = ?", (codigo,)
            ).fetchone()
            if comunicacion is None or comunicacion["codigo_ipress"] != codigo_ipress:
                raise AuditoriaInvalidaError(
                    f"No existe la comunicacion {codigo} para esta IPRESS."
                )
            if comunicacion["tipo"] != "OBSERVACION":
                raise AuditoriaInvalidaError("Solo se responde una observacion.")
            if comunicacion["respondida_en"] is not None:
                raise AuditoriaInvalidaError(f"La observacion {codigo} ya fue respondida.")
            conexion.execute(
                """UPDATE comunicacion SET respuesta_texto = ?, respuesta_sustento = ?,
                       respondida_en = ? WHERE codigo = ?""",
                (texto, sustento, datetime.now().isoformat(timespec="seconds"), codigo),
            )
            if refacturado is not None:
                conexion.execute(
                    """UPDATE documento_auditoria SET documento_vigente = ?, monto_facturado = ?
                       WHERE documento = ?""",
                    (refacturado[0], str(refacturado[1]), comunicacion["documento"]),
                )
            return self._evaluar_respuesta(conexion, comunicacion)

    def adjuntar(self, codigo: str, nombre: str, contenido: bytes) -> None:
        """El documento que la IPRESS adjunto a su respuesta."""
        with self._conexion() as conexion:
            conexion.execute(
                """UPDATE comunicacion SET respuesta_adjunto_nombre = ?, respuesta_adjunto = ?
                   WHERE codigo = ?""",
                (nombre, contenido, codigo),
            )

    def adjunto(self, codigo: str) -> tuple[str, bytes] | None:
        with self._conexion() as conexion:
            fila = conexion.execute(
                """SELECT respuesta_adjunto_nombre, respuesta_adjunto FROM comunicacion
                   WHERE codigo = ? AND respuesta_adjunto IS NOT NULL""",
                (codigo,),
            ).fetchone()
        return None if fila is None else (fila[0], bytes(fila[1]))

    def _evaluar_respuesta(
        self, conexion: sqlite3.Connection, comunicacion: sqlite3.Row
    ) -> list[Comunicacion]:
        fila = self._documento(conexion, comunicacion["documento"])
        datos = json.loads(comunicacion["datos"])
        facturado = Decimal(fila["monto_facturado"])
        mantener = (
            fila["decision_respuesta"] == "MANTENER"
            and not datos["es_parcial"]
            and fila["observaciones_mantenidas"] == 0
        )
        if mantener:
            conexion.execute(
                """UPDATE documento_auditoria SET observaciones_mantenidas = 1
                   WHERE documento = ?""",
                (fila["documento"],),
            )
            nueva = _datos_observacion(
                datos["motivo_codigo"], False, facturado, "La IAFAS mantiene la observacion."
            )
            return self._emitir(conexion, fila, fila["canal"], [("OBSERVACION", nueva)])
        liquidado = (
            facturado - Decimal(datos["monto_glosado"]) if datos["es_parcial"] else facturado
        )
        conexion.execute(
            "UPDATE documento_auditoria SET estado = 'PAGADO' WHERE documento = ?",
            (fila["documento"],),
        )
        return self._emitir(
            conexion,
            fila,
            fila["canal"],
            [
                (
                    "LIQUIDACION",
                    {"monto_liquidado": str(liquidado), "es_parcial": datos["es_parcial"]},
                ),
                ("PAGO", {"monto_pagado": str(liquidado)}),
            ],
        )

    # --- Comunicaciones -----------------------------------------------------

    def _emitir(
        self,
        conexion: sqlite3.Connection,
        fila: sqlite3.Row,
        canal: str,
        piezas: list[tuple[str, dict[str, Any]]],
    ) -> list[Comunicacion]:
        emitidas = []
        for tipo, datos in piezas:
            ahora = datetime.now().isoformat(timespec="seconds")
            cursor = conexion.execute(
                """INSERT INTO comunicacion
                       (codigo_iafas, codigo_ipress, documento, tipo, datos, canal, emitida_en)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    fila["codigo_iafas"],
                    fila["codigo_ipress"],
                    fila["documento"],
                    tipo,
                    json.dumps(datos, ensure_ascii=False),
                    canal,
                    ahora,
                ),
            )
            codigo = f"COM-{cursor.lastrowid:08d}"
            conexion.execute(
                "UPDATE comunicacion SET codigo = ? WHERE id = ?", (codigo, cursor.lastrowid)
            )
            emitidas.append(
                Comunicacion(
                    codigo=codigo,
                    codigo_iafas=fila["codigo_iafas"],
                    codigo_ipress=fila["codigo_ipress"],
                    documento=fila["documento"],
                    tipo=tipo,
                    datos=datos,
                    canal=canal,
                    emitida_en=ahora,
                    respuesta_texto=None,
                    respondida_en=None,
                )
            )
        if self._enviar_correo is not None:
            for comunicacion in emitidas:
                if comunicacion.canal == "CORREO":
                    self._enviar_correo(comunicacion)
        return emitidas

    def comunicaciones(self, codigo_ipress: str | None = None) -> list[Comunicacion]:
        consulta = "SELECT * FROM comunicacion"
        parametros: tuple[str, ...] = ()
        if codigo_ipress is not None:
            consulta += " WHERE codigo_ipress = ?"
            parametros = (codigo_ipress,)
        with self._conexion() as conexion:
            filas = conexion.execute(consulta + " ORDER BY id", parametros).fetchall()
        return [_a_comunicacion(fila) for fila in filas]

    def comunicacion(self, codigo: str) -> Comunicacion | None:
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT * FROM comunicacion WHERE codigo = ?", (codigo,)
            ).fetchone()
        return _a_comunicacion(fila) if fila is not None else None


def _datos_observacion(
    motivo_codigo: str, es_parcial: bool, monto_glosado: Decimal, detalle: str | None
) -> dict[str, Any]:
    return {
        "motivo_codigo": motivo_codigo,
        "es_parcial": es_parcial,
        "monto_glosado": str(monto_glosado),
        "detalle": detalle or "",
    }


def _a_documento(fila: sqlite3.Row) -> DocumentoAuditado:
    return DocumentoAuditado(
        documento=fila["documento"],
        nombre_archivo=fila["nombre_archivo"],
        codigo_iafas=fila["codigo_iafas"],
        codigo_ipress=fila["codigo_ipress"],
        monto_facturado=Decimal(fila["monto_facturado"]),
        estado=fila["estado"],
        canal=fila["canal"],
        decision_respuesta=fila["decision_respuesta"],
        documento_vigente=fila["documento_vigente"],
    )


def _a_comunicacion(fila: sqlite3.Row) -> Comunicacion:
    return Comunicacion(
        codigo=fila["codigo"],
        codigo_iafas=fila["codigo_iafas"],
        codigo_ipress=fila["codigo_ipress"],
        documento=fila["documento"],
        tipo=fila["tipo"],
        datos=json.loads(fila["datos"]),
        canal=fila["canal"],
        emitida_en=fila["emitida_en"],
        respuesta_texto=fila["respuesta_texto"],
        respondida_en=fila["respondida_en"],
        respuesta_adjunto=fila["respuesta_adjunto_nombre"],
    )
