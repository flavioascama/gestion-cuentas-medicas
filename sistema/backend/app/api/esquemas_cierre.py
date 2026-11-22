"""Esquemas Pydantic de /cuentas/{id}/cierre, /cuentas/{id}/anulacion y
/anulaciones (CU-13, RF-21, Fase 28)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.cierre.valores import EstadoCierreCuenta, SolicitudAnulacion


class RespuestaCierre(BaseModel):
    estado_cuenta: str


class SolicitudNuevaAnulacion(BaseModel):
    motivo: str = Field(min_length=1, max_length=500)


class RespuestaSolicitudAnulacion(BaseModel):
    solicitud_id: int


class SolicitudResolucionAnulacion(BaseModel):
    aprobada: bool
    # Obligatorio al rechazar (lo exige el caso de uso); opcional al aprobar.
    motivo: str | None = Field(default=None, max_length=500)


class RespuestaResolucionAnulacion(BaseModel):
    estado_cuenta: str | None


class SolicitudAnulacionRespuesta(BaseModel):
    id: int
    cuenta_medica_id: int
    motivo: str
    estado: str
    solicitado_por: str
    solicitado_en: datetime
    resuelto_por: str | None
    resuelto_en: datetime | None
    identificacion_interna: str | None = None
    solicitado_por_nombre: str | None = None
    asegurado: str | None = None
    estado_cuenta: str | None = None
    comprobante: str | None = None
    nota_credito: str | None = None
    motivo_resolucion: str | None = None

    @staticmethod
    def desde_valor(valor: SolicitudAnulacion) -> SolicitudAnulacionRespuesta:
        return SolicitudAnulacionRespuesta(**campos(valor))


class EstadoCierreRespuesta(BaseModel):
    """Lo que falta para cerrar y la ultima solicitud de anulacion."""

    pago_conciliado: bool
    diferencia: Decimal | None
    observaciones_sin_responder: int
    ultima_solicitud: SolicitudAnulacionRespuesta | None

    @staticmethod
    def desde_valor(valor: EstadoCierreCuenta) -> EstadoCierreRespuesta:
        solicitud = valor.ultima_solicitud
        return EstadoCierreRespuesta(
            pago_conciliado=valor.condiciones.pago_conciliado,
            diferencia=valor.condiciones.diferencia,
            observaciones_sin_responder=valor.condiciones.observaciones_sin_responder,
            ultima_solicitud=(
                None if solicitud is None else SolicitudAnulacionRespuesta.desde_valor(solicitud)
            ),
        )
