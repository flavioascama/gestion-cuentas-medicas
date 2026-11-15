"""Regla de continuidad de estados (Tabla 69), 2026-11-13.

Desde esta fecha `RegistroEventosSql.registrar` rechaza un evento cuyo
estado previo no es el ultimo estado registrado del agregado. Antes del
12/11 la remision de un lote no dejaba evento por cuenta (brecha 2 de la
verificacion de cumplimiento), y algunas pruebas de integracion fijaban el
estado por SQL: esas cuentas tienen hoy un estado que su historial no
registra, y su siguiente transicion real seria rechazada.

Esta herramienta no modifica ni borra ningun evento (el almacen es de solo
insercion): agrega a cada cuenta afectada un evento
CONTINUIDAD_RESTABLECIDA, del ultimo estado registrado al estado actual,
fechado en el momento en que se corre y con el motivo en sus datos.

Uso (desde sistema/backend/):
    uv run python -m herramientas.restablecer_continuidad_estados
"""

from __future__ import annotations

import asyncio

import sqlalchemy as sa

from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo, EventoModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql

_MOTIVO = (
    "El estado de la cuenta se fijo sin su evento antes de la regla de continuidad "
    "(Tabla 69); se registra ahora para que el historial lo refleje."
)


async def main() -> None:
    orden = (
        sa.func.row_number()
        .over(partition_by=EventoModelo.agregado_id, order_by=EventoModelo.version.desc())
        .label("orden")
    )
    ultimos = (
        sa.select(EventoModelo.agregado_id, EventoModelo.estado_nuevo, orden)
        .where(EventoModelo.tipo_agregado == "CUENTA", EventoModelo.estado_nuevo.is_not(None))
        .subquery()
    )
    async with FabricaSesiones() as sesion:
        filas = (
            await sesion.execute(
                sa.select(CuentaMedicaModelo.id, ultimos.c.estado_nuevo, CuentaMedicaModelo.estado)
                .join(ultimos, ultimos.c.agregado_id == CuentaMedicaModelo.id)
                .where(ultimos.c.orden == 1, ultimos.c.estado_nuevo != CuentaMedicaModelo.estado)
                .order_by(CuentaMedicaModelo.id)
            )
        ).all()
        registro = RegistroEventosSql(sesion)
        for cuenta_id, ultimo, actual in filas:
            await registro.registrar(
                Evento(
                    cuenta_medica_id=cuenta_id,
                    tipo_evento="CONTINUIDAD_RESTABLECIDA",
                    actor="sistema",
                    estado_previo=ultimo,
                    estado_nuevo=actual,
                    datos={"motivo": _MOTIVO},
                )
            )
            print(f"cuenta {cuenta_id}: {ultimo} -> {actual}")
    print(f"{len(filas)} cuentas con la continuidad restablecida")


if __name__ == "__main__":
    asyncio.run(main())
