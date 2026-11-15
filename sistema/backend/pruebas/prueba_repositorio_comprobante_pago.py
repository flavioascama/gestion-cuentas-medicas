"""Pruebas de RepositorioComprobantePagoSql contra SQLite en memoria
(adenda de ingesta y completitud, emision via el simulador PSE)."""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.integracion.puertos_ingesta import DatosNuevaCuenta
from app.dominio.pse.puertos import (
    ComprobantePse,
    ErrorComprobanteYaExiste,
    ErrorCuentaNoEncontrada,
)
from app.infraestructura.persistencia.modelos_integracion import IafasModelo, IpressModelo
from app.infraestructura.persistencia.repositorio_comprobante_pago_sql import (
    RepositorioComprobantePagoSql,
)
from app.infraestructura.persistencia.repositorio_ingesta_cuentas_sql import (
    RepositorioIngestaCuentasSql,
)

_COMPROBANTE = ComprobantePse(
    tipo_documento_pago="01", serie="F001", numero="00000001", fecha_emision=date(2026, 9, 28)
)


async def _sembrar_iafas_e_ipress(sesion: AsyncSession) -> int:
    iafas = IafasModelo(
        codigo="19395",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    ipress = IpressModelo(ruc="20123456789", codigo_ipress="15995250", razon_social="Clinica")
    sesion.add_all([iafas, ipress])
    await sesion.flush()
    return iafas.id


async def _sembrar_cuenta(sesion: AsyncSession) -> int:
    iafas_id = await _sembrar_iafas_e_ipress(sesion)
    await sesion.commit()
    repositorio_ingesta = RepositorioIngestaCuentasSql(sesion)
    return await repositorio_ingesta.crear_cuenta(
        DatosNuevaCuenta(
            tipo_documento_asegurado="1",
            numero_documento_asegurado="12345678",
            nombres_asegurado="Ana",
            apellidos_asegurado="Perez",
            iafas_id=iafas_id,
            fecha_prestacion=date(2026, 9, 28),
            hora_prestacion=time(9, 0, 0),
            diagnostico_principal_cie10=None,
        )
    )


async def prueba_obtener_ipress_propia_devuelve_ruc_y_codigo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_iafas_e_ipress(sesion)
        await sesion.commit()
        repositorio = RepositorioComprobantePagoSql(sesion)

        ruc, codigo = await repositorio.obtener_ipress_propia()

        assert ruc == "20123456789"
        assert codigo == "15995250"


async def prueba_guardar_comprobante_persiste_documento_facturador(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioComprobantePagoSql(sesion)

        documento_id = await repositorio.guardar_comprobante(cuenta_id, _COMPROBANTE)

        assert documento_id is not None
        estado = await repositorio.obtener_ipress_propia()
        assert estado == ("20123456789", "15995250")


async def prueba_guardar_comprobante_con_cuenta_inexistente_falla(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioComprobantePagoSql(sesion)

        with pytest.raises(ErrorCuentaNoEncontrada):
            await repositorio.guardar_comprobante(999, _COMPROBANTE)


async def prueba_guardar_comprobante_duplicado_falla(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioComprobantePagoSql(sesion)
        await repositorio.guardar_comprobante(cuenta_id, _COMPROBANTE)

        otro_comprobante = ComprobantePse(
            tipo_documento_pago="01", serie="F001", numero="00000002", fecha_emision=date.today()
        )
        with pytest.raises(ErrorComprobanteYaExiste):
            await repositorio.guardar_comprobante(cuenta_id, otro_comprobante)
