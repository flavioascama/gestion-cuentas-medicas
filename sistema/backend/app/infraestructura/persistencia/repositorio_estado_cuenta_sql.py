"""Adaptador de RepositorioEstadoCuenta (Seccion 5.2.4): compartido por
todos los casos de uso del motor de orquestacion que necesitan leer o
fijar `cuenta_medica.estado` tras una transicion ya validada."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)


class RepositorioEstadoCuentaSql(RepositorioEstadoCuenta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return (
            await self._sesion.execute(
                sa.select(CuentaMedicaModelo.estado).where(
                    CuentaMedicaModelo.id == cuenta_medica_id
                )
            )
        ).scalar_one_or_none()

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        await self._sesion.execute(
            sa.update(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_medica_id)
            .values(estado=estado_nuevo)
        )

    async def en_correccion_validador(self, cuenta_medica_id: int) -> bool:
        if await self.obtener_estado(cuenta_medica_id) != "FACTURADA":
            return False
        # El comprobante de reemplazo se guarda en la misma fila, asi que el
        # documento de la cuenta sigue enlazado a sus lotes anteriores.
        estado_lote = (
            await self._sesion.execute(
                sa.select(LoteFacturacionModelo.estado)
                .join(LoteDocumentoModelo, LoteDocumentoModelo.lote_id == LoteFacturacionModelo.id)
                .join(
                    DocumentoFacturadorModelo,
                    DocumentoFacturadorModelo.id == LoteDocumentoModelo.documento_id,
                )
                .where(DocumentoFacturadorModelo.cuenta_id == cuenta_medica_id)
                .order_by(LoteFacturacionModelo.generado_en.desc(), LoteFacturacionModelo.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return estado_lote == "OBSERVADO_VALIDADOR"
