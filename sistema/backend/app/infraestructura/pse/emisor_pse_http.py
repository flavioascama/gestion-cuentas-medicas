"""Adaptador de EmisorPse contra el simulador (simuladores/pse/): un POST
sincrono, sin sesion asistida (mismo criterio de
ConsultorRespuestaReceptorHttp para el simulador receptor_iafas -- un
PSE real es API-a-API, no un portal navegado)."""

from __future__ import annotations

from datetime import date

import httpx

from app.dominio.pse.puertos import ComprobantePse, EmisorPse


class EmisorPseHttp(EmisorPse):
    def __init__(self, url_base: str, tiempo_espera_segundos: float = 10.0) -> None:
        self._url_base = url_base.rstrip("/")
        self._tiempo_espera_segundos = tiempo_espera_segundos

    async def emitir(self, ruc_ipress: str, codigo_ipress: str) -> ComprobantePse:
        async with httpx.AsyncClient(timeout=self._tiempo_espera_segundos) as cliente:
            respuesta = await cliente.post(
                f"{self._url_base}/comprobantes",
                json={"ruc_ipress": ruc_ipress, "codigo_ipress": codigo_ipress},
            )
        respuesta.raise_for_status()
        cuerpo = respuesta.json()
        return ComprobantePse(
            tipo_documento_pago=cuerpo["tipo_documento_pago"],
            serie=cuerpo["serie"],
            numero=cuerpo["numero"],
            fecha_emision=date.fromisoformat(cuerpo["fecha_emision"]),
        )
