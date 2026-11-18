"""Esquemas Pydantic de /cpms, /cuentas/{id}/procedimientos y
/catalogo-cpms (Fase 18)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.api.serializacion import campos
from app.dominio.cpms.puertos import VersionCpms
from app.dominio.cpms.valores import ResultadoSugerencia


@dataclass(slots=True)
class ParametrosSugerenciaCpms:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): agrupa
    los parametros de consulta de `GET /cpms/sugerencias` para no superar
    el limite de 5 parametros por funcion (Seccion 3) junto con
    `caso_uso`, `actor` y `reloj`. FastAPI trata cada campo como un
    parametro de consulta independiente (patron "Classes as
    Dependencies")."""

    descripcion: str
    cuenta_medica_id: int | None = None
    codigo_grupo: str | None = None
    codigo_seccion: str | None = None
    codigo_subseccion: str | None = None


class CandidatoCpmsRespuesta(BaseModel):
    codigo: str
    denominacion: str
    codigo_grupo: str
    nombre_grupo: str
    codigo_seccion: str
    nombre_seccion: str
    codigo_subseccion: str
    nombre_subseccion: str
    puntaje: float
    posicion: int


class RespuestaSugerenciaCpms(BaseModel):
    cpms_version_id: int
    cpms_version_etiqueta: str
    coincidencia_exacta: bool
    candidatos: list[CandidatoCpmsRespuesta]
    # Seccion 6.4: quien confirme un codigo debe devolver este instante
    # como `inicio_sugerencia` (HTTP es sin estado, la API no lo recuerda).
    inicio_sugerencia: datetime

    @staticmethod
    def desde_valor(
        valor: ResultadoSugerencia, inicio_sugerencia: datetime
    ) -> RespuestaSugerenciaCpms:
        return RespuestaSugerenciaCpms(
            cpms_version_id=valor.cpms_version_id,
            cpms_version_etiqueta=valor.cpms_version_etiqueta,
            coincidencia_exacta=valor.coincidencia_exacta,
            candidatos=[CandidatoCpmsRespuesta(**campos(c)) for c in valor.candidatos],
            inicio_sugerencia=inicio_sugerencia,
        )


class SolicitudConfirmarProcedimiento(BaseModel):
    descripcion_registrada: str = Field(min_length=1, max_length=500)
    codigo_elegido: str = Field(min_length=1, max_length=20)
    posicion_aceptada: int | None = None
    cantidad: int = Field(gt=0)
    monto_unitario: Decimal
    fecha: date
    # Instante en que el cliente pidio las sugerencias (Seccion 6.4: la
    # medicion "codificacion_total" cuenta desde ahi, no desde que llega
    # esta solicitud) -- HTTP es sin estado, asi que quien confirma debe
    # devolver el instante que le llego en la respuesta de
    # GET /cpms/sugerencias.
    inicio_sugerencia: datetime


class UltimoPrecioRespuesta(BaseModel):
    monto_unitario: Decimal | None


class RespuestaProcedimientoConfirmado(BaseModel):
    procedimiento_id: int


class VersionCpmsRespuesta(BaseModel):
    id: int
    etiqueta: str
    conteo: int
    archivos_origen: list[dict[str, str]]
    creado_en: datetime

    @staticmethod
    def desde_valor(valor: VersionCpms) -> VersionCpmsRespuesta:
        return VersionCpmsRespuesta(**campos(valor))


class SolicitudCargarCatalogoCpms(BaseModel):
    etiqueta: str | None = None


class RespuestaCatalogoCpmsCargado(BaseModel):
    version_id: int
    etiqueta: str
    conteo: int
