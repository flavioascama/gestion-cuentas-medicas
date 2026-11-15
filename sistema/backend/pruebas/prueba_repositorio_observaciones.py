"""Pruebas de RepositorioCatalogoMotivosSql y RepositorioObservacionesSql
contra SQLite en memoria (Seccion 5.2.4.2, Fase 26)."""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.observaciones.valores import DatosNuevaObservacion, Naturaleza
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.modelos_observaciones import (
    CatalogoMotivoObservacionModelo,
)
from app.infraestructura.persistencia.repositorio_observaciones_sql import (
    RepositorioCatalogoMotivosSql,
    RepositorioObservacionesSql,
)

_AHORA = datetime(2026, 11, 8, 10, 0, 0)


async def _sembrar_cuenta(sesion: AsyncSession) -> int:
    iafas = IafasModelo(
        codigo="00012",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
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
        estado="EN_AUDITORIA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta.id


async def _sembrar_motivo(sesion: AsyncSession) -> None:
    sesion.add(
        CatalogoMotivoObservacionModelo(
            codigo="OBS-01", descripcion="Datos incompletos", naturaleza="ADMINISTRATIVA"
        )
    )
    await sesion.flush()


async def prueba_catalogo_motivos_obtener_y_listar(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_motivo(sesion)
        repositorio = RepositorioCatalogoMotivosSql(sesion)

        motivo = await repositorio.obtener("OBS-01")
        assert motivo is not None
        assert motivo.naturaleza == Naturaleza.ADMINISTRATIVA

        assert await repositorio.obtener("NO-EXISTE") is None
        assert len(await repositorio.listar()) == 1


async def prueba_crear_obtener_y_listar_por_cuenta(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_motivo(sesion)
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioObservacionesSql(sesion)

        observacion_id = await repositorio.crear(
            DatosNuevaObservacion(
                cuenta_medica_id=cuenta_id,
                motivo_codigo="OBS-01",
                naturaleza=Naturaleza.ADMINISTRATIVA,
                es_parcial=False,
                detalle_campo_objetado="Historia clinica en blanco",
                responsable_rol=NombreRol.ANALISTA,
                registrado_en=_AHORA,
            )
        )
        await sesion.commit()

        observacion = await repositorio.obtener(observacion_id)
        assert observacion is not None
        assert observacion.cuenta_medica_id == cuenta_id
        assert observacion.naturaleza == Naturaleza.ADMINISTRATIVA
        assert observacion.responsable_rol == NombreRol.ANALISTA
        assert observacion.estado == "ABIERTA"
        assert observacion.detalle_campo_objetado == "Historia clinica en blanco"

        listadas = await repositorio.listar_por_cuenta(cuenta_id)
        assert [o.id for o in listadas] == [observacion_id]

        assert await repositorio.obtener(999) is None


async def prueba_reasignar_cambia_naturaleza_rol_y_usuario(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_motivo(sesion)
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioObservacionesSql(sesion)
        observacion_id = await repositorio.crear(
            DatosNuevaObservacion(
                cuenta_medica_id=cuenta_id,
                motivo_codigo="OBS-01",
                naturaleza=Naturaleza.ADMINISTRATIVA,
                es_parcial=False,
                detalle_campo_objetado=None,
                responsable_rol=NombreRol.ANALISTA,
                registrado_en=_AHORA,
            )
        )
        await sesion.commit()

        await repositorio.reasignar(observacion_id, Naturaleza.TECNICA, NombreRol.AUDITOR, 5)
        await sesion.commit()

        observacion = await repositorio.obtener(observacion_id)
        assert observacion is not None
        assert observacion.naturaleza == Naturaleza.TECNICA
        assert observacion.responsable_rol == NombreRol.AUDITOR
        assert observacion.responsable_usuario_id == 5


async def prueba_responder_marca_respondida_con_texto_y_sustento(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_motivo(sesion)
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioObservacionesSql(sesion)
        observacion_id = await repositorio.crear(
            DatosNuevaObservacion(
                cuenta_medica_id=cuenta_id,
                motivo_codigo="OBS-01",
                naturaleza=Naturaleza.ADMINISTRATIVA,
                es_parcial=False,
                detalle_campo_objetado=None,
                responsable_rol=NombreRol.ANALISTA,
                registrado_en=_AHORA,
            )
        )
        await sesion.commit()

        respondido_en = datetime(2026, 11, 9, 8, 0, 0)
        await repositorio.responder(
            observacion_id, "Se adjunta sustento.", "archivo.pdf", respondido_en
        )
        await sesion.commit()

        observacion = await repositorio.obtener(observacion_id)
        assert observacion is not None
        assert observacion.estado == "RESPONDIDA"
        assert observacion.respuesta_texto == "Se adjunta sustento."
        assert observacion.respuesta_sustento == "archivo.pdf"
        assert observacion.respondido_en == respondido_en
