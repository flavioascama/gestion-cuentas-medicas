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
    # La IAFAS registrada en la cuenta: el robot la compara con la que
    # responde ACREDITA SALUD.
    codigo_iafas: str = ""
    # Para decidir si la cobertura se puede volver a consultar.
    estado_cuenta: str = ""
    tiene_comprobante: bool = False


def admite_consulta(contexto: ContextoCuentaAcreditacion, ya_acreditada: bool) -> bool:
    """La primera consulta siempre; una nueva consulta solo mientras la
    cuenta siga REGISTRADA y sin comprobante (despues, la acreditacion ya
    sustento lo facturado y no se reemplaza). Las normas del proyecto no
    fijan un plazo de vigencia de la acreditacion, asi que no se impone."""
    if not ya_acreditada:
        return True
    return contexto.estado_cuenta == "REGISTRADA" and not contexto.tiene_comprobante


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


def es_acreditable(condicion: str) -> bool:
    """ACREDITA SALUD responde 'NO ACREDITABLE: <motivo>' cuando no cubre
    al asegurado; cualquier otra condicion (incluida la acreditable con
    restriccion) permite facturar."""
    return not condicion.lstrip().upper().startswith("NO ACREDITABLE")


_LONGITUD_CONDICION = 120  # acreditacion.condicion_cobertura


def condicion_segun_aseguradora(
    condicion: str, codigo_iafas_cuenta: str, codigo_iafas_respuesta: str, nombre_respuesta: str
) -> str:
    """Si ACREDITA SALUD devuelve al asegurado bajo una IAFAS distinta de la
    registrada en la cuenta, la acreditacion no sirve para facturar a la
    IAFAS de la cuenta: queda NO ACREDITABLE con el nombre de la otra."""
    if not codigo_iafas_cuenta or not codigo_iafas_respuesta:
        return condicion
    if codigo_iafas_respuesta.strip() == codigo_iafas_cuenta.strip():
        return condicion
    nombre = nombre_respuesta.strip() or codigo_iafas_respuesta.strip()
    texto = f"NO ACREDITABLE: el asegurado figura en otra aseguradora ({nombre})"
    return texto[:_LONGITUD_CONDICION]


# Tipos de documento del asegurado con nombre conocido (los mismos que
# ofrece el formulario de nueva cuenta); cualquier otro se nombra generico.
_NOMBRE_TIPO_DOCUMENTO = {"1": "DNI", "2": "carné de extranjería"}


def mensaje_asegurado_no_encontrado(tipo_documento: str, numero_documento: str) -> str:
    """Lo que ve el analista cuando ACREDITA SALUD no encuentra al
    asegurado, en el lenguaje de la clinica (2026-11-12: antes se mostraba
    el texto interno del robot, que nombraba al simulador)."""
    nombre = _NOMBRE_TIPO_DOCUMENTO.get(tipo_documento, "documento")
    return f"ACREDITA SALUD no encontró al asegurado con {nombre} {numero_documento}."
