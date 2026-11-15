"""Pruebas de RepositorioTrazabilidadSql contra SQLite en memoria
(Seccion 6.2, Fase 29): verifica la reconstruccion del historial, la
deteccion de rupturas de la cadena y el calculo de los indicadores --
`RevisarVencimientos`-style, los casos de uso ya se prueban aparte con
un doble (pruebas/prueba_casos_uso_trazabilidad.py)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.puertos_comunes import Evento
from app.dominio.trazabilidad.valores import FiltroIndicadores
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    EventoModelo,
    IafasModelo,
    IpressModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.modelos_liquidacion import LiquidacionModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_trazabilidad_sql import RepositorioTrazabilidadSql

_AHORA = datetime(2026, 11, 8, 10, 0, 0)


async def _sembrar_cuenta(
    sesion: AsyncSession, iafas_codigo: str = "00012", fecha_prestacion: date = date(2026, 9, 10)
) -> int:
    sufijo = uuid.uuid4().hex[:8]
    iafas = (
        await sesion.execute(sa.select(IafasModelo).where(IafasModelo.codigo == iafas_codigo))
    ).scalar_one_or_none()
    if iafas is None:
        iafas = IafasModelo(
            codigo=iafas_codigo,
            razon_social="IAFAS de prueba",
            periodicidad_remision_dias=7,
            ventana_monitoreo_horas=48,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        sesion.add(iafas)
        await sesion.flush()
    ipress = IpressModelo(
        ruc=f"201{sufijo[:8]}", codigo_ipress=sufijo, razon_social="Clinica de prueba"
    )
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
        identificacion_interna=f"CTA{asegurado.id:07d}",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=fecha_prestacion,
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica="00000001",
        estado="REGISTRADA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta.id


async def prueba_historial_de_cuenta_reconstruye_eventos_en_orden(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="REGISTRO",
                actor="ana.analista",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="FACTURACION",
                actor="sistema",
                estado_previo="REGISTRADA",
                estado_nuevo="FACTURADA",
            )
        )

        repositorio = RepositorioTrazabilidadSql(sesion)
        assert await repositorio.existe_cuenta(cuenta_id) is True
        assert await repositorio.existe_cuenta(999) is False

        historial = await repositorio.historial_de_cuenta(cuenta_id)
        assert [e.tipo_evento for e in historial.eventos] == ["REGISTRO", "FACTURACION"]
        assert historial.cadena_integra is True
        assert historial.rupturas == []


async def prueba_historial_detecta_una_ruptura_de_la_cadena(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        await RegistroEventosSql(sesion).registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="REGISTRO",
                actor="ana.analista",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        await sesion.execute(
            sa.update(EventoModelo)
            .where(EventoModelo.agregado_id == cuenta_id, EventoModelo.tipo_agregado == "CUENTA")
            .values(hash_evento="valor-alterado-manualmente")
        )
        await sesion.commit()

        repositorio = RepositorioTrazabilidadSql(sesion)
        historial = await repositorio.historial_de_cuenta(cuenta_id)

        assert historial.cadena_integra is False
        assert len(historial.rupturas) == 1


async def prueba_historial_de_lote_reconstruye_sus_eventos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """RT-13: el historial de un lote, no solo el de la cuenta."""
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None
        lote = LoteFacturacionModelo(
            numero=f"L{uuid.uuid4().hex[:8]}",
            iafas_id=cuenta.iafas_id,
            periodo="202609",
            generado_en=_AHORA,
            estado="GENERADO",
        )
        sesion.add(lote)
        await sesion.flush()
        registro = RegistroEventosSql(sesion)
        for tipo, previo, nuevo in (
            ("GENERACION_LOTE", None, "GENERADO"),
            ("VALIDACION_LOTE", "GENERADO", "VALIDADO"),
        ):
            await registro.registrar(
                Evento(
                    cuenta_medica_id=None,
                    lote_id=lote.id,
                    tipo_evento=tipo,
                    actor="ana.analista",
                    estado_previo=previo,
                    estado_nuevo=nuevo,
                )
            )

        repositorio = RepositorioTrazabilidadSql(sesion)
        assert await repositorio.existe_lote(lote.id) is True
        assert await repositorio.existe_lote(999999) is False
        historial = await repositorio.historial_de_lote(lote.id)
        assert historial.lote_id == lote.id
        assert [e.tipo_evento for e in historial.eventos] == ["GENERACION_LOTE", "VALIDACION_LOTE"]
        assert historial.cadena_integra is True


async def prueba_calcular_indicadores_filtra_por_iafas_y_periodo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_setiembre = await _sembrar_cuenta(
            sesion, iafas_codigo="00012", fecha_prestacion=date(2026, 9, 15)
        )
        cuenta_octubre = await _sembrar_cuenta(
            sesion, iafas_codigo="00012", fecha_prestacion=date(2026, 10, 15)
        )
        await sesion.execute(
            sa.update(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_setiembre)
            .values(estado="GLOSADA")
        )
        await sesion.commit()
        await RegistroEventosSql(sesion).registrar(
            Evento(
                cuenta_medica_id=cuenta_setiembre,
                tipo_evento="GLOSA",
                actor="ana.analista",
                estado_previo="EN_AUDITORIA",
                estado_nuevo="GLOSADA",
            )
        )

        repositorio = RepositorioTrazabilidadSql(sesion)
        indicadores_setiembre = await repositorio.calcular_indicadores(
            FiltroIndicadores(iafas_codigo="00012", periodo="202609")
        )
        assert indicadores_setiembre.cuentas_evaluadas == 1
        assert indicadores_setiembre.tasa_glosas == 1.0
        assert indicadores_setiembre.distribucion_por_estado[0].estado == "GLOSADA"

        indicadores_octubre = await repositorio.calcular_indicadores(
            FiltroIndicadores(iafas_codigo="00012", periodo="202610")
        )
        assert indicadores_octubre.cuentas_evaluadas == 1
        assert indicadores_octubre.tasa_glosas == 0.0
        assert indicadores_octubre.distribucion_por_estado[0].estado == "REGISTRADA"

        indicadores_sin_filtro_de_periodo = await repositorio.calcular_indicadores(
            FiltroIndicadores(iafas_codigo="00012")
        )
        assert indicadores_sin_filtro_de_periodo.cuentas_evaluadas == 2
        _ = cuenta_octubre


async def prueba_calcular_indicadores_sin_filtro_cuenta_todos_los_lotes(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas = IafasModelo(
            codigo="00099",
            razon_social="IAFAS de prueba",
            periodicidad_remision_dias=7,
            ventana_monitoreo_horas=48,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        sesion.add(iafas)
        await sesion.flush()
        for numero, estado in (("0000001", "OBSERVADO_VALIDADOR"), ("0000002", "VALIDADO")):
            sesion.add(
                LoteFacturacionModelo(
                    numero=numero,
                    iafas_id=iafas.id,
                    periodo="202609",
                    generado_en=_AHORA,
                    estado=estado,
                )
            )
        await sesion.commit()

        repositorio = RepositorioTrazabilidadSql(sesion)
        indicadores = await repositorio.calcular_indicadores(FiltroIndicadores())

        # Sin filtro de IAFAS ni de periodo, `_contar_lotes` arma un
        # `SELECT count(*)` sin FROM si no hay ninguna columna de
        # LoteFacturacionModelo en la consulta (regresion: antes
        # devolvia 1 para cualquier cantidad real de lotes, porque
        # Postgres y SQLite cuentan una fila "vacia" cuando no hay
        # FROM).
        assert indicadores.lotes_evaluados == 2
        assert indicadores.pct_lotes_observados == 0.5
        assert indicadores.pct_lotes_rechazados == 0.0


async def prueba_cartera_por_cobrar_suma_solo_diferencias_negativas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        sesion.add(
            LiquidacionModelo(
                cuenta_medica_id=cuenta_id,
                es_parcial=False,
                monto_liquidado=Decimal("1500.00"),
                registrado_en=_AHORA,
                monto_pagado=Decimal("1450.00"),
                diferencia=Decimal("-50.00"),
                conciliado_en=_AHORA,
            )
        )
        await sesion.commit()

        repositorio = RepositorioTrazabilidadSql(sesion)
        indicadores = await repositorio.calcular_indicadores(FiltroIndicadores())

        assert indicadores.cartera_por_cobrar == Decimal("50.00")


async def prueba_documentos_de_cuenta_incluye_la_acreditacion(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        sesion.add(
            AcreditacionModelo(
                cuenta_id=cuenta_id,
                condicion_cobertura="VIGENTE",
                codigo_autorizacion="AUT-0001",
                tipo_documento_autorizacion="01",
                codigo_asegurado="ASE-0001",
                tipo_afiliacion="1",
                instante=_AHORA,
                componente_ejecutor="robot_acreditacion",
            )
        )
        await sesion.commit()

        repositorio = RepositorioTrazabilidadSql(sesion)
        documentos = await repositorio.documentos_de_cuenta(cuenta_id)

        assert len(documentos) == 1
        assert documentos[0].tipo == "ACREDITACION"
        assert documentos[0].referencia == "AUT-0001"


async def prueba_documentos_de_cuenta_incluye_el_comprobante_de_pago(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None
        sesion.add(
            DocumentoFacturadorModelo(
                cuenta_id=cuenta_id,
                ipress_id=cuenta.ipress_id,
                tipo_documento_pago="01",
                serie="F001",
                numero="00012345",
                fecha_emision=date(2026, 9, 12),
            )
        )
        await sesion.commit()

        repositorio = RepositorioTrazabilidadSql(sesion)
        documentos = await repositorio.documentos_de_cuenta(cuenta_id)

        assert len(documentos) == 1
        assert documentos[0].tipo == "COMPROBANTE_PAGO"
        assert documentos[0].referencia == "01-F001-00012345"


async def prueba_tiempo_por_etapa_calcula_la_duracion_entre_eventos_consecutivos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="REGISTRO",
                actor="ana.analista",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="FACTURACION",
                actor="sistema",
                estado_previo="REGISTRADA",
                estado_nuevo="FACTURADA",
            )
        )

        repositorio = RepositorioTrazabilidadSql(sesion)
        indicadores = await repositorio.calcular_indicadores(FiltroIndicadores())

        (etapa_facturada,) = (t for t in indicadores.tiempo_por_etapa if t.etapa == "FACTURADA")
        assert etapa_facturada.transiciones == 1
        assert etapa_facturada.promedio_horas >= 0
        # REGISTRADA es el primer evento del agregado (estado_previo
        # vacio): no tiene un evento anterior del que medir una
        # duracion, por eso no aparece como su propia etapa.
        assert all(t.etapa != "REGISTRADA" for t in indicadores.tiempo_por_etapa)
