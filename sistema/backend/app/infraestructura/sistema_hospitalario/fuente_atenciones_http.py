"""Adaptador de FuenteAtenciones contra el sistema hospitalario de la
clinica (simuladores/sistema_hospitalario, 2026-11-19): consultas GET
sincronas, API a API, con la clave en la cabecera `X-Clave-Api`. Mismo
esquema de URL y tiempo de espera que EmisorPseHttp."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from app.dominio.integracion.atencion_hospitalaria import (
    AtencionHospitalaria,
    ErrorAtencionInvalida,
    ErrorSistemaHospitalarioNoDisponible,
    FuenteAtenciones,
    ResumenAtencionHospitalaria,
)
from app.infraestructura.sistema_hospitalario.esquema_atencion import (
    AtencionJson,
    ResumenAtencionJson,
)


class FuenteAtencionesHttp(FuenteAtenciones):
    def __init__(self, url_base: str, clave_api: str, tiempo_espera_segundos: float = 10.0) -> None:
        self._url_base = url_base.rstrip("/")
        self._clave_api = clave_api
        self._tiempo_espera_segundos = tiempo_espera_segundos

    async def _pedir(self, ruta: str, parametros: dict[str, str] | None = None) -> Any:
        """El cuerpo JSON de la respuesta; None si el sistema responde 404."""
        try:
            async with httpx.AsyncClient(timeout=self._tiempo_espera_segundos) as cliente:
                respuesta = await cliente.get(
                    f"{self._url_base}{ruta}",
                    params=parametros,
                    headers={"X-Clave-Api": self._clave_api},
                )
        except httpx.HTTPError as error:
            raise ErrorSistemaHospitalarioNoDisponible(
                "El sistema hospitalario no responde."
            ) from error
        if respuesta.status_code == httpx.codes.NOT_FOUND:
            return None
        if respuesta.is_error:
            raise ErrorSistemaHospitalarioNoDisponible(
                f"El sistema hospitalario respondio con el estado {respuesta.status_code}."
            )
        try:
            return respuesta.json()
        except ValueError as error:
            raise ErrorSistemaHospitalarioNoDisponible(
                "El sistema hospitalario respondio algo que no es JSON."
            ) from error

    async def listar(self, documento: str | None) -> list[ResumenAtencionHospitalaria]:
        cuerpo = await self._pedir("/atenciones", {"documento": documento} if documento else None)
        if not isinstance(cuerpo, list):
            raise ErrorSistemaHospitalarioNoDisponible(
                "El sistema hospitalario no devolvio la lista de atenciones."
            )
        try:
            return [ResumenAtencionJson.model_validate(fila).a_valor() for fila in cuerpo]
        except ValidationError as error:
            raise ErrorSistemaHospitalarioNoDisponible(
                "La lista de atenciones del sistema hospitalario no tiene la estructura esperada."
            ) from error

    async def obtener(self, atencion_id: str) -> AtencionHospitalaria | None:
        cuerpo = await self._pedir(f"/atenciones/{quote(atencion_id, safe='')}")
        if cuerpo is None:
            return None
        try:
            return AtencionJson.model_validate(cuerpo).a_valor()
        except ValidationError as error:
            raise ErrorAtencionInvalida(
                "ATENCION_MAL_FORMADA",
                f"La atencion {atencion_id} no tiene la estructura esperada.",
            ) from error
