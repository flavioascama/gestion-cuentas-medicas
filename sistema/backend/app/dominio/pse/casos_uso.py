"""Caso de uso de la emision del comprobante de pago (adenda de ingesta y
completitud): resuelve la pieza "comprobante" y, con ella, lleva la cuenta
a FACTURADA (FacturarCuentaCompleta, 2026-11-19)."""

from __future__ import annotations

from app.dominio.integracion.facturacion_cuenta import FacturarCuentaCompleta
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.orquestacion.valores import ESTADOS_TERMINALES
from app.dominio.pse.puertos import (
    TIPO_FACTURA,
    ComprobanteEmitido,
    EmisorPse,
    ErrorCuentaNoEncontrada,
    ErrorFaltaParaFacturar,
    RepositorioComprobantePago,
    ResultadoEmisionComprobante,
    SolicitudComprobante,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos


class ErrorCuentaCerradaComprobante(Exception):
    pass


async def solicitud_comprobante(
    comprobantes: RepositorioComprobantePago, cuenta_id: int
) -> SolicitudComprobante:
    """Cliente y montos se calculan antes de emitir (2026-11-18): el PSE
    recibe lo que la cuenta factura y el comprobante guarda eso mismo."""
    datos = await comprobantes.datos_para_facturar(cuenta_id, TIPO_FACTURA)
    if datos is None:
        raise ErrorFaltaParaFacturar(("la acreditación del asegurado",))
    ruc_ipress, codigo_ipress = await comprobantes.obtener_ipress_propia()
    return SolicitudComprobante(
        ruc_ipress=ruc_ipress,
        codigo_ipress=codigo_ipress,
        tipo_comprobante=TIPO_FACTURA,
        cliente=datos.cliente,
        montos=datos.montos,
    )


class EmitirComprobantePago:
    def __init__(
        self,
        repositorio: RepositorioComprobantePago,
        emisor: EmisorPse,
        registro_eventos: RegistroEventos,
        estado_cuenta: RepositorioEstadoCuenta | None = None,
        facturacion: FacturarCuentaCompleta | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._emisor = emisor
        self._registro_eventos = registro_eventos
        self._estado_cuenta = estado_cuenta
        self._facturacion = facturacion

    async def ejecutar(self, cuenta_id: int, actor: str) -> ResultadoEmisionComprobante:
        # Tabla 69 (secuencia): nada despues de CERRADA o ANULADA.
        if self._estado_cuenta is not None:
            estado = await self._estado_cuenta.obtener_estado(cuenta_id)
            if estado in ESTADOS_TERMINALES:
                raise ErrorCuentaCerradaComprobante(
                    f"La cuenta {cuenta_id} esta en estado {estado!r}: no admite comprobante."
                )
        # El comprobante va al final (2026-11-18): antes se podia emitir sin
        # nada que facturar.
        requisitos = await self._repositorio.requisitos_para_facturar(cuenta_id)
        if requisitos is None:
            raise ErrorCuentaNoEncontrada(cuenta_id)
        faltantes = requisitos.faltantes()
        if faltantes:
            raise ErrorFaltaParaFacturar(faltantes)
        solicitud = await solicitud_comprobante(self._repositorio, cuenta_id)
        comprobante = await self._emisor.emitir(solicitud)
        documento_id = await self._repositorio.guardar_comprobante(
            cuenta_id, ComprobanteEmitido(comprobante, solicitud.montos)
        )
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="COMPROBANTE_PAGO_EMITIDO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "documento_id": documento_id,
                    "serie": comprobante.serie,
                    "numero": comprobante.numero,
                },
            )
        )
        # El comprobante es la ultima pieza (exige las demas): con el, la
        # cuenta queda FACTURADA aqui mismo y a nombre de quien lo emitio.
        if self._facturacion is not None:
            await self._facturacion.ejecutar(cuenta_id, actor)
        return ResultadoEmisionComprobante(documento_id=documento_id, comprobante=comprobante)
