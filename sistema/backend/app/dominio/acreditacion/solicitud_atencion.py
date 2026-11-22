"""La Solicitud de Atencion Medica que el robot capturo de ACREDITA SALUD
(se guarda cifrada, C-12): se entrega descifrada a quien puede verla y la
consulta queda en el historial de la cuenta, sin datos del paciente."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from typing import Protocol

from app.dominio.acreditacion.puertos import ErrorAcreditacion, RepositorioAcreditacion
from app.dominio.puertos_comunes import Evento, RegistroEventos

TIPO_EVENTO_SOLICITUD_CONSULTADA = "SOLICITUD_ATENCION_CONSULTADA"
_SUFIJO_CIFRADO = ".cifrado"


class ErrorSolicitudAtencionNoDisponible(ErrorAcreditacion):
    """La acreditacion vigente no tiene la solicitud capturada (registro en
    contingencia, por ejemplo) o el archivo no se pudo leer."""


@dataclass(frozen=True, slots=True)
class DocumentoSolicitudAtencion:
    contenido: bytes
    tipo_contenido: str


class AlmacenEvidencias(Protocol):
    def leer(self, ruta: str) -> bytes:
        """El contenido descifrado; ErrorSolicitudAtencionNoDisponible si no
        existe o no se puede descifrar."""
        ...


def tipo_contenido(ruta: str) -> str:
    tipo, _ = mimetypes.guess_type(ruta.removesuffix(_SUFIJO_CIFRADO))
    return tipo or "application/octet-stream"


class VerSolicitudAtencion:
    def __init__(
        self,
        repositorio: RepositorioAcreditacion,
        almacen: AlmacenEvidencias,
        registro_eventos: RegistroEventos,
    ) -> None:
        self._repositorio = repositorio
        self._almacen = almacen
        self._registro_eventos = registro_eventos

    async def ejecutar(self, cuenta_medica_id: int, actor: str) -> DocumentoSolicitudAtencion:
        acreditacion = await self._repositorio.obtener_acreditacion(cuenta_medica_id)
        ruta = acreditacion.resultado.ruta_evidencia if acreditacion else None
        if acreditacion is None or not ruta:
            raise ErrorSolicitudAtencionNoDisponible("La cuenta no tiene la solicitud de atención.")
        contenido = self._almacen.leer(ruta)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=TIPO_EVENTO_SOLICITUD_CONSULTADA,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"acreditacion_id": acreditacion.id},
            )
        )
        return DocumentoSolicitudAtencion(contenido=contenido, tipo_contenido=tipo_contenido(ruta))
