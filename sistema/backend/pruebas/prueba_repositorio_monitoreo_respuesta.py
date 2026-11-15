"""Pruebas de RepositorioMonitoreoRespuestaSql contra SQLite en memoria
(Seccion 8.3): verifica el efecto real de aplicar_respuesta sobre
acuse_transmision, lote_facturacion y (solo si RECHAZADO) cuenta_medica."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.integracion.puertos import ErrorLoteNoMonitoreable
from app.infraestructura.persistencia.modelos_integracion import (
    AcuseTransmisionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.repositorio_monitoreo_respuesta_sql import (
    RepositorioMonitoreoRespuestaSql,
)


async def _sembrar_cuenta_enviada(
    sesion: AsyncSession, *, ventana_monitoreo_horas: int
) -> tuple[int, int, int]:
    """Devuelve (iafas_id, ipress_id, cuenta_id) de una IAFAS, una IPRESS y
    una cuenta medica ENVIADA nuevas."""

    iafas = IafasModelo(
        codigo="00012",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=ventana_monitoreo_horas,
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
        diagnostico_principal_cie10="E119",
        estado="ENVIADA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    return iafas.id, ipress.id, cuenta.id


async def _sembrar_lote_remitido(
    sesion: AsyncSession, *, ventana_monitoreo_horas: int = 48
) -> tuple[int, int]:
    """Devuelve (lote_id, cuenta_id) de un lote REMITIDO_IAFAS con un acuse
    ENVIADO pendiente de respuesta del receptor, listo para monitorear."""

    iafas_id, ipress_id, cuenta_id = await _sembrar_cuenta_enviada(
        sesion, ventana_monitoreo_horas=ventana_monitoreo_horas
    )

    documento = DocumentoFacturadorModelo(
        cuenta_id=cuenta_id,
        ipress_id=ipress_id,
        tipo_documento_pago="01",
        serie="F001",
        numero="00000123",
        fecha_emision=date(2026, 9, 10),
        fecha_primer_envio=date(2026, 9, 16),
    )
    sesion.add(documento)
    await sesion.flush()

    lote = LoteFacturacionModelo(
        numero="0000001",
        iafas_id=iafas_id,
        periodo="202609",
        generado_en=datetime(2026, 9, 15, 8, 0, 0),
        estado="REMITIDO_IAFAS",
        nombre_s01="937_20123456789_12345678_00012_0000001_202609_20260915.S01",
        sha256_s01="a" * 64,
        ruta_s01="/reportes/lotes_validados/937_...S01",
        s01_obtenido_en=datetime(2026, 9, 16, 9, 0, 0),
    )
    sesion.add(lote)
    await sesion.flush()

    sesion.add(LoteDocumentoModelo(lote_id=lote.id, documento_id=documento.id))
    sesion.add(
        AcuseTransmisionModelo(
            lote_id=lote.id,
            resultado_transferencia="ENVIADO",
            motivo_transferencia=None,
            intentado_en=datetime(2026, 9, 16, 10, 0, 0),
        )
    )
    await sesion.commit()
    return lote.id, cuenta_id


async def prueba_obtener_contexto_lote_inexistente_devuelve_none(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioMonitoreoRespuestaSql(sesion)
        assert await repositorio.obtener_contexto_lote(999) is None


async def prueba_obtener_contexto_lote_devuelve_la_ventana_de_la_iafas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, _ = await _sembrar_lote_remitido(sesion, ventana_monitoreo_horas=72)
        repositorio = RepositorioMonitoreoRespuestaSql(sesion)

        contexto = await repositorio.obtener_contexto_lote(lote_id)

        assert contexto is not None
        assert contexto.lote_id == lote_id
        assert contexto.numero == "0000001"
        assert contexto.ventana_monitoreo_horas == 72


async def prueba_aplicar_respuesta_aceptado_lleva_la_cuenta_a_en_auditoria(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """Fase 25 (T-06, Seccion 5.2.4): "Inicio de la auditoria... al
    aceptarse el lote" -- antes del motor de orquestacion, la aceptacion
    no tenia a donde llevar la cuenta (EN_AUDITORIA no era un estado
    valido) y quedaba sin cambios; ahora es la transicion T-06."""

    async with fabrica_sesiones() as sesion:
        lote_id, cuenta_id = await _sembrar_lote_remitido(sesion)
        repositorio = RepositorioMonitoreoRespuestaSql(sesion)

        acuse_id, cuenta_medica_ids = await repositorio.aplicar_respuesta(
            lote_id, "ACEPTADO", None, datetime(2026, 9, 18, 10, 0, 0)
        )
        assert cuenta_medica_ids == (cuenta_id,)

    async with fabrica_sesiones() as sesion:
        lote = await sesion.get(LoteFacturacionModelo, lote_id)
        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        acuse = await sesion.get(AcuseTransmisionModelo, acuse_id)

        assert lote is not None and lote.estado == "ACEPTADO"
        assert cuenta is not None and cuenta.estado == "EN_AUDITORIA"
        assert acuse is not None
        assert acuse.respuesta_receptor == "ACEPTADO"
        assert acuse.respondido_en == datetime(2026, 9, 18, 10, 0, 0)


async def prueba_aplicar_respuesta_rechazado_marca_la_cuenta_rechazada(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, cuenta_id = await _sembrar_lote_remitido(sesion)
        repositorio = RepositorioMonitoreoRespuestaSql(sesion)

        acuse_id, cuenta_medica_ids = await repositorio.aplicar_respuesta(
            lote_id, "RECHAZADO", "estructura invalida", datetime(2026, 9, 18, 10, 0, 0)
        )
        assert cuenta_medica_ids == (cuenta_id,)

    async with fabrica_sesiones() as sesion:
        lote = await sesion.get(LoteFacturacionModelo, lote_id)
        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        acuse = await sesion.get(AcuseTransmisionModelo, acuse_id)

        assert lote is not None and lote.estado == "RECHAZADO"
        assert cuenta is not None and cuenta.estado == "RECHAZADA"
        assert acuse is not None
        assert acuse.respuesta_receptor == "RECHAZADO"
        assert acuse.motivo_receptor == "estructura invalida"


async def prueba_aplicar_respuesta_sin_acuse_pendiente_lanza_error(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, _ = await _sembrar_lote_remitido(sesion)
        repositorio = RepositorioMonitoreoRespuestaSql(sesion)
        # Ya se aplico una respuesta antes: no queda ningun acuse ENVIADO
        # con respuesta_receptor NULL.
        await repositorio.aplicar_respuesta(
            lote_id, "ACEPTADO", None, datetime(2026, 9, 18, 10, 0, 0)
        )

        with pytest.raises(ErrorLoteNoMonitoreable):
            await repositorio.aplicar_respuesta(
                lote_id, "ACEPTADO", None, datetime(2026, 9, 19, 10, 0, 0)
            )
