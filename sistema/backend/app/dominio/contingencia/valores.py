"""Modo de contingencia (RF-23, AD-13, C-18; CU-01 y CU-03, flujos
alternativos): ante la indisponibilidad de una plataforma externa, el
analista registra manualmente el resultado de la operacion, con su
sustento obligatorio; el registro queda marcado como manual en el almacen
de eventos y en el panel gerencial, y el jefe de cuentas medicas lo revisa
despues.

"Indisponibilidad" se toma de lo que el sistema ya sabe, no de lo que el
usuario declara: la ultima solicitud de esa operacion agoto sus reintentos
(trabajo AGOTADO, RNF-07). Es lo que dice CU-01: "agotados los reintentos,
alerta y habilita el registro manual del resultado en modo de
contingencia".

El estado de la revision no vive en una tabla mutable: se deriva de los
eventos (un registro sin evento de revision posterior esta pendiente)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

TIPO_EVENTO_COBERTURA_CONTINGENCIA = "CONTINGENCIA_COBERTURA_REGISTRADA"
TIPO_EVENTO_VALIDACION_CONTINGENCIA = "CONTINGENCIA_VALIDACION_REGISTRADA"
TIPO_EVENTO_REVISION_CONTINGENCIA = "CONTINGENCIA_REVISADA"

# Componente ejecutor de una acreditacion registrada a mano (RF-02: "la
# identidad del componente que la ejecuto").
COMPONENTE_REGISTRO_MANUAL = "registro_manual_contingencia"

# C-18: "cada resultado registrado en modo de contingencia exige adjuntar
# su sustento". Un minimo de caracteres evita un sustento vacio de hecho
# ("-", "ok"); el valor no figura en la tesis, es supuesto de esta fase.
LONGITUD_MINIMA_SUSTENTO = 10


class TipoOperacion(StrEnum):
    COBERTURA = "COBERTURA"  # CU-01, ACREDITA SALUD no disponible
    VALIDACION = "VALIDACION"  # CU-03, validador TEDEF Web no disponible


class EstadoRevision(StrEnum):
    PENDIENTE = "PENDIENTE"
    CONFORME = "CONFORME"
    NO_CONFORME = "NO_CONFORME"


class ResultadoValidacionManual(StrEnum):
    VALIDADO = "VALIDADO"
    OBSERVADO = "OBSERVADO"


@dataclass(frozen=True, slots=True)
class RegistroContingencia:
    evento_id: str
    tipo_operacion: TipoOperacion
    cuenta_medica_id: int | None
    identificacion_interna: str | None
    lote_id: int | None
    numero_lote: str | None
    resumen: str
    sustento: str
    registrado_por: str
    registrado_en: datetime
    estado_revision: EstadoRevision
    revisado_por: str | None = None
    revisado_en: datetime | None = None
    comentario_revision: str | None = None


@dataclass(frozen=True, slots=True)
class IdentidadLoteS01:
    """Lo que el nombre del `.S01` de un lote debe llevar (Anexo 3,
    infraestructura/tedef/nombrado.py): RUC e IPRESS propios, IAFAS, numero
    de lote y periodo."""

    ruc: str
    codigo_ipress: str
    codigo_iafas: str
    numero_lote: str
    periodo: str


@dataclass(frozen=True, slots=True)
class ResumenTrabajo:
    """La ultima solicitud de una operacion automatizada (de la cola)."""

    estado: str
    error: str | None
    intentos: int
    creado_en: datetime
    actualizado_en: datetime


class ResultadoConsulta(StrEnum):
    EN_CURSO = "EN_CURSO"
    REQUIERE_SESION = "REQUIERE_SESION"
    # La plataforma respondio que no hay resultado (asegurado no encontrado):
    # no se reintenta ni habilita la contingencia.
    SIN_RESULTADO = "SIN_RESULTADO"
    # La plataforma no respondio tras los reintentos: habilita la contingencia.
    SIN_RESPUESTA = "SIN_RESPUESTA"
    COMPLETADA = "COMPLETADA"


# Antes del estado SIN_RESULTADO (2026-11-12), un asegurado no encontrado
# terminaba AGOTADO tras cinco reintentos con este texto del robot.
_TEXTO_LEGADO_NO_ENCONTRADO = "no encontro al asegurado"


def es_no_encontrado_legado(error: str | None) -> bool:
    return _TEXTO_LEGADO_NO_ENCONTRADO in (error or "").lower()


def clasificar_consulta(resumen: ResumenTrabajo) -> ResultadoConsulta:
    if resumen.estado == "SIN_RESULTADO":
        return ResultadoConsulta.SIN_RESULTADO
    if resumen.estado == "AGOTADO":
        legado = es_no_encontrado_legado(resumen.error)
        return ResultadoConsulta.SIN_RESULTADO if legado else ResultadoConsulta.SIN_RESPUESTA
    if resumen.estado == "REQUIERE_SESION":
        return ResultadoConsulta.REQUIERE_SESION
    if resumen.estado == "COMPLETADO":
        return ResultadoConsulta.COMPLETADA
    return ResultadoConsulta.EN_CURSO


@dataclass(frozen=True, slots=True)
class UltimaConsultaCobertura:
    """Como termino la ultima consulta de ACREDITA SALUD de una cuenta, con
    el mensaje para el analista (nunca el texto interno del robot)."""

    resultado: ResultadoConsulta
    intentos: int
    solicitada_en: datetime
    actualizada_en: datetime
    mensaje: str | None
