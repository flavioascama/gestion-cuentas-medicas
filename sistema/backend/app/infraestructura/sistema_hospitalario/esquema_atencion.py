"""Estructura JSON de la atencion del sistema hospitalario (contrato fijo,
2026-11-19). La usan el adaptador HTTP y la importacion por archivo, que
recibe la misma estructura. Aqui solo se exigen los tipos; las reglas de
negocio (montos positivos, fechas coherentes, catalogos) son del caso de
uso, para que las dos vias respondan igual."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.dominio.integracion.atencion_hospitalaria import (
    AtencionHospitalaria,
    CopagoAtencion,
    HospitalizacionAtencion,
    PacienteAtencion,
    ProcedimientoAtencion,
    ProductoAtencion,
    ProfesionalAtencion,
    ResumenAtencionHospitalaria,
)

_IGNORAR_EXTRAS = ConfigDict(extra="ignore")


class PacienteJson(BaseModel):
    model_config = _IGNORAR_EXTRAS
    tipo_documento: str = Field(min_length=1, max_length=1)
    numero_documento: str = Field(min_length=1, max_length=15)
    nombres: str = Field(min_length=1, max_length=150)
    apellidos: str = Field(min_length=1, max_length=150)

    def a_valor(self) -> PacienteAtencion:
        return PacienteAtencion(**self.model_dump())


class ProfesionalJson(BaseModel):
    model_config = _IGNORAR_EXTRAS
    numero_colegiatura: str = Field(max_length=20)
    nombres: str = Field(min_length=1, max_length=200)


class HospitalizacionJson(BaseModel):
    model_config = _IGNORAR_EXTRAS
    fecha_ingreso: date | None = None
    fecha_alta: date | None = None


class ProcedimientoJson(BaseModel):
    model_config = _IGNORAR_EXTRAS
    descripcion: str = Field(max_length=500)
    area: str = Field(max_length=20)
    cantidad: int
    monto_unitario: Decimal
    fecha: date


class ProductoJson(BaseModel):
    model_config = _IGNORAR_EXTRAS
    codigo_producto: str = Field(min_length=1, max_length=13)
    cantidad: Decimal
    tipo_unidad_dispensacion: str = Field(max_length=1)
    monto_unitario: Decimal
    fecha_dispensacion: date


class CopagoJson(BaseModel):
    model_config = _IGNORAR_EXTRAS
    monto: Decimal
    referencia: str = Field(max_length=60)
    fecha: date


class ResumenAtencionJson(BaseModel):
    model_config = _IGNORAR_EXTRAS
    atencion_id: str = Field(min_length=1, max_length=40)
    tipo_atencion: str
    fecha_prestacion: date
    paciente: PacienteJson
    iafas_codigo: str

    def a_valor(self) -> ResumenAtencionHospitalaria:
        return ResumenAtencionHospitalaria(
            atencion_id=self.atencion_id,
            tipo_atencion=self.tipo_atencion,
            fecha_prestacion=self.fecha_prestacion,
            paciente=self.paciente.a_valor(),
            iafas_codigo=self.iafas_codigo,
        )


class AtencionJson(BaseModel):
    model_config = _IGNORAR_EXTRAS
    atencion_id: str = Field(min_length=1, max_length=40)
    tipo_atencion: str = Field(max_length=20)
    fecha_prestacion: date
    hora_prestacion: time
    numero_historia_clinica: str = Field(max_length=20)
    paciente: PacienteJson
    iafas_codigo: str = Field(max_length=5)
    profesional: ProfesionalJson
    diagnostico_principal_cie10: str = Field(max_length=5)
    diagnosticos_secundarios_cie10: list[str] = Field(default_factory=list)
    hospitalizacion: HospitalizacionJson | None = None
    procedimientos: list[ProcedimientoJson] = Field(default_factory=list)
    farmacia: list[ProductoJson] = Field(default_factory=list)
    copago_cobrado: CopagoJson | None = None

    def a_valor(self) -> AtencionHospitalaria:
        hospitalizacion = self.hospitalizacion
        return AtencionHospitalaria(
            atencion_id=self.atencion_id.strip(),
            tipo_atencion=self.tipo_atencion,
            fecha_prestacion=self.fecha_prestacion,
            hora_prestacion=self.hora_prestacion,
            numero_historia_clinica=self.numero_historia_clinica,
            paciente=self.paciente.a_valor(),
            iafas_codigo=self.iafas_codigo,
            profesional=ProfesionalAtencion(**self.profesional.model_dump()),
            diagnostico_principal_cie10=self.diagnostico_principal_cie10.strip(),
            diagnosticos_secundarios_cie10=tuple(
                d.strip() for d in self.diagnosticos_secundarios_cie10 if d.strip()
            ),
            hospitalizacion=(
                HospitalizacionAtencion(**hospitalizacion.model_dump()) if hospitalizacion else None
            ),
            procedimientos=tuple(
                ProcedimientoAtencion(**p.model_dump()) for p in self.procedimientos
            ),
            farmacia=tuple(ProductoAtencion(**p.model_dump()) for p in self.farmacia),
            copago_cobrado=(
                CopagoAtencion(**self.copago_cobrado.model_dump()) if self.copago_cobrado else None
            ),
        )
