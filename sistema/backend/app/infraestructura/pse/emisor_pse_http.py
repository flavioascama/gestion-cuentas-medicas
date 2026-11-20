"""Adaptador de EmisorPse contra el simulador (simuladores/pse/): un POST
sincrono, sin sesion asistida (mismo criterio de
ConsultorRespuestaReceptorHttp para el simulador receptor_iafas -- un
PSE real es API-a-API, no un portal navegado)."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx

from app.dominio.pse.puertos import (
    ComprobantePse,
    EmisorPse,
    NotaPse,
    SolicitudComprobante,
    SolicitudNota,
)


class EmisorPseHttp(EmisorPse):
    def __init__(self, url_base: str, tiempo_espera_segundos: float = 10.0) -> None:
        self._url_base = url_base.rstrip("/")
        self._tiempo_espera_segundos = tiempo_espera_segundos

    async def _enviar(self, ruta: str, datos: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._tiempo_espera_segundos) as cliente:
            respuesta = await cliente.post(f"{self._url_base}{ruta}", json=datos)
        respuesta.raise_for_status()
        cuerpo: dict[str, Any] = respuesta.json()
        return cuerpo

    async def emitir(self, solicitud: SolicitudComprobante) -> ComprobantePse:
        # Los montos van como texto para no perder decimales en el JSON.
        montos = solicitud.montos
        cuerpo = await self._enviar(
            "/comprobantes",
            {
                "ruc_ipress": solicitud.ruc_ipress,
                "codigo_ipress": solicitud.codigo_ipress,
                "tipo_comprobante": solicitud.tipo_comprobante,
                "codigo_cliente": solicitud.cliente.codigo_iafas,
                "razon_social_cliente": solicitud.cliente.razon_social,
                "valor_venta": str(montos.valor_venta),
                "igv": str(montos.igv),
                "total": str(montos.total),
            },
        )
        return ComprobantePse(
            tipo_documento_pago=cuerpo["tipo_documento_pago"],
            serie=cuerpo["serie"],
            numero=cuerpo["numero"],
            fecha_emision=date.fromisoformat(cuerpo["fecha_emision"]),
        )

    async def emitir_nota(self, solicitud: SolicitudNota) -> NotaPse:
        referido = solicitud.referido
        cuerpo = await self._enviar(
            "/notas",
            {
                "ruc_ipress": solicitud.ruc_ipress,
                "codigo_ipress": solicitud.codigo_ipress,
                "tipo": solicitud.tipo,
                "monto": str(solicitud.monto),
                "comprobante_referido": {
                    "tipo_comprobante": referido.tipo_documento_pago,
                    "serie": referido.serie,
                    "numero": referido.numero,
                },
            },
        )
        return NotaPse(
            serie=cuerpo["serie"],
            numero=cuerpo["numero"],
            fecha_emision=date.fromisoformat(cuerpo["fecha_emision"]),
        )
