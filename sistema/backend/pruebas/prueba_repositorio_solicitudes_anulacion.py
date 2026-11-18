"""Pruebas de RepositorioSolicitudesAnulacionSql contra SQLite en
memoria (Seccion 5.2.4.1, RF-21, Fase 28)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.cierre.valores import DatosNuevaSolicitudAnulacion, EstadoSolicitudAnulacion
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.repositorio_solicitudes_anulacion_sql import (
    RepositorioSolicitudesAnulacionSql,
)

_AHORA = datetime(2026, 11, 8, 10, 0, 0)


async def _sembrar_cuenta(sesion: AsyncSession) -> int:
    # Sufijo unico (en vez de los valores fijos de otras fases): esta
    # version de la prueba siembra mas de una cuenta por prueba
    # (prueba_listar_pendientes_excluye_las_ya_resueltas), y los campos
    # unicos de iafas/ipress/asegurado/cuenta chocarian si se repitieran.
    sufijo = uuid.uuid4().hex[:8]
    iafas = (
        await sesion.execute(sa.select(IafasModelo).where(IafasModelo.codigo == "00012"))
    ).scalar_one_or_none()
    if iafas is None:
        iafas = IafasModelo(
            codigo="00012",
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
        fecha_prestacion=date(2026, 9, 10),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica="00000001",
        estado="FACTURADA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta.id


async def prueba_crear_obtener_y_pendiente_por_cuenta(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioSolicitudesAnulacionSql(sesion)

        solicitud_id = await repositorio.crear(
            DatosNuevaSolicitudAnulacion(
                cuenta_medica_id=cuenta_id,
                motivo="paciente no se presento",
                solicitado_por="ana.analista",
                solicitado_en=_AHORA,
            )
        )
        await sesion.commit()

        solicitud = await repositorio.obtener(solicitud_id)
        assert solicitud is not None
        assert solicitud.estado == EstadoSolicitudAnulacion.PENDIENTE
        assert solicitud.motivo == "paciente no se presento"

        pendiente = await repositorio.obtener_pendiente_por_cuenta(cuenta_id)
        assert pendiente is not None
        assert pendiente.id == solicitud_id

        assert await repositorio.obtener(999) is None


async def prueba_resolver_aprobada_y_rechazada(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioSolicitudesAnulacionSql(sesion)
        solicitud_id = await repositorio.crear(
            DatosNuevaSolicitudAnulacion(
                cuenta_medica_id=cuenta_id,
                motivo="motivo de prueba",
                solicitado_por="ana.analista",
                solicitado_en=_AHORA,
            )
        )
        await sesion.commit()

        resuelto_en = datetime(2026, 11, 9, 8, 0, 0)
        await repositorio.resolver(solicitud_id, True, "jefa.prueba", resuelto_en)
        await sesion.commit()

        solicitud = await repositorio.obtener(solicitud_id)
        assert solicitud is not None
        assert solicitud.estado == EstadoSolicitudAnulacion.APROBADA
        assert solicitud.resuelto_por == "jefa.prueba"
        assert solicitud.resuelto_en == resuelto_en

        # Ya resuelta: no aparece mas como pendiente.
        assert await repositorio.obtener_pendiente_por_cuenta(cuenta_id) is None


async def prueba_listar_pendientes_dice_la_cuenta_y_el_asegurado(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioSolicitudesAnulacionSql(sesion)
        await repositorio.crear(
            DatosNuevaSolicitudAnulacion(
                cuenta_medica_id=cuenta_id,
                motivo="duplicada",
                solicitado_por="ana.analista",
                solicitado_en=_AHORA,
            )
        )
        await sesion.commit()
        (pendiente,) = await repositorio.listar_pendientes()

    assert pendiente.identificacion_interna is not None
    assert pendiente.identificacion_interna.startswith("CTA")
    assert pendiente.asegurado == "Ana Perez"


async def prueba_listar_pendientes_excluye_las_ya_resueltas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_pendiente_id = await _sembrar_cuenta(sesion)
        cuenta_resuelta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioSolicitudesAnulacionSql(sesion)

        solicitud_pendiente_id = await repositorio.crear(
            DatosNuevaSolicitudAnulacion(
                cuenta_medica_id=cuenta_pendiente_id,
                motivo="pendiente",
                solicitado_por="ana.analista",
                solicitado_en=_AHORA,
            )
        )
        solicitud_resuelta_id = await repositorio.crear(
            DatosNuevaSolicitudAnulacion(
                cuenta_medica_id=cuenta_resuelta_id,
                motivo="ya resuelta",
                solicitado_por="ana.analista",
                solicitado_en=_AHORA,
            )
        )
        await sesion.commit()
        await repositorio.resolver(solicitud_resuelta_id, True, "jefa.prueba", _AHORA)
        await sesion.commit()

        pendientes = await repositorio.listar_pendientes()

        assert [s.id for s in pendientes] == [solicitud_pendiente_id]
        assert solicitud_resuelta_id not in [s.id for s in pendientes]
