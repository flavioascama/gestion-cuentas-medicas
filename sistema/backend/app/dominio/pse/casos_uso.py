"""Caso de uso de la emision del comprobante de pago (adenda de ingesta y
completitud): resuelve la pieza "comprobante" que
ConsultarCompletitudCuenta (casos_uso_ingesta.py) hasta ahora solo podia
reportar, nunca completar."""

from __future__ import annotations

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.orquestacion.valores import ESTADOS_TERMINALES
from app.dominio.pse.puertos import (
    EmisorPse,
    ErrorCuentaNoEncontrada,
    ErrorFaltaParaFacturar,
    RepositorioComprobantePago,
    ResultadoEmisionComprobante,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos


class ErrorCuentaCerradaComprobante(Exception):
    pass


class EmitirComprobantePago:
    def __init__(
        self,
        repositorio: RepositorioComprobantePago,
        emisor: EmisorPse,
        registro_eventos: RegistroEventos,
        estado_cuenta: RepositorioEstadoCuenta | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._emisor = emisor
        self._registro_eventos = registro_eventos
        self._estado_cuenta = estado_cuenta

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
        ruc_ipress, codigo_ipress = await self._repositorio.obtener_ipress_propia()
        comprobante = await self._emisor.emitir(ruc_ipress, codigo_ipress)
        documento_id = await self._repositorio.guardar_comprobante(cuenta_id, comprobante)
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
        return ResultadoEmisionComprobante(documento_id=documento_id, comprobante=comprobante)
