"""Lote vigente leido de la base (2026-11-19): la nota o el reemplazo del
comprobante despues del lote lo desactualizan, la generacion y los lotes
sugeridos no repiten una cuenta de un lote en curso y vigente, y las de un
lote que dejo de serlo quedan libres."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_documentos_pago import (
    ComprobanteReemplazadoModelo,
    NotaDocumentoModelo,
)
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.repositorio_cuentas_por_lotear_sql import (
    RepositorioCuentasPorLotearSql,
)
from app.infraestructura.persistencia.repositorio_lote_sql import RepositorioLoteFacturacionSql
from app.infraestructura.persistencia.vigencia_lote_sql import vigencia_de_lote
from pruebas.prueba_lotes_sugeridos import _crear_cuenta

_GENERADO = datetime(2026, 11, 6, 12, 0, 0)
_DESPUES = datetime(2026, 11, 7, 9, 0, 0)


async def _base(sesion: AsyncSession) -> tuple[IpressModelo, IafasModelo]:
    ipress = IpressModelo(ruc="20690951848", codigo_ipress="15995250", razon_social="Clinica")
    iafas = IafasModelo(
        codigo="19395",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    sesion.add_all([ipress, iafas])
    await sesion.flush()
    return ipress, iafas


async def _lote(
    sesion: AsyncSession,
    iafas: IafasModelo,
    documentos: list[DocumentoFacturadorModelo],
    estado: str = "GENERADO",
) -> int:
    lote = LoteFacturacionModelo(
        numero=f"00000{documentos[0].id:02d}",
        iafas_id=iafas.id,
        periodo="202611",
        generado_en=_GENERADO,
        estado=estado,
    )
    sesion.add(lote)
    await sesion.flush()
    sesion.add_all(LoteDocumentoModelo(lote_id=lote.id, documento_id=d.id) for d in documentos)
    await sesion.flush()
    return lote.id


async def _anular(sesion: AsyncSession, documento: DocumentoFacturadorModelo) -> None:
    cuenta = await sesion.get(CuentaMedicaModelo, documento.cuenta_id)
    assert cuenta is not None
    cuenta.estado = "ANULADA"
    await sesion.flush()


async def _acreditar(sesion: AsyncSession, cuenta_id: int) -> None:
    sesion.add(
        AcreditacionModelo(
            cuenta_id=cuenta_id,
            condicion_cobertura="Cubierto",
            codigo_autorizacion="AUT-1",
            tipo_documento_autorizacion="1",
            codigo_asegurado="ASEG-1",
            tipo_afiliacion="1",
            instante=_GENERADO,
            componente_ejecutor="prueba",
        )
    )
    await sesion.flush()


async def prueba_nota_o_reemplazo_posterior_desactualizan_el_lote(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress, iafas = await _base(sesion)
        con_nota = await _crear_cuenta(sesion, ipress, iafas, "1", "FACTURADA")
        reemplazado = await _crear_cuenta(sesion, ipress, iafas, "2", "FACTURADA")
        intacta = await _crear_cuenta(sesion, ipress, iafas, "3", "FACTURADA")
        lote_id = await _lote(sesion, iafas, [con_nota, reemplazado, intacta])

        vigencia = await vigencia_de_lote(sesion, lote_id)
        assert vigencia is not None and vigencia.vigente

        sesion.add_all(
            [
                NotaDocumentoModelo(
                    documento_facturador_id=con_nota.id,
                    tipo="C",
                    serie="FC01",
                    numero="00000001",
                    monto=Decimal("10.00"),
                    fecha=date(2026, 11, 7),
                    motivo="D",
                    registrado_en=_DESPUES,
                    registrado_por="ana.analista",
                ),
                ComprobanteReemplazadoModelo(
                    documento_facturador_id=reemplazado.id,
                    tipo_documento_pago="01",
                    serie="F001",
                    numero="00000009",
                    fecha_emision=date(2026, 11, 5),
                    reemplazado_en=_DESPUES,
                    reemplazado_por="ana.analista",
                    motivo="Correccion",
                ),
            ]
        )
        await sesion.flush()

        vigencia = await vigencia_de_lote(sesion, lote_id)
        assert vigencia is not None
        assert vigencia.cuentas_que_cambiaron == ("CTA-000001", "CTA-000002")
        assert await vigencia_de_lote(sesion, 999) is None


async def prueba_sugeridos_y_generacion_no_repiten_cuentas_de_un_lote_vigente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress, iafas = await _base(sesion)
        en_vigente = await _crear_cuenta(sesion, ipress, iafas, "1", "FACTURADA")
        await _lote(sesion, iafas, [en_vigente])
        liberada = await _crear_cuenta(sesion, ipress, iafas, "2", "FACTURADA")
        anulada = await _crear_cuenta(sesion, ipress, iafas, "3", "FACTURADA")
        await _lote(sesion, iafas, [liberada, anulada], estado="VALIDADO")
        await _anular(sesion, anulada)
        for documento in (en_vigente, liberada):
            await _acreditar(sesion, documento.cuenta_id)

        sugeridas = await RepositorioCuentasPorLotearSql(sesion).cuentas_por_lotear()
        # La del lote vigente no se repite; la del lote desactualizado queda libre.
        assert [c.cuenta_id for c in sugeridas] == [liberada.cuenta_id]

        documentos = await RepositorioLoteFacturacionSql(sesion).obtener_documentos_facturados(
            iafas.id, [en_vigente.cuenta_id, liberada.cuenta_id]
        )
        assert [d.cuenta_medica_id for d in documentos] == [liberada.cuenta_id]


async def prueba_cargar_un_lote_desactualizado_responde_409(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress, iafas = await _base(sesion)
        intacta = await _crear_cuenta(sesion, ipress, iafas, "1", "FACTURADA")
        anulada = await _crear_cuenta(sesion, ipress, iafas, "2", "FACTURADA")
        lote_id = await _lote(sesion, iafas, [intacta, anulada])
        await _anular(sesion, anulada)
        await sesion.commit()

    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.post(
        f"/lotes/{lote_id}/carga-validador", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 409
    assert "LOTE_DESACTUALIZADO" in respuesta.text
    assert "CTA-000002" in respuesta.text
