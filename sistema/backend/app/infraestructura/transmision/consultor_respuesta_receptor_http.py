"""Adaptador ConsultorRespuestaReceptor (Seccion 8.3, 9.2).

El portal de respuestas del simulador receptor IAFAS (Fase 8,
`simuladores/receptor_iafas/`) no tiene sesion, login, ni pasos
interactivos: cada pagina es una lectura HTTP simple de HTML ya
renderizado en el servidor. Por eso este adaptador usa `httpx` +
`BeautifulSoup`, no Playwright -- a diferencia de AcreditacionWeb (Fase
11), que si necesita un navegador real porque ACREDITA SALUD si tiene
sesion y varios pasos.
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from app.dominio.integracion.puertos import ConsultorRespuestaReceptor, RespuestaReceptor


class ErrorConsultaReceptor(Exception):
    pass


class ConsultorRespuestaReceptorHttp(ConsultorRespuestaReceptor):
    def __init__(self, url_base: str, tiempo_espera_segundos: float = 30.0) -> None:
        self._url_base = url_base.rstrip("/")
        self._tiempo_espera_segundos = tiempo_espera_segundos

    async def consultar(self, nombre_s01: str) -> RespuestaReceptor | None:
        async with httpx.AsyncClient(timeout=self._tiempo_espera_segundos) as cliente:
            respuesta = await cliente.get(f"{self._url_base}/lotes/{nombre_s01}")

        if respuesta.status_code == 404:
            return None
        respuesta.raise_for_status()

        sopa = BeautifulSoup(respuesta.text, "html.parser")
        elemento_estado = sopa.find(attrs={"data-testid": "detalle-estado"})
        if elemento_estado is None:
            raise ErrorConsultaReceptor(
                f"No se encontro 'detalle-estado' en la respuesta para {nombre_s01!r}."
            )
        estado = elemento_estado.get_text().strip().split(" ")[0]
        # La IAFAS recibio el lote y todavia no lo acepto ni lo rechazo.
        if estado == "RECIBIDO":
            return None

        elemento_motivo = sopa.find(attrs={"data-testid": "detalle-motivo"})
        motivo = elemento_motivo.get_text().strip() if elemento_motivo else None
        if motivo in (None, "-"):
            motivo = None

        return RespuestaReceptor(estado=estado, motivo=motivo)
