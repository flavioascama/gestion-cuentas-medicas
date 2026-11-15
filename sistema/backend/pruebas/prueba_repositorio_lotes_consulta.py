"""Pruebas de RepositorioLotesConsultaSql contra SQLite en memoria (Fase
18, Seccion 11).

`listar()` se probaba solo con la base de datos vacia (pruebas de
autorizacion, Fase 18): nunca con un lote real, asi que nunca ejecutaba
`lote.iafas.codigo`. Contra Postgres real (Fase 19), esa linea fallaba
con `sqlalchemy.exc.MissingGreenlet` -- el `.join(IafasModelo)` de la
consulta no dejaba la relacion `iafas` cargada (le faltaba
`contains_eager`), asi que acceder a `lote.iafas` disparaba una carga
perezosa fuera del contexto async permitido. Esta prueba fija el
comportamiento correcto con un lote sembrado de verdad."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.repositorio_lotes_consulta_sql import (
    RepositorioLotesConsultaSql,
)


async def _sembrar_lote(sesion: AsyncSession) -> int:
    iafas = IafasModelo(
        codigo="19395",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    sesion.add(iafas)
    await sesion.flush()
    lote = LoteFacturacionModelo(
        numero="0000001",
        iafas_id=iafas.id,
        periodo="202609",
        generado_en=datetime(2026, 9, 25, 12, 0, 0),
        estado="GENERADO",
    )
    sesion.add(lote)
    await sesion.commit()
    return lote.id


async def prueba_listar_incluye_el_codigo_de_la_iafas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_lote(sesion)
        repositorio = RepositorioLotesConsultaSql(sesion)
        lotes = await repositorio.listar(None)
        assert len(lotes) == 1
        assert lotes[0].iafas_codigo == "19395"


async def prueba_listar_filtra_por_periodo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_lote(sesion)
        repositorio = RepositorioLotesConsultaSql(sesion)
        assert await repositorio.listar("202609") != []
        assert await repositorio.listar("202601") == []


async def _crear_cuenta_con_documento(
    sesion: AsyncSession,
    ipress: IpressModelo,
    iafas: IafasModelo,
    sufijo: str,
) -> DocumentoFacturadorModelo:
    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento=f"1111111{sufijo}",
        nombres="Nombre",
        apellidos="Apellido",
        iafas_id=iafas.id,
    )
    sesion.add(asegurado)
    await sesion.flush()
    cuenta = CuentaMedicaModelo(
        identificacion_interna=f"CTA-00000{sufijo}",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=date(2026, 9, 15),
        hora_prestacion=time(8, 0, 0),
        numero_historia_clinica=f"0000000{sufijo}",
        estado="FACTURADA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    documento = DocumentoFacturadorModelo(
        cuenta_id=cuenta.id,
        ipress_id=ipress.id,
        tipo_documento_pago="01",
        serie="F001",
        numero=f"0000000{sufijo}",
        fecha_emision=date(2026, 9, 15),
    )
    sesion.add(documento)
    await sesion.flush()
    return documento


async def _agregar_procedimiento(sesion: AsyncSession, cuenta_id: int) -> None:
    version_cpms = CpmsVersionModelo(etiqueta="v1", archivos_origen=[], conteo=0)
    sesion.add(version_cpms)
    await sesion.flush()
    sesion.add(
        ProcedimientoFacturadoModelo(
            cuenta_id=cuenta_id,
            descripcion_registrada="Consulta",
            codigo_asignado="99201",
            cpms_version_id=version_cpms.id,
            origen_codigo="coincidencia_exacta",
            cantidad=2,
            monto_unitario=Decimal("50.00"),
            fecha=date(2026, 9, 15),
        )
    )


def _agregar_producto(sesion: AsyncSession, cuenta_medica_id: int) -> None:
    sesion.add(
        ProductoFacturadoModelo(
            cuenta_medica_id=cuenta_medica_id,
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


async def _sembrar_lote_con_monto(sesion: AsyncSession) -> int:
    """Un lote con dos cuentas: una con un procedimiento, otra con un
    producto de farmacia -- para que la suma de monto_total ejercite las
    dos tablas de hecho, y la cuenta de cantidad_documentos cuente
    ambas, no solo una."""
    ipress = IpressModelo(ruc="20690951848", codigo_ipress="15995250", razon_social="Clinica")
    iafas = IafasModelo(
        codigo="19395",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    sesion.add_all([ipress, iafas])
    await sesion.flush()

    documento_1 = await _crear_cuenta_con_documento(sesion, ipress, iafas, "1")
    documento_2 = await _crear_cuenta_con_documento(sesion, ipress, iafas, "2")
    await _agregar_procedimiento(sesion, documento_1.cuenta_id)
    _agregar_producto(sesion, documento_2.cuenta_id)

    lote = LoteFacturacionModelo(
        numero="0000002",
        iafas_id=iafas.id,
        periodo="202609",
        generado_en=datetime(2026, 9, 25, 12, 0, 0),
        estado="GENERADO",
    )
    sesion.add(lote)
    await sesion.flush()
    sesion.add_all(
        [
            LoteDocumentoModelo(lote_id=lote.id, documento_id=documento_1.id),
            LoteDocumentoModelo(lote_id=lote.id, documento_id=documento_2.id),
        ]
    )
    await sesion.commit()
    return lote.id


async def prueba_listar_suma_procedimientos_y_productos_de_todas_las_cuentas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id = await _sembrar_lote_con_monto(sesion)
        repositorio = RepositorioLotesConsultaSql(sesion)
        lotes = await repositorio.listar(None)

    lote = next(fila for fila in lotes if fila.id == lote_id)
    assert lote.cantidad_documentos == 2
    # 2 * 50.00 (procedimiento) + 15.50 (producto) = 115.50
    assert lote.monto_total == Decimal("115.50")


async def prueba_listar_sin_cuentas_no_revienta(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_lote(sesion)
        repositorio = RepositorioLotesConsultaSql(sesion)
        lotes = await repositorio.listar(None)

    assert lotes[0].cantidad_documentos == 0
    assert lotes[0].monto_total == Decimal("0.00")


async def prueba_obtener_cuentas_suma_procedimientos_y_productos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id = await _sembrar_lote_con_monto(sesion)
        repositorio = RepositorioLotesConsultaSql(sesion)
        cuentas = await repositorio.obtener_cuentas(lote_id)

    assert [c.identificacion_interna for c in cuentas] == ["CTA-000001", "CTA-000002"]
    assert cuentas[0].nombres_asegurado == "Nombre"
    assert cuentas[0].apellidos_asegurado == "Apellido"
    assert cuentas[0].monto == Decimal("100.00")
    assert cuentas[1].monto == Decimal("15.50")
    # 2026-11-12: cada atencion del lote dice su estado y su fecha.
    assert all(c.estado for c in cuentas)
    assert all(c.fecha_prestacion is not None for c in cuentas)


async def prueba_obtener_cuentas_lote_sin_documentos_devuelve_vacio(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id = await _sembrar_lote(sesion)
        repositorio = RepositorioLotesConsultaSql(sesion)
        cuentas = await repositorio.obtener_cuentas(lote_id)

    assert cuentas == []


async def prueba_obtener_ruta_s01_none_cuando_no_tiene(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id = await _sembrar_lote(sesion)
        repositorio = RepositorioLotesConsultaSql(sesion)
        assert await repositorio.obtener_ruta_s01(lote_id) is None


async def prueba_obtener_ruta_s01_devuelve_la_ruta_guardada(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id = await _sembrar_lote(sesion)
        lote = await sesion.get(LoteFacturacionModelo, lote_id)
        assert lote is not None
        lote.ruta_s01 = "/datos/lotes/0000001.S01"
        await sesion.commit()

        repositorio = RepositorioLotesConsultaSql(sesion)
        assert await repositorio.obtener_ruta_s01(lote_id) == "/datos/lotes/0000001.S01"
