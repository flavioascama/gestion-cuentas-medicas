"""Pruebas de las dos vistas agregadas del panel gerencial (rediseno
pedido por el usuario, 2026-11-12): la evolucion de lotes por periodo y
el comparativo por IAFAS de RepositorioTrazabilidadSql.calcular_indicadores.

Separadas de prueba_repositorio_trazabilidad.py para no pasar el limite
de 400 lineas por archivo (GUIA_ESTILO_CODIGO.md, Seccion 3)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.trazabilidad.valores import FiltroIndicadores
from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
    LoteFacturacionModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.modelos_liquidacion import LiquidacionModelo
from app.infraestructura.persistencia.repositorio_trazabilidad_sql import RepositorioTrazabilidadSql

_AHORA = datetime(2026, 11, 8, 10, 0, 0)


async def _crear_iafas(sesion: AsyncSession, codigo: str) -> IafasModelo:
    iafas = IafasModelo(
        codigo=codigo,
        razon_social=f"IAFAS {codigo}",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
        dias_plazo_respuesta_observacion=7,
        dias_plazo_comunicacion_auditoria=30,
        dias_plazo_pago_liquidacion=30,
    )
    sesion.add(iafas)
    await sesion.flush()
    return iafas


async def _crear_cuenta(sesion: AsyncSession, iafas: IafasModelo, fecha: date) -> int:
    sufijo = uuid.uuid4().hex[:8]
    ipress = IpressModelo(ruc=f"201{sufijo}", codigo_ipress=sufijo, razon_social="Clinica")
    sesion.add(ipress)
    await sesion.flush()
    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento=sufijo,
        nombres="Ana",
        apellidos="Perez",
        iafas_id=iafas.id,
        ficticio=True,
    )
    sesion.add(asegurado)
    await sesion.flush()
    cuenta = CuentaMedicaModelo(
        identificacion_interna=f"CTA-{sufijo}",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=fecha,
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica="00000001",
        estado="REGISTRADA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta.id


async def _agregar_montos(sesion: AsyncSession, cuenta_id: int) -> None:
    """2 x 50.00 en procedimientos + 15.50 en farmacia = 115.50."""
    version = CpmsVersionModelo(etiqueta=f"v-{uuid.uuid4().hex[:6]}", archivos_origen=[], conteo=0)
    sesion.add(version)
    await sesion.flush()
    sesion.add(
        ProcedimientoFacturadoModelo(
            cuenta_id=cuenta_id,
            descripcion_registrada="Consulta",
            codigo_asignado="99201",
            cpms_version_id=version.id,
            origen_codigo="coincidencia_exacta",
            cantidad=2,
            monto_unitario=Decimal("50.00"),
            fecha=date(2026, 9, 15),
        )
    )
    sesion.add(
        ProductoFacturadoModelo(
            cuenta_medica_id=cuenta_id,
            correlativo=1,
            tipo_producto="M",
            catalogo="1",
            codigo_producto="0380652555906",
            fecha_dispensacion=date(2026, 9, 15),
            cantidad_venta=Decimal("1.00"),
            tipo_unidad_dispensacion="1",
            monto_unitario_sin_impuesto=Decimal("15.50"),
            monto_presentado=Decimal("15.50"),
        )
    )


def _agregar_lote(sesion: AsyncSession, iafas: IafasModelo, periodo: str, estado: str) -> None:
    sesion.add(
        LoteFacturacionModelo(
            numero=uuid.uuid4().hex[:7],
            iafas_id=iafas.id,
            periodo=periodo,
            generado_en=_AHORA,
            estado=estado,
        )
    )


async def prueba_lotes_por_periodo_agrupa_por_periodo_y_estado_y_respeta_la_iafas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_a = await _crear_iafas(sesion, "00001")
        iafas_b = await _crear_iafas(sesion, "00002")
        _agregar_lote(sesion, iafas_a, "202609", "ACEPTADO")
        _agregar_lote(sesion, iafas_a, "202609", "ACEPTADO")
        _agregar_lote(sesion, iafas_a, "202610", "OBSERVADO_VALIDADOR")
        _agregar_lote(sesion, iafas_b, "202609", "RECHAZADO")
        await sesion.commit()

        repositorio = RepositorioTrazabilidadSql(sesion)
        todas = await repositorio.calcular_indicadores(FiltroIndicadores())
        solo_a = await repositorio.calcular_indicadores(FiltroIndicadores(iafas_codigo="00001"))
        # El filtro de periodo no recorta la serie de evolucion.
        con_periodo = await repositorio.calcular_indicadores(
            FiltroIndicadores(iafas_codigo="00001", periodo="202609")
        )

    assert [(f.periodo, f.estado, f.cantidad) for f in todas.lotes_por_periodo] == [
        ("202609", "ACEPTADO", 2),
        ("202609", "RECHAZADO", 1),
        ("202610", "OBSERVADO_VALIDADOR", 1),
    ]
    assert [(f.periodo, f.estado, f.cantidad) for f in solo_a.lotes_por_periodo] == [
        ("202609", "ACEPTADO", 2),
        ("202610", "OBSERVADO_VALIDADOR", 1),
    ]
    assert con_periodo.lotes_por_periodo == solo_a.lotes_por_periodo


async def prueba_por_iafas_desglosa_cada_indicador_y_respeta_el_periodo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_a = await _crear_iafas(sesion, "00001")
        iafas_b = await _crear_iafas(sesion, "00002")
        cuenta_a = await _crear_cuenta(sesion, iafas_a, date(2026, 9, 10))
        await _crear_cuenta(sesion, iafas_a, date(2026, 10, 10))
        await _agregar_montos(sesion, cuenta_a)
        sesion.add(
            LiquidacionModelo(
                cuenta_medica_id=cuenta_a,
                es_parcial=False,
                monto_liquidado=Decimal("115.50"),
                registrado_en=_AHORA,
                monto_pagado=Decimal("100.00"),
                diferencia=Decimal("-15.50"),
                conciliado_en=_AHORA,
            )
        )
        _agregar_lote(sesion, iafas_a, "202609", "OBSERVADO_VALIDADOR")
        _agregar_lote(sesion, iafas_a, "202609", "ACEPTADO")
        _agregar_lote(sesion, iafas_b, "202609", "ACEPTADO")
        await sesion.commit()

        repositorio = RepositorioTrazabilidadSql(sesion)
        setiembre = await repositorio.calcular_indicadores(FiltroIndicadores(periodo="202609"))
        # El filtro de IAFAS no oculta las demas aseguradoras del comparativo.
        con_iafas = await repositorio.calcular_indicadores(
            FiltroIndicadores(iafas_codigo="00001", periodo="202609")
        )

    a, b = setiembre.por_iafas
    assert (a.iafas_codigo, a.iafas_razon_social) == ("00001", "IAFAS 00001")
    assert a.cuentas == 1
    assert a.monto_registrado == Decimal("115.50")
    assert a.cartera_por_cobrar == Decimal("15.50")
    assert a.lotes == 2
    assert a.pct_lotes_observados == 0.5
    assert (b.iafas_codigo, b.cuentas, b.lotes, b.pct_lotes_observados) == ("00002", 0, 1, 0.0)
    assert b.monto_registrado == Decimal("0.00")
    assert [f.iafas_codigo for f in con_iafas.por_iafas] == ["00001", "00002"]
