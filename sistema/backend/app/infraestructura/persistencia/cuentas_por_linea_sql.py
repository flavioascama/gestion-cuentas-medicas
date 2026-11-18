"""A que cuenta pertenece cada linea de las tablas de un lote (2026-11-18).

El validador observa por tabla y numero de linea; quien corrige necesita
saber de que cuenta se trata. El lote se arma recorriendo sus comprobantes
por id de cuenta (`RepositorioLoteFacturacionSql.obtener_documentos_
facturados`): T1 y T2 llevan una linea por cuenta, T3 una por procedimiento
y T4 una por producto de farmacia, en ese mismo orden. Con eso se
reconstruye la cuenta de cada linea sin leer los archivos del lote.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    LoteDocumentoModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.tedef.nombrado import PREFIJO_ARCHIVO_POR_TABLA

# (id de la cuenta, identificacion interna)
Cuenta = tuple[int, str]
CuentasPorLinea = dict[str, list[Cuenta]]

_TABLA_POR_PREFIJO = {
    prefijo.upper(): tabla for tabla, prefijo in PREFIJO_ARCHIVO_POR_TABLA.items()
}


async def _contar(
    sesion: AsyncSession, columna_cuenta: InstrumentedAttribute[int], cuenta_ids: list[int]
) -> dict[int, int]:
    if not cuenta_ids:
        return {}
    filas = await sesion.execute(
        sa.select(columna_cuenta, sa.func.count())
        .where(columna_cuenta.in_(cuenta_ids))
        .group_by(columna_cuenta)
    )
    return {cuenta_id: cantidad for cuenta_id, cantidad in filas.all()}


async def cuentas_por_linea(sesion: AsyncSession, lote_id: int) -> CuentasPorLinea:
    filas = await sesion.execute(
        sa.select(CuentaMedicaModelo.id, CuentaMedicaModelo.identificacion_interna)
        .select_from(LoteDocumentoModelo)
        .join(
            DocumentoFacturadorModelo,
            DocumentoFacturadorModelo.id == LoteDocumentoModelo.documento_id,
        )
        .join(CuentaMedicaModelo, CuentaMedicaModelo.id == DocumentoFacturadorModelo.cuenta_id)
        .where(LoteDocumentoModelo.lote_id == lote_id)
        .order_by(CuentaMedicaModelo.id)
    )
    cuentas: list[Cuenta] = [(cuenta_id, codigo) for cuenta_id, codigo in filas.all()]
    ids = [cuenta_id for cuenta_id, _ in cuentas]
    procedimientos = await _contar(sesion, ProcedimientoFacturadoModelo.cuenta_id, ids)
    productos = await _contar(sesion, ProductoFacturadoModelo.cuenta_medica_id, ids)
    return {
        "T1": cuentas,
        "T2": cuentas,
        "T3": [c for c in cuentas for _ in range(procedimientos.get(c[0], 0))],
        "T4": [c for c in cuentas for _ in range(productos.get(c[0], 0))],
    }


def cuenta_de_linea(
    lineas: CuentasPorLinea, tabla: str | None, numero_linea: int | None
) -> Cuenta | None:
    """None si la observacion es de todo el lote o la linea no existe."""
    if tabla is None or numero_linea is None:
        return None
    clave = tabla.strip().upper()
    de_la_tabla = lineas.get(_TABLA_POR_PREFIJO.get(clave, clave), [])
    if not 1 <= numero_linea <= len(de_la_tabla):
        return None
    return de_la_tabla[numero_linea - 1]
