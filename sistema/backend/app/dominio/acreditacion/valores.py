"""DTOs del contexto de acreditacion (Seccion 6.1, 8.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ContextoCuentaAcreditacion:
    """Lo que el robot necesita para consultar la cobertura de una cuenta
    (Seccion 8.1, CU-01, punto 3): el documento del asegurado."""

    cuenta_medica_id: int
    tipo_documento_paciente: str
    numero_documento_paciente: str


@dataclass(frozen=True, slots=True)
class ResultadoAcreditacion:
    """Lo que el robot extrae del portal (Seccion 6.1: 'condicion de
    cobertura, codigo de autorizacion, vigencia, plan, copagos,
    preexistencias, instante, duracion en milisegundos, componente
    ejecutor, ruta de la evidencia')."""

    condicion_cobertura: str
    codigo_autorizacion: str
    tipo_documento_autorizacion: str
    codigo_asegurado: str
    tipo_afiliacion: str
    plan: str | None
    vigente_desde: date | None
    vigente_hasta: date | None
    tipo_copago: str | None
    monto_copago_fijo: Decimal | None
    porcentaje_coaseguro: int | None
    preexistencias: list[str] = field(default_factory=list)
    ruta_evidencia: str | None = None


# Tipos de documento del asegurado con nombre conocido (los mismos que
# ofrece el formulario de nueva cuenta); cualquier otro se nombra generico.
_NOMBRE_TIPO_DOCUMENTO = {"1": "DNI", "2": "carné de extranjería"}


def mensaje_asegurado_no_encontrado(tipo_documento: str, numero_documento: str) -> str:
    """Lo que ve el analista cuando ACREDITA SALUD no encuentra al
    asegurado, en el lenguaje de la clinica (2026-11-12: antes se mostraba
    el texto interno del robot, que nombraba al simulador)."""
    nombre = _NOMBRE_TIPO_DOCUMENTO.get(tipo_documento, "documento")
    return f"ACREDITA SALUD no encontró al asegurado con {nombre} {numero_documento}."
