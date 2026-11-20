"""Regulariza una sola vez las cuentas completas que siguen REGISTRADAS
(2026-11-19).

Hasta esta fecha la cuenta pasaba a FACTURADA solo cuando alguien
consultaba su completitud; desde ahora pasa al registrarse el comprobante
(FacturarCuentaCompleta). Las cuentas que ya tenian todas sus piezas y que
nadie volvio a consultar se quedaron en REGISTRADA. Esta herramienta les
aplica la misma regla y la misma transicion (T-02, evento CUENTA_FACTURADA),
a nombre del sistema. Es idempotente: una cuenta ya facturada o a la que le
falta una pieza no se toca, asi que correrla otra vez no mueve nada.

Uso (desde sistema/backend/):
    uv run python -m herramientas.facturar_cuentas_completas
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.facturacion_cuenta import ESTADO_REGISTRADA, FacturarCuentaCompleta
from app.dominio.puertos_comunes import RegistroEventos
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
)
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_ingesta_cuentas_sql import (
    RepositorioCompletitudCuentaSql,
)

ACTOR_SISTEMA = "sistema"


@dataclass(frozen=True, slots=True)
class ResumenRegularizacion:
    revisadas: int
    facturadas: list[int]


async def regularizar(
    sesion: AsyncSession, registro_eventos: RegistroEventos
) -> ResumenRegularizacion:
    # Solo una cuenta REGISTRADA con comprobante puede estar completa: el
    # comprobante exige las demas piezas. La regla completa la evalua
    # FacturarCuentaCompleta, la misma que usa la emision del comprobante.
    candidatas = (
        await sesion.scalars(
            sa.select(CuentaMedicaModelo.id)
            .join(
                DocumentoFacturadorModelo,
                DocumentoFacturadorModelo.cuenta_id == CuentaMedicaModelo.id,
            )
            .where(CuentaMedicaModelo.estado == ESTADO_REGISTRADA)
            .order_by(CuentaMedicaModelo.id)
        )
    ).all()
    facturacion = FacturarCuentaCompleta(RepositorioCompletitudCuentaSql(sesion), registro_eventos)
    facturadas = [
        cuenta_id
        for cuenta_id in candidatas
        if await facturacion.ejecutar(cuenta_id, ACTOR_SISTEMA)
    ]
    return ResumenRegularizacion(revisadas=len(candidatas), facturadas=facturadas)


async def main() -> None:
    async with FabricaSesiones() as sesion:
        resumen = await regularizar(sesion, RegistroEventosSql(sesion))
    for cuenta_id in resumen.facturadas:
        print(f"cuenta {cuenta_id}: REGISTRADA -> FACTURADA")
    print(
        f"{resumen.revisadas} cuentas REGISTRADAS con comprobante revisadas; "
        f"{len(resumen.facturadas)} pasaron a FACTURADA"
    )


if __name__ == "__main__":
    asyncio.run(main())
