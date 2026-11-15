"""Pruebas de RepositorioLiquidacionesSql contra SQLite en memoria
(Seccion 5.2.4.1, Fase 28)."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.liquidacion.valores import DatosNuevaLiquidacion
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.repositorio_liquidaciones_sql import (
    RepositorioLiquidacionesSql,
)

_AHORA = datetime(2026, 11, 8, 10, 0, 0)


async def _sembrar_cuenta(sesion: AsyncSession) -> int:
    iafas = IafasModelo(
        codigo="00012",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
        dias_plazo_respuesta_observacion=7,
        dias_plazo_comunicacion_auditoria=30,
        dias_plazo_pago_liquidacion=30,
    )
    ipress = IpressModelo(
        ruc="20123456789", codigo_ipress="12345678", razon_social="Clinica de prueba"
    )
    sesion.add_all([iafas, ipress])
    await sesion.flush()
    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento="12345678",
        nombres="Ana",
        apellidos="Perez",
        iafas_id=iafas.id,
        ficticio=True,
    )
    sesion.add(asegurado)
    await sesion.flush()
    cuenta = CuentaMedicaModelo(
        identificacion_interna="CTA0000001",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=date(2026, 9, 10),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica="00000001",
        estado="LIQUIDADA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta.id


async def prueba_crear_y_obtener_por_cuenta(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioLiquidacionesSql(sesion)

        liquidacion_id = await repositorio.crear(
            DatosNuevaLiquidacion(
                cuenta_medica_id=cuenta_id,
                es_parcial=False,
                monto_liquidado=Decimal("1500.00"),
                registrado_en=_AHORA,
            )
        )
        await sesion.commit()

        liquidacion = await repositorio.obtener_por_cuenta(cuenta_id)
        assert liquidacion is not None
        assert liquidacion.id == liquidacion_id
        assert liquidacion.monto_liquidado == Decimal("1500.00")
        assert liquidacion.monto_pagado is None
        assert liquidacion.diferencia is None

        assert await repositorio.obtener_por_cuenta(999) is None


async def prueba_conciliar_completa_el_monto_pagado_y_la_diferencia(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioLiquidacionesSql(sesion)
        liquidacion_id = await repositorio.crear(
            DatosNuevaLiquidacion(
                cuenta_medica_id=cuenta_id,
                es_parcial=False,
                monto_liquidado=Decimal("1500.00"),
                registrado_en=_AHORA,
            )
        )
        await sesion.commit()

        conciliado_en = datetime(2026, 11, 9, 8, 0, 0)
        await repositorio.conciliar(
            liquidacion_id, Decimal("1450.00"), Decimal("-50.00"), conciliado_en
        )
        await sesion.commit()

        liquidacion = await repositorio.obtener_por_cuenta(cuenta_id)
        assert liquidacion is not None
        assert liquidacion.monto_pagado == Decimal("1450.00")
        assert liquidacion.diferencia == Decimal("-50.00")
        assert liquidacion.conciliado_en == conciliado_en
