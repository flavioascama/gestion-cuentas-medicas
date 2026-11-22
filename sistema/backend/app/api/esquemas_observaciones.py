"""Esquemas Pydantic de /observaciones (CU-08 a CU-10, Fase 26)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.observaciones.casos_uso import ResultadoRegistroObservacion
from app.dominio.observaciones.valores import MotivoObservacion, Naturaleza, Observacion


class SolicitudRegistroObservacion(BaseModel):
    motivo_codigo: str = Field(min_length=1, max_length=10)
    es_parcial: bool
    detalle_campo_objetado: str | None = Field(default=None, max_length=500)
    monto_observado: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)


class RespuestaObservacionRegistrada(BaseModel):
    observacion_id: int
    naturaleza: str
    responsable_rol: str
    estado_cuenta: str

    @staticmethod
    def desde_valor(valor: ResultadoRegistroObservacion) -> RespuestaObservacionRegistrada:
        return RespuestaObservacionRegistrada(**campos(valor))


class ObservacionRespuesta(BaseModel):
    id: int
    cuenta_medica_id: int
    motivo_codigo: str
    naturaleza: str
    es_parcial: bool
    detalle_campo_objetado: str | None
    responsable_rol: str
    responsable_usuario_id: int | None
    estado: str
    respuesta_texto: str | None
    respuesta_sustento: str | None
    registrado_en: datetime
    respondido_en: datetime | None
    responsable_nombres: str | None = None
    monto_observado: Decimal | None = None
    resultado: str | None = None
    resultado_en: datetime | None = None
    # PENDIENTE | ENTREGADA | NO_ENTREGADA; None si no vino de la aseguradora
    # o aun no se responde.
    entrega_estado: str | None = None
    entrega_en: datetime | None = None
    entrega_solicitada_por: str | None = None

    @staticmethod
    def desde_valor(valor: Observacion) -> ObservacionRespuesta:
        return ObservacionRespuesta(**campos(valor))


class ResponsablePosibleRespuesta(BaseModel):
    """A quien se puede asignar una observacion: solo el nombre y los
    roles que responden observaciones."""

    id: int
    nombres: str
    roles: list[NombreRol]

    @staticmethod
    def desde_usuario(usuario: Usuario, roles: frozenset[NombreRol]) -> ResponsablePosibleRespuesta:
        assert usuario.id is not None
        return ResponsablePosibleRespuesta(
            id=usuario.id, nombres=usuario.nombres, roles=sorted(usuario.roles & roles)
        )


class MotivoObservacionRespuesta(BaseModel):
    codigo: str
    descripcion: str
    naturaleza: str

    @staticmethod
    def desde_valor(valor: MotivoObservacion) -> MotivoObservacionRespuesta:
        return MotivoObservacionRespuesta(**campos(valor))


class SolicitudAsignacionObservacion(BaseModel):
    """CU-09: ambos campos son opcionales -- el jefe puede confirmar sin
    cambiar nada mas que el responsable, o corregir tambien la
    naturaleza (lo que recalcula el rol responsable)."""

    responsable_usuario_id: int | None = None
    naturaleza_corregida: Naturaleza | None = None


class RespuestaNuevaEntrega(BaseModel):
    trabajo_id: int


class SolicitudRespuestaObservacion(BaseModel):
    respuesta_texto: str = Field(min_length=1, max_length=1000)
    respuesta_sustento: str | None = Field(default=None, max_length=500)
