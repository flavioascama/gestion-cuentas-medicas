"""Pruebas de RepositorioValidacionOficialSql contra SQLite en memoria
(Seccion 8.3, 10, Fase 16)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.integracion.puertos_validacion import (
    ArchivoLote,
    DatosRegistrarValidacion,
    ObservacionLectura,
    ResultadoEtapaValidador,
)
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.modelos_plataformas import ObservacionValidadorModelo
from app.infraestructura.persistencia.repositorio_validacion_oficial_sql import (
    RepositorioValidacionOficialSql,
)

_OBSERVACION = ObservacionLectura(
    tabla="T1",
    numero_linea=3,
    campo_clave="123",
    campo="Codigo de IPRESS",
    valor_observado="99999999",
    codigo_error="SIM-001",
    descripcion="Codigo de IPRESS no asignado al usuario.",
)


@pytest_asyncio.fixture
async def lote_generado(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> int:
    async with fabrica_sesiones() as sesion:
        ipress = IpressModelo(ruc="20690951848", codigo_ipress="15995250", razon_social="Clinica")
        iafas = IafasModelo(
            codigo="96969",
            razon_social="IAFAS Dos",
            periodicidad_remision_dias=15,
            ventana_monitoreo_horas=72,
        )
        sesion.add_all([ipress, iafas])
        await sesion.flush()
        lote = LoteFacturacionModelo(
            numero="0000004",
            iafas_id=iafas.id,
            periodo="202609",
            generado_en=datetime(2026, 9, 25, 10, 0, tzinfo=UTC),
            estado="GENERADO",
        )
        sesion.add(lote)
        await sesion.commit()
        return lote.id


async def prueba_obtener_estado_lote_devuelve_none_si_no_existe(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        assert await repositorio.obtener_estado_lote(999) is None


async def prueba_obtener_lote_para_carga_recomputa_los_tres_archivos(
    fabrica_sesiones: async_sessionmaker[AsyncSession], lote_generado: int
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        lote = await repositorio.obtener_lote_para_carga(lote_generado)

    assert lote is not None
    assert lote.numero == "0000004"
    assert lote.periodo == "202609"
    nombres = [a.nombre for a in lote.archivos]
    assert nombres == [
        "dfac_20690951848_15995250_96969_0000004_202609_20260925.txt",
        "date_20690951848_15995250_96969_0000004_202609_20260925.txt",
        "dser_20690951848_15995250_96969_0000004_202609_20260925.txt",
    ]


async def _crear_documento_facturado(
    sesion: AsyncSession, ipress: IpressModelo, iafas: IafasModelo
) -> DocumentoFacturadorModelo:
    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento="12345678",
        nombres="Nombre",
        apellidos="Apellido",
        iafas_id=iafas.id,
    )
    sesion.add(asegurado)
    await sesion.flush()
    cuenta = CuentaMedicaModelo(
        identificacion_interna="CTA-000001",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=date(2026, 9, 15),
        hora_prestacion=time(8, 0, 0),
        numero_historia_clinica="00000001",
        estado="FACTURADA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    documento = DocumentoFacturadorModelo(
        cuenta_id=cuenta.id,
        ipress_id=ipress.id,
        tipo_documento_pago="01",
        serie="F001",
        numero="00000001",
        fecha_emision=date(2026, 9, 15),
    )
    sesion.add(documento)
    await sesion.flush()
    return documento


@pytest_asyncio.fixture
async def lote_generado_con_producto(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> int:
    """Igual que `lote_generado`, pero con un `producto_facturado` real
    encadenado, para ejercitar la inclusion condicional de T4 (Fase 17)."""

    async with fabrica_sesiones() as sesion:
        ipress = IpressModelo(ruc="20690951848", codigo_ipress="15995250", razon_social="Clinica")
        iafas = IafasModelo(
            codigo="96969",
            razon_social="IAFAS Dos",
            periodicidad_remision_dias=15,
            ventana_monitoreo_horas=72,
        )
        sesion.add_all([ipress, iafas])
        await sesion.flush()
        documento = await _crear_documento_facturado(sesion, ipress, iafas)
        sesion.add(
            ProductoFacturadoModelo(
                cuenta_medica_id=documento.cuenta_id,
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
        lote = LoteFacturacionModelo(
            numero="0000004",
            iafas_id=iafas.id,
            periodo="202609",
            generado_en=datetime(2026, 9, 25, 10, 0, tzinfo=UTC),
            estado="GENERADO",
        )
        sesion.add(lote)
        await sesion.flush()
        sesion.add(LoteDocumentoModelo(lote_id=lote.id, documento_id=documento.id))
        await sesion.commit()
        return lote.id


async def prueba_obtener_lote_para_carga_incluye_t4_cuando_hay_productos(
    fabrica_sesiones: async_sessionmaker[AsyncSession], lote_generado_con_producto: int
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        resultado = await repositorio.obtener_lote_para_carga(lote_generado_con_producto)

    assert resultado is not None
    nombres = [a.nombre for a in resultado.archivos]
    assert nombres == [
        "dfac_20690951848_15995250_96969_0000004_202609_20260925.txt",
        "date_20690951848_15995250_96969_0000004_202609_20260925.txt",
        "dser_20690951848_15995250_96969_0000004_202609_20260925.txt",
        "dfar_20690951848_15995250_96969_0000004_202609_20260925.txt",
    ]


async def prueba_registrar_validacion_forma_conforme_pone_cargado_validador(
    fabrica_sesiones: async_sessionmaker[AsyncSession], lote_generado: int
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        await repositorio.registrar_validacion(
            DatosRegistrarValidacion(
                lote_id=lote_generado,
                trabajo_id=10,
                etapa="FORMA",
                resultado=ResultadoEtapaValidador(conforme=True, estado_informado="Registrado"),
                ruta_reporte=None,
                sha256_reporte=None,
                instante=datetime(2026, 9, 26, 9, 0, tzinfo=UTC),
            )
        )
        assert await repositorio.obtener_estado_lote(lote_generado) == "CARGADO_VALIDADOR"


async def prueba_registrar_validacion_observado_persiste_observaciones(
    fabrica_sesiones: async_sessionmaker[AsyncSession], lote_generado: int
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        validacion_id = await repositorio.registrar_validacion(
            DatosRegistrarValidacion(
                lote_id=lote_generado,
                trabajo_id=10,
                etapa="FORMA",
                resultado=ResultadoEtapaValidador(
                    conforme=False, estado_informado="Observado", observaciones=(_OBSERVACION,)
                ),
                ruta_reporte="/reportes/validacion_oficial/1_forma.xlsx",
                sha256_reporte="abc123",
                instante=datetime(2026, 9, 26, 9, 0, tzinfo=UTC),
            )
        )
        assert await repositorio.obtener_estado_lote(lote_generado) == "OBSERVADO_VALIDADOR"

    async with fabrica_sesiones() as sesion:
        consulta = select(ObservacionValidadorModelo).where(
            ObservacionValidadorModelo.validacion_oficial_id == validacion_id
        )
        filas = (await sesion.execute(consulta)).scalars().all()
        assert len(filas) == 1
        assert filas[0].codigo_error == "SIM-001"
        assert filas[0].numero_linea == 3


async def prueba_registrar_validacion_detallada_conforme_no_cambia_el_estado(
    fabrica_sesiones: async_sessionmaker[AsyncSession], lote_generado: int
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        await repositorio.registrar_validacion(
            DatosRegistrarValidacion(
                lote_id=lote_generado,
                trabajo_id=10,
                etapa="FORMA",
                resultado=ResultadoEtapaValidador(conforme=True, estado_informado="Registrado"),
                ruta_reporte=None,
                sha256_reporte=None,
                instante=datetime(2026, 9, 26, 9, 0, tzinfo=UTC),
            )
        )
        await repositorio.registrar_validacion(
            DatosRegistrarValidacion(
                lote_id=lote_generado,
                trabajo_id=10,
                etapa="DETALLADA",
                resultado=ResultadoEtapaValidador(conforme=True, estado_informado="VALIDADO"),
                ruta_reporte=None,
                sha256_reporte=None,
                instante=datetime(2026, 9, 26, 9, 5, tzinfo=UTC),
            )
        )
        assert await repositorio.obtener_estado_lote(lote_generado) == "CARGADO_VALIDADOR"


async def prueba_registrar_archivo_transmision_pone_validado(
    fabrica_sesiones: async_sessionmaker[AsyncSession], lote_generado: int
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        archivo = ArchivoLote(
            nombre="937_20690951848_15995250_96969_0000004_202609_20260925.S01",
            contenido=b"cifrado",
        )
        await repositorio.registrar_archivo_transmision(
            lote_id=lote_generado,
            archivo=archivo,
            ruta_s01="/artefactos_s01/937_....S01",
            sha256_s01="deadbeef",
            instante=datetime(2026, 9, 26, 9, 10, tzinfo=UTC),
        )

    async with fabrica_sesiones() as sesion:
        lote = await sesion.get(LoteFacturacionModelo, lote_generado)
        assert lote is not None
        assert lote.estado == "VALIDADO"
        assert lote.nombre_s01 == archivo.nombre
        assert lote.sha256_s01 == "deadbeef"
        assert lote.s01_obtenido_en is not None


async def prueba_lotes_para_envio_susalud_solo_los_no_enviados_del_periodo(
    fabrica_sesiones: async_sessionmaker[AsyncSession], lote_generado: int
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        # Todavia GENERADO: no califica.
        pendientes = await repositorio.obtener_lotes_para_envio_susalud("202609")
        assert pendientes == ()

        await repositorio.registrar_archivo_transmision(
            lote_id=lote_generado,
            archivo=ArchivoLote(nombre="937_....S01", contenido=b"x"),
            ruta_s01="/artefactos_s01/937_....S01",
            sha256_s01="deadbeef",
            instante=datetime(2026, 9, 26, 9, 10, tzinfo=UTC),
        )
        # VALIDADO tampoco: la norma pide reportar lo ya remitido a la IAFAS.
        assert await repositorio.obtener_lotes_para_envio_susalud("202609") == ()

        lote = await sesion.get(LoteFacturacionModelo, lote_generado)
        assert lote is not None
        lote.estado = "REMITIDO_IAFAS"
        await sesion.flush()
        pendientes = await repositorio.obtener_lotes_para_envio_susalud("202609")
        assert len(pendientes) == 1
        assert pendientes[0].lote_id == lote_generado

        # RECHAZADO se corrige y se reporta despues, en un lote nuevo.
        lote.estado = "RECHAZADO"
        await sesion.flush()
        assert await repositorio.obtener_lotes_para_envio_susalud("202609") == ()
        lote.estado = "REMITIDO_IAFAS"
        await sesion.flush()

        await repositorio.marcar_enviados_susalud(
            (lote_generado,), datetime(2026, 9, 26, 9, 20, tzinfo=UTC)
        )
        assert await repositorio.obtener_lotes_para_envio_susalud("202609") == ()


async def prueba_ruta_archivo_usa_la_fecha_de_generado_en(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress = IpressModelo(ruc="20111111111", codigo_ipress="11111111", razon_social="Otra")
        iafas = IafasModelo(
            codigo="12345",
            razon_social="IAFAS Uno",
            periodicidad_remision_dias=15,
            ventana_monitoreo_horas=72,
        )
        sesion.add_all([ipress, iafas])
        await sesion.flush()
        lote = LoteFacturacionModelo(
            numero="0000001",
            iafas_id=iafas.id,
            periodo="202601",
            generado_en=datetime.combine(date(2026, 1, 15), datetime.min.time(), tzinfo=UTC),
            estado="GENERADO",
        )
        sesion.add(lote)
        await sesion.commit()

        repositorio = RepositorioValidacionOficialSql(sesion)
        resultado = await repositorio.obtener_lote_para_carga(lote.id)
        assert resultado is not None
        assert resultado.archivos[0].nombre.endswith("20260115.txt")
