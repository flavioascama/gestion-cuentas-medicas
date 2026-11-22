"""DTOs del contexto de cierre y anulacion de la cuenta medica (Seccion
5.2.4.1, Tabla 58 T-12/T-13; CU-13, RF-21, Fase 28)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
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
    # Lo que escribio el jefe al resolver: obligatorio al rechazar.
    motivo_resolucion: str | None = None


@dataclass(frozen=True, slots=True)
class CondicionesCierre:
    """Lo que CU-13 exige antes de cerrar (Tabla 52): el pago conciliado,
    sin diferencia con lo liquidado y sin observaciones sin responder."""

    pago_conciliado: bool
    diferencia: Decimal | None  # solo si es distinta de cero
    observaciones_sin_responder: int

    @property
    def procede(self) -> bool:
        return (
            self.pago_conciliado
            and self.diferencia is None
            and self.observaciones_sin_responder == 0
        )


@dataclass(frozen=True, slots=True)
class EstadoCierreCuenta:
    """Lo que la seccion de cierre y anulacion muestra de una cuenta: las
    condiciones del cierre y la solicitud de anulacion pendiente o, si no
    hay, la ultima resuelta."""

    condiciones: CondicionesCierre
    ultima_solicitud: SolicitudAnulacion | None
