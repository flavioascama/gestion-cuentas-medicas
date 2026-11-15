"""Pruebas de RepositorioIngestaCuentasSql y RepositorioCompletitudCuentaSql
contra SQLite en memoria (adenda de ingesta y completitud, previa a R1.4)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.integracion.puertos_ingesta import DatosNuevaCuenta, ErrorIafasInexistente
from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.repositorio_ingesta_cuentas_sql import (
    RepositorioCompletitudCuentaSql,
    RepositorioIngestaCuentasSql,
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


def _datos_cuenta(iafas_id: int) -> DatosNuevaCuenta:
    return DatosNuevaCuenta(
        tipo_documento_asegurado="1",
        numero_documento_asegurado="12345678",
        nombres_asegurado="Ana",
        apellidos_asegurado="Perez",
        iafas_id=iafas_id,
        fecha_prestacion=date(2026, 9, 27),
        hora_prestacion=time(9, 0, 0),
        diagnostico_principal_cie10=None,
    )


async def prueba_crear_cuenta_genera_identificacion_y_asegurado_nuevo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas_e_ipress(sesion)
        await sesion.commit()
        repositorio = RepositorioIngestaCuentasSql(sesion)

        cuenta_id = await repositorio.crear_cuenta(_datos_cuenta(iafas_id))

        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None
        assert cuenta.estado == "REGISTRADA"
        assert cuenta.identificacion_interna == f"CTA-{cuenta_id:06d}"
        assert cuenta.numero_historia_clinica == f"{cuenta_id:08d}"

        asegurado = await sesion.get(AseguradoModelo, cuenta.asegurado_id)
        assert asegurado is not None
        assert asegurado.numero_documento == "12345678"
        assert asegurado.ficticio is True


async def prueba_crear_cuenta_reutiliza_asegurado_existente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas_e_ipress(sesion)
        await sesion.commit()
        repositorio = RepositorioIngestaCuentasSql(sesion)

        primera_cuenta_id = await repositorio.crear_cuenta(_datos_cuenta(iafas_id))
        segunda_cuenta_id = await repositorio.crear_cuenta(_datos_cuenta(iafas_id))

        primera = await sesion.get(CuentaMedicaModelo, primera_cuenta_id)
        segunda = await sesion.get(CuentaMedicaModelo, segunda_cuenta_id)
        assert primera is not None and segunda is not None
        assert primera.asegurado_id == segunda.asegurado_id


async def prueba_crear_cuenta_con_iafas_inexistente_falla(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioIngestaCuentasSql(sesion)

        with pytest.raises(ErrorIafasInexistente):
            await repositorio.crear_cuenta(_datos_cuenta(iafas_id=999))


async def prueba_completitud_de_cuenta_inexistente_devuelve_none(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioCompletitudCuentaSql(sesion)
        assert await repositorio.obtener_estado_piezas(999) is None


async def prueba_completitud_refleja_ausencia_de_piezas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas_e_ipress(sesion)
        await sesion.commit()
        repositorio_ingesta = RepositorioIngestaCuentasSql(sesion)
        cuenta_id = await repositorio_ingesta.crear_cuenta(_datos_cuenta(iafas_id))

        repositorio_completitud = RepositorioCompletitudCuentaSql(sesion)
        estado = await repositorio_completitud.obtener_estado_piezas(cuenta_id)

        assert estado is not None
        assert estado.estado_cuenta == "REGISTRADA"
        assert estado.tiene_acreditacion is False
        assert estado.cantidad_procedimientos == 0
        assert estado.tiene_comprobante is False


async def _sembrar_piezas_completas(sesion: AsyncSession, cuenta_id: int, ipress_id: int) -> None:
    version_cpms = CpmsVersionModelo(etiqueta="v1", archivos_origen=[], conteo=0)
    sesion.add(version_cpms)
    await sesion.flush()

    sesion.add(
        AcreditacionModelo(
            cuenta_id=cuenta_id,
            condicion_cobertura="CON_COBERTURA",
            codigo_autorizacion="AUT-1",
            tipo_documento_autorizacion="1",
            codigo_asegurado="ASE-1",
            tipo_afiliacion="1",
            instante=datetime.now(UTC),
            duracion_ms=100,
            componente_ejecutor="robot_acredita_salud",
        )
    )
    sesion.add(
        ProcedimientoFacturadoModelo(
            cuenta_id=cuenta_id,
            descripcion_registrada="Consulta",
            codigo_asignado="99201",
            cpms_version_id=version_cpms.id,
            origen_codigo="sugerencia",
            cantidad=1,
            monto_unitario="50.00",
            fecha=date(2026, 9, 27),
        )
    )
    sesion.add(
        DocumentoFacturadorModelo(
            cuenta_id=cuenta_id,
            ipress_id=ipress_id,
            tipo_documento_pago="01",
            serie="0001",
            numero="00000001",
            fecha_emision=date(2026, 9, 27),
        )
    )
    await sesion.commit()


async def prueba_completitud_refleja_piezas_presentes(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas_e_ipress(sesion)
        await sesion.commit()
        repositorio_ingesta = RepositorioIngestaCuentasSql(sesion)
        cuenta_id = await repositorio_ingesta.crear_cuenta(_datos_cuenta(iafas_id))

        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None
        await _sembrar_piezas_completas(sesion, cuenta_id, cuenta.ipress_id)

        repositorio_completitud = RepositorioCompletitudCuentaSql(sesion)
        estado = await repositorio_completitud.obtener_estado_piezas(cuenta_id)

        assert estado is not None
        assert estado.tiene_acreditacion is True
        assert estado.cantidad_procedimientos == 1
        assert estado.tiene_comprobante is True


async def prueba_marcar_facturada_solo_transiciona_desde_registrada(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas_e_ipress(sesion)
        await sesion.commit()
        repositorio_ingesta = RepositorioIngestaCuentasSql(sesion)
        cuenta_id = await repositorio_ingesta.crear_cuenta(_datos_cuenta(iafas_id))

        repositorio_completitud = RepositorioCompletitudCuentaSql(sesion)
        await repositorio_completitud.marcar_facturada(cuenta_id)

        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None
        assert cuenta.estado == "FACTURADA"

        await sesion.refresh(cuenta)
        cuenta.estado = "ENVIADA"
        await sesion.commit()

        await repositorio_completitud.marcar_facturada(cuenta_id)
        await sesion.refresh(cuenta)
        assert cuenta.estado == "ENVIADA"
