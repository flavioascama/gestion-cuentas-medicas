"""DTOs del contexto de cierre y anulacion de la cuenta medica (Seccion
5.2.4.1, Tabla 58 T-12/T-13; CU-13, RF-21, Fase 28)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class EstadoSolicitudAnulacion(StrEnum):
    PENDIENTE = "PENDIENTE"
    APROBADA = "APROBADA"
    RECHAZADA = "RECHAZADA"


@dataclass(frozen=True, slots=True)
class DatosNuevaSolicitudAnulacion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2) de
    `RepositorioSolicitudesAnulacion.crear`."""

    cuenta_medica_id: int
    motivo: str
    solicitado_por: str
    solicitado_en: datetime


@dataclass(frozen=True, slots=True)
class SolicitudAnulacion:
    """Entidad de dominio, tal como la devuelve el repositorio."""

    id: int
    cuenta_medica_id: int
    motivo: str
    estado: EstadoSolicitudAnulacion
    solicitado_por: str
    solicitado_en: datetime
    resuelto_por: str | None
    resuelto_en: datetime | None
    # Para la bandeja (2026-11-18): antes solo se veia el id interno.
    identificacion_interna: str | None = None
    asegurado: str | None = None
    # Lo que el jefe anula (2026-11-19): estado de la cuenta, comprobante
    # vigente y nota de credito (serie-numero), si los hay.
    estado_cuenta: str | None = None
    comprobante: str | None = None
    nota_credito: str | None = None
