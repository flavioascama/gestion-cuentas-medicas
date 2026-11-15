"""Pruebas de RepositorioLoteRemisionSql contra SQLite en memoria (Seccion
7.8): verifica el efecto real de registrar_remision sobre las cuatro
tablas que toca -- acuse_transmision, documento_facturador (fecha_primer_envio
sin sobreescribir), cuenta_medica (estado) y lote_facturacion (estado). Los
disparadores de Postgres que ademas protegen fecha_primer_envio se
verifican aparte, contra Postgres real (docs/DECISIONES.md, Fase 7)."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
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
from app.infraestructura.persistencia.repositorio_lote_remision_sql import (
    RepositorioLoteRemisionSql,
)


async def _sembrar_cuenta_facturada(sesion: AsyncSession) -> tuple[int, int, int]:
    """Devuelve (iafas_id, ipress_id, cuenta_id) de una IAFAS, una IPRESS y
    una cuenta medica FACTURADA nuevas."""

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
        diagnostico_principal_cie10="E119",
        estado="FACTURADA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    return iafas.id, ipress.id, cuenta.id


async def _sembrar_lote_validado(
    sesion: AsyncSession, *, fecha_primer_envio: date | None = None
) -> tuple[int, int]:
    """Devuelve (lote_id, documento_id) de un lote VALIDADO con un solo
    documento, listo para remitir (Fase 13: RemitirLote ya no exige
    GENERADO, exige VALIDADO -- ver docs/MIGRACION_V2_A_V3.md, seccion 3)."""

    iafas_id, ipress_id, cuenta_id = await _sembrar_cuenta_facturada(sesion)

    documento = DocumentoFacturadorModelo(
        cuenta_id=cuenta_id,
        ipress_id=ipress_id,
        tipo_documento_pago="01",
        serie="F001",
        numero="00000123",
        fecha_emision=date(2026, 9, 10),
        fecha_primer_envio=fecha_primer_envio,
    )
    sesion.add(documento)
    await sesion.flush()

    lote = LoteFacturacionModelo(
        numero="0000001",
        iafas_id=iafas_id,
        periodo="202609",
        generado_en=datetime(2026, 9, 15, 8, 0, 0),
        estado="VALIDADO",
        nombre_s01="937_20123456789_12345678_00012_0000001_202609_20260915.S01",
        sha256_s01="a" * 64,
        ruta_s01="/reportes/lotes_validados/937_...S01",
        s01_obtenido_en=datetime(2026, 9, 15, 9, 0, 0),
    )
    sesion.add(lote)
    await sesion.flush()

    sesion.add(LoteDocumentoModelo(lote_id=lote.id, documento_id=documento.id))
    await sesion.commit()
    return lote.id, documento.id


async def prueba_registrar_remision_exitosa_marca_todo_en_cadena(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, documento_id = await _sembrar_lote_validado(sesion)
        repositorio = RepositorioLoteRemisionSql(sesion)

        lote_para_remitir = await repositorio.obtener_lote_para_remision(lote_id)
        assert lote_para_remitir is not None
        assert lote_para_remitir.estado == "VALIDADO"
        assert lote_para_remitir.documento_ids == (documento_id,)

        acuse_id, cuenta_medica_ids = await repositorio.registrar_remision(
            lote_id=lote_id,
            documento_ids=(documento_id,),
            exitosa=True,
            motivo=None,
            instante=datetime(2026, 9, 16, 10, 0, 0),
        )
        assert acuse_id > 0
        assert len(cuenta_medica_ids) == 1

    async with fabrica_sesiones() as sesion:
        lote = await sesion.get(LoteFacturacionModelo, lote_id)
        documento = await sesion.get(DocumentoFacturadorModelo, documento_id)
        cuenta = await sesion.get(CuentaMedicaModelo, documento.cuenta_id)  # type: ignore[union-attr]
        acuse = await sesion.get(AcuseTransmisionModelo, acuse_id)

        assert lote is not None and lote.estado == "REMITIDO_IAFAS"
        assert documento is not None and documento.fecha_primer_envio == date(2026, 9, 16)
        assert cuenta is not None and cuenta.estado == "ENVIADA"
        assert acuse is not None and acuse.resultado_transferencia == "ENVIADO"


async def prueba_registrar_remision_fallida_no_cambia_estados(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, documento_id = await _sembrar_lote_validado(sesion)
        repositorio = RepositorioLoteRemisionSql(sesion)
        _, cuenta_medica_ids = await repositorio.registrar_remision(
            lote_id=lote_id,
            documento_ids=(documento_id,),
            exitosa=False,
            motivo="conexion rechazada",
            instante=datetime(2026, 9, 16, 10, 0, 0),
        )
        assert cuenta_medica_ids == ()

    async with fabrica_sesiones() as sesion:
        lote = await sesion.get(LoteFacturacionModelo, lote_id)
        documento = await sesion.get(DocumentoFacturadorModelo, documento_id)
        cuenta = await sesion.get(CuentaMedicaModelo, documento.cuenta_id)  # type: ignore[union-attr]

        assert lote is not None and lote.estado == "VALIDADO"
        assert documento is not None and documento.fecha_primer_envio is None
        assert cuenta is not None and cuenta.estado == "FACTURADA"

        resultado = await sesion.execute(
            sa.select(AcuseTransmisionModelo).where(AcuseTransmisionModelo.lote_id == lote_id)
        )
        acuses = resultado.scalars().all()
        assert len(acuses) == 1
        assert acuses[0].resultado_transferencia == "ERROR_TRANSFERENCIA"
        assert acuses[0].motivo_transferencia == "conexion rechazada"


async def prueba_registrar_remision_no_sobreescribe_fecha_primer_envio_existente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    fecha_original = date(2026, 8, 1)
    async with fabrica_sesiones() as sesion:
        lote_id, documento_id = await _sembrar_lote_validado(
            sesion, fecha_primer_envio=fecha_original
        )
        repositorio = RepositorioLoteRemisionSql(sesion)
        await repositorio.registrar_remision(
            lote_id=lote_id,
            documento_ids=(documento_id,),
            exitosa=True,
            motivo=None,
            instante=datetime(2026, 9, 16, 10, 0, 0),
        )

    async with fabrica_sesiones() as sesion:
        documento = await sesion.get(DocumentoFacturadorModelo, documento_id)
        assert documento is not None
        assert documento.fecha_primer_envio == fecha_original


async def prueba_registrar_remision_rechaza_una_cuenta_que_no_esta_facturada(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """T-03 pasa por el motor de orquestacion (RF-08): una cuenta que no
    esta FACTURADA no puede pasar a ENVIADA aunque su documento este en el
    lote. Antes la remision escribia ENVIADA sin ninguna guarda."""

    async with fabrica_sesiones() as sesion:
        lote_id, documento_id = await _sembrar_lote_validado(sesion)
        documento = await sesion.get(DocumentoFacturadorModelo, documento_id)
        assert documento is not None
        await sesion.execute(
            sa.update(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == documento.cuenta_id)
            .values(estado="CERRADA")
        )
        await sesion.commit()

        repositorio = RepositorioLoteRemisionSql(sesion)
        with pytest.raises(ErrorTransicionNoDefinida):
            await repositorio.registrar_remision(
                lote_id=lote_id,
                documento_ids=(documento_id,),
                exitosa=True,
                motivo=None,
                instante=datetime(2026, 9, 16, 10, 0, 0),
            )
