"""Pruebas de los lotes sugeridos para "Generar lote": el periodo sale del
mes del comprobante, los grupos se arman por IAFAS y periodo, y solo
entran las cuentas facturadas que no estan ya en un lote en curso."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, time
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.integracion.lotes_sugeridos import (
    CuentaPorLotear,
    ErrorPeriodoLote,
    agrupar_en_lotes_sugeridos,
    periodo_unico,
)
from app.dominio.integracion.pendientes_lote import (
    COMPROBANTE_DESFASADO,
    pendientes_para_lotear,
)
from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
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
from app.infraestructura.persistencia.repositorio_cuentas_por_lotear_sql import (
    RepositorioCuentasPorLotearSql,
)

# --- periodo del lote -----------------------------------------------------


def prueba_periodo_unico_es_el_mes_de_los_comprobantes() -> None:
    assert periodo_unico([date(2026, 11, 3), date(2026, 11, 28)]) == "202611"


def prueba_periodo_unico_rechaza_comprobantes_de_meses_distintos() -> None:
    with pytest.raises(ErrorPeriodoLote, match="202610, 202611"):
        periodo_unico([date(2026, 11, 3), date(2026, 10, 31)])


def prueba_periodo_unico_rechaza_un_lote_sin_cuentas_facturadas() -> None:
    with pytest.raises(ErrorPeriodoLote, match="Ninguna"):
        periodo_unico([])


# --- agrupacion -----------------------------------------------------------


def _cuenta(cuenta_id: int, iafas_codigo: str, emision: date, monto: str) -> CuentaPorLotear:
    return CuentaPorLotear(
        cuenta_id=cuenta_id,
        identificacion_interna=f"CTA-{cuenta_id:06d}",
        nombres_asegurado="Nombre",
        apellidos_asegurado="Apellido",
        iafas_id=int(iafas_codigo),
        iafas_codigo=iafas_codigo,
        iafas_razon_social=f"IAFAS {iafas_codigo}",
        fecha_emision=emision,
        monto=Decimal(monto),
    )


def prueba_agrupar_separa_por_iafas_y_por_mes_del_comprobante() -> None:
    sugeridos = agrupar_en_lotes_sugeridos(
        [
            _cuenta(4, "19395", date(2026, 11, 9), "20.00"),
            _cuenta(1, "19395", date(2026, 11, 5), "50.00"),
            _cuenta(2, "05292", date(2026, 11, 7), "30.00"),
            _cuenta(3, "19395", date(2026, 10, 30), "10.00"),
        ]
    )

    assert [(s.periodo, s.iafas_codigo, [c.cuenta_id for c in s.cuentas]) for s in sugeridos] == [
        ("202610", "19395", [3]),
        ("202611", "05292", [2]),
        ("202611", "19395", [1, 4]),
    ]
    assert sugeridos[2].monto_total == Decimal("70.00")
    assert sugeridos[2].iafas_razon_social == "IAFAS 19395"


def prueba_agrupar_sin_cuentas_no_sugiere_nada() -> None:
    assert agrupar_en_lotes_sugeridos([]) == []


# --- RepositorioCuentasPorLotearSql ---------------------------------------


async def _crear_cuenta(
    sesion: AsyncSession, ipress: IpressModelo, iafas: IafasModelo, sufijo: str, estado: str
) -> DocumentoFacturadorModelo:
    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento=f"1111111{sufijo}",
        nombres="Nombre",
        apellidos=f"Apellido {sufijo}",
        iafas_id=iafas.id,
    )
    sesion.add(asegurado)
    await sesion.flush()
    cuenta = CuentaMedicaModelo(
        identificacion_interna=f"CTA-00000{sufijo}",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=date(2026, 10, 28),
        hora_prestacion=time(8, 0, 0),
        numero_historia_clinica=f"0000000{sufijo}",
        estado=estado,
    )
    sesion.add(cuenta)
    await sesion.flush()
    documento = DocumentoFacturadorModelo(
        cuenta_id=cuenta.id,
        ipress_id=ipress.id,
        tipo_documento_pago="01",
        serie="F001",
        numero=f"0000000{sufijo}",
        fecha_emision=date(2026, 11, 5),
    )
    sesion.add(documento)
    await sesion.flush()
    return documento


async def _poner_en_lote(
    sesion: AsyncSession, iafas: IafasModelo, documento: DocumentoFacturadorModelo, estado: str
) -> None:
    lote = LoteFacturacionModelo(
        numero=f"000000{documento.id}",
        iafas_id=iafas.id,
        periodo="202611",
        generado_en=datetime(2026, 11, 6, 12, 0, 0),
        estado=estado,
    )
    sesion.add(lote)
    await sesion.flush()
    sesion.add(LoteDocumentoModelo(lote_id=lote.id, documento_id=documento.id))
    await sesion.flush()


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
            fecha=date(2026, 10, 28),
        )
    )
    await sesion.flush()


async def prueba_repositorio_solo_devuelve_facturadas_fuera_de_un_lote_en_curso(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress = IpressModelo(ruc="20690951848", codigo_ipress="15995250", razon_social="Clinica")
        iafas = IafasModelo(
            codigo="19395",
            razon_social="IAFAS de prueba",
            periodicidad_remision_dias=7,
            ventana_monitoreo_horas=48,
        )
        sesion.add_all([ipress, iafas])
        await sesion.flush()

        libre = await _crear_cuenta(sesion, ipress, iafas, "1", "FACTURADA")
        await _agregar_procedimiento(sesion, libre.cuenta_id)
        for sufijo, estado_lote in (
            ("2", "GENERADO"),
            ("3", "CARGADO_VALIDADOR"),
            ("4", "VALIDADO"),
        ):
            en_curso = await _crear_cuenta(sesion, ipress, iafas, sufijo, "FACTURADA")
            await _poner_en_lote(sesion, iafas, en_curso, estado_lote)
        observada = await _crear_cuenta(sesion, ipress, iafas, "5", "FACTURADA")
        await _poner_en_lote(sesion, iafas, observada, "OBSERVADO_VALIDADOR")
        await _crear_cuenta(sesion, ipress, iafas, "6", "REGISTRADA")

        cuentas = await RepositorioCuentasPorLotearSql(sesion).cuentas_por_lotear()

        # La libre y la del lote observado por el validador; ni las que ya
        # estan en un lote en curso ni la que aun no esta facturada.
        assert [c.cuenta_id for c in cuentas] == [libre.cuenta_id, observada.cuenta_id]
        assert cuentas[0].monto == Decimal("100.00")
        assert cuentas[1].monto == Decimal("0.00")
        assert cuentas[0].fecha_emision == date(2026, 11, 5)
        assert (cuentas[0].iafas_id, cuentas[0].iafas_codigo) == (iafas.id, "19395")
        assert cuentas[0].apellidos_asegurado == "Apellido 1"


# --- rutas ----------------------------------------------------------------


async def prueba_ruta_de_lotes_sugeridos_no_se_confunde_con_el_detalle_de_un_lote(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.get("/lotes/sugeridos", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 200
    assert respuesta.json() == []


async def prueba_generar_sin_periodo_y_sin_cuentas_facturadas_responde_409(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.post(
        "/lotes",
        json={"iafas_id": 1, "cuenta_ids": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 409
    assert "LOTE_NO_GENERABLE" in respuesta.text


def prueba_un_comprobante_desfasado_es_pendiente_para_lotear() -> None:
    assert pendientes_para_lotear(True, 1, comprobante_desfasado=True) == (COMPROBANTE_DESFASADO,)
    assert pendientes_para_lotear(True, 1) == ()
