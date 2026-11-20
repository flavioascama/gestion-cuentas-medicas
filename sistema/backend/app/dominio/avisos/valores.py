"""Catalogo de avisos (CU-08, CU-09, CU-11, CU-14; RT-10, C-15): que
eventos del almacen son un aviso para una persona, para que roles y con
que severidad.

Los avisos ya se registraban como eventos desde la Fase 27 (control de
plazos) y la Fase 29 (ruptura de la cadena), pero ninguna pantalla los
mostraba: la verificacion de cumplimiento del 12 de noviembre los encontro
"registrados sin canal". Un aviso no es una entidad nueva ni un estado
mutable: es una lectura del almacen de eventos filtrada por tipo y rol.

Destinatarios segun la tesis: el aviso previo va al responsable de la
etapa (Tabla 61: analista o auditor para las observaciones, analista para
el reenvio y la auditoria, tesoreria para el pago) y el escalamiento,
ademas, al jefe de cuentas medicas (CU-11). La ruptura de la cadena va al
jefe y al administrador (RT-10, C-15)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.dominio.acceso.entidades import NombreRol


class Severidad(StrEnum):
    AVISO = "aviso"  # proximo a vencer
    ESCALAMIENTO = "escalamiento"  # plazo vencido, escalado al jefe
    CRITICO = "critico"  # rechazo de la IAFAS o integridad comprometida


@dataclass(frozen=True, slots=True)
class DefinicionAviso:
    titulo: str
    severidad: Severidad
    roles: frozenset[NombreRol]


TIPO_AVISO_TRABAJO_AGOTADO = "TRABAJO_AGOTADO"
TIPO_AVISO_CORREO_POR_REVISAR = "CORREO_IAFAS_POR_REVISAR"

_ANALISTA = NombreRol.ANALISTA
_AUDITOR = NombreRol.AUDITOR
_JEFE = NombreRol.JEFE
_TESORERIA = NombreRol.TESORERIA
_ADMINISTRADOR = NombreRol.ADMINISTRADOR

CATALOGO_AVISOS: dict[str, DefinicionAviso] = {
    "OBSERVACION_PLAZO_PROXIMO_A_VENCER": DefinicionAviso(
        "Observación por vencer", Severidad.AVISO, frozenset({_ANALISTA, _AUDITOR})
    ),
    "OBSERVACION_PLAZO_VENCIDO_ESCALADO": DefinicionAviso(
        "Observación vencida", Severidad.ESCALAMIENTO, frozenset({_ANALISTA, _AUDITOR, _JEFE})
    ),
    # CU-09: "notifica al nuevo responsable".
    "OBSERVACION_REASIGNADA": DefinicionAviso(
        "Observación reasignada", Severidad.AVISO, frozenset({_ANALISTA, _AUDITOR})
    ),
    "LOTE_RECHAZADO_PLAZO_PROXIMO_A_VENCER": DefinicionAviso(
        "Reenvío de cuenta rechazada por vencer", Severidad.AVISO, frozenset({_ANALISTA})
    ),
    "LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO": DefinicionAviso(
        "Reenvío de cuenta rechazada vencido", Severidad.ESCALAMIENTO, frozenset({_ANALISTA, _JEFE})
    ),
    "AUDITORIA_PLAZO_PROXIMO_A_VENCER": DefinicionAviso(
        "Resultado de auditoría por vencer", Severidad.AVISO, frozenset({_ANALISTA})
    ),
    "AUDITORIA_EXCEDIDA": DefinicionAviso(
        "Resultado de auditoría vencido", Severidad.ESCALAMIENTO, frozenset({_ANALISTA, _JEFE})
    ),
    "LIQUIDACION_PAGO_PROXIMO_A_VENCER": DefinicionAviso(
        "Pago de liquidación por vencer", Severidad.AVISO, frozenset({_TESORERIA})
    ),
    "LIQUIDACION_PAGO_VENCIDO_ESCALADO": DefinicionAviso(
        "Pago de liquidación vencido", Severidad.ESCALAMIENTO, frozenset({_TESORERIA, _JEFE})
    ),
    # RT-05 y RI-16: el envio a SUSALUD de los lotes del periodo.
    "SUSALUD_ENVIO_PROXIMO_A_VENCER": DefinicionAviso(
        "Envío a SUSALUD por vencer", Severidad.AVISO, frozenset({_ANALISTA})
    ),
    "SUSALUD_ENVIO_VENCIDO_ESCALADO": DefinicionAviso(
        "Envío a SUSALUD vencido", Severidad.ESCALAMIENTO, frozenset({_ANALISTA, _JEFE})
    ),
    "CARTA_GARANTIA_PROXIMA_A_VENCER": DefinicionAviso(
        "Vigencia de cobertura por vencer", Severidad.AVISO, frozenset({_ANALISTA})
    ),
    "LOTE_RECHAZADO": DefinicionAviso(
        "Lote rechazado por la IAFAS", Severidad.CRITICO, frozenset({_ANALISTA, _JEFE})
    ),
    # Una glosa, liquidacion o pago que llego por el portal o el correo de
    # la IAFAS y no se pudo registrar en la cuenta.
    "COMUNICACION_IAFAS_NO_APLICADA": DefinicionAviso(
        "Comunicación de la IAFAS no aplicada",
        Severidad.CRITICO,
        frozenset({_ANALISTA, _JEFE, _TESORERIA}),
    ),
    # Un correo de la IAFAS que el robot no pudo aplicar solo (2026-11-15):
    # sin el formato de la aseguradora, de un remitente no registrado o de
    # un comprobante desconocido. No es un evento del almacen sino un
    # correo en estado POR_REVISAR; deja de avisarse al vincularlo o
    # descartarlo.
    TIPO_AVISO_CORREO_POR_REVISAR: DefinicionAviso(
        "Correo de la IAFAS por revisar", Severidad.CRITICO, frozenset({_ANALISTA, _JEFE})
    ),
    # C-15 (2026-11-13): el acceso indebido tambien es una alerta para el
    # titular del banco de datos (el administrador y el jefe).
    "ACCESO_DENEGADO": DefinicionAviso(
        "Acceso no permitido", Severidad.AVISO, frozenset({_JEFE, _ADMINISTRADOR})
    ),
    "RUPTURA_CADENA_DETECTADA": DefinicionAviso(
        "Ruptura en la cadena de eventos", Severidad.CRITICO, frozenset({_JEFE, _ADMINISTRADOR})
    ),
    # C-18: cada registro en modo de contingencia queda a revision del jefe.
    "CONTINGENCIA_COBERTURA_REGISTRADA": DefinicionAviso(
        "Cobertura registrada en contingencia, por revisar", Severidad.AVISO, frozenset({_JEFE})
    ),
    "CONTINGENCIA_VALIDACION_REGISTRADA": DefinicionAviso(
        "Validación registrada en contingencia, por revisar", Severidad.AVISO, frozenset({_JEFE})
    ),
    # RNF-20: "ante una falla del proceso de automatizacion... alertar al
    # jefe de cuentas medicas y al administrador... y habilitar el modo de
    # contingencia". No es un evento del almacen sino un trabajo de la cola
    # que agoto sus reintentos (RNF-07); el analista lo recibe tambien,
    # porque es quien registra el resultado en contingencia (Tabla 46).
    TIPO_AVISO_TRABAJO_AGOTADO: DefinicionAviso(
        "Falla del proceso de automatización",
        Severidad.CRITICO,
        frozenset({_ANALISTA, _JEFE, _ADMINISTRADOR}),
    ),
}


def tipos_para_roles(roles: frozenset[NombreRol]) -> list[str]:
    return sorted(tipo for tipo, definicion in CATALOGO_AVISOS.items() if definicion.roles & roles)


# Un aviso previo y su escalamiento son dos momentos del mismo hito: la
# bandeja muestra el mas reciente de cada hito (de la cuenta, del lote o de
# la observacion) y cuantas veces se repitio, en vez de una fila por
# evento (rediseno del 2026-11-12: la bandeja repetia la misma cuenta).
_FAMILIAS = {
    "OBSERVACION_PLAZO_PROXIMO_A_VENCER": "observacion",
    "OBSERVACION_PLAZO_VENCIDO_ESCALADO": "observacion",
    "LOTE_RECHAZADO_PLAZO_PROXIMO_A_VENCER": "reenvio",
    "LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO": "reenvio",
    "AUDITORIA_PLAZO_PROXIMO_A_VENCER": "auditoria",
    "AUDITORIA_EXCEDIDA": "auditoria",
    "LIQUIDACION_PAGO_PROXIMO_A_VENCER": "pago",
    "LIQUIDACION_PAGO_VENCIDO_ESCALADO": "pago",
    "SUSALUD_ENVIO_PROXIMO_A_VENCER": "susalud",
    "SUSALUD_ENVIO_VENCIDO_ESCALADO": "susalud",
}

# Cada registro en contingencia se revisa por separado (C-18): no se agrupan.
# Tampoco los correos por revisar: cada uno lo resuelve una persona.
_TIPOS_SIN_AGRUPAR = frozenset(
    {
        "CONTINGENCIA_COBERTURA_REGISTRADA",
        "CONTINGENCIA_VALIDACION_REGISTRADA",
        TIPO_AVISO_CORREO_POR_REVISAR,
    }
)


def familia_de(tipo_evento: str) -> str:
    return _FAMILIAS.get(tipo_evento, tipo_evento)


@dataclass(frozen=True, slots=True)
class EventoAviso:
    """Lo que el repositorio lee de un evento que es aviso."""

    evento_id: str
    tipo_evento: str
    ocurrido_en: datetime
    datos: dict[str, Any]
    cuenta_medica_id: int | None
    identificacion_interna: str | None
    lote_id: int | None
    numero_lote: str | None
    # Si ya se actuo sobre lo que el aviso pedia (la cuenta cambio de
    # estado despues, la contingencia se reviso, el trabajo se completo
    # despues): lo decide el repositorio, que ve el resto del almacen.
    atendido: bool = False
    # De un aviso de observacion (2026-11-19): la persona asignada y el rol
    # responsable, que deciden quien lo ve (destinatarios.py).
    responsable_usuario_id: int | None = None
    responsable_rol: str | None = None


def clave_agrupacion(evento: EventoAviso) -> tuple[object, ...]:
    if evento.tipo_evento in _TIPOS_SIN_AGRUPAR:
        return (evento.evento_id,)
    # El envio a SUSALUD es por periodo (RI-16): un aviso por periodo, no
    # uno por cada lote del periodo.
    if familia_de(evento.tipo_evento) == "susalud":
        return ("susalud", evento.datos.get("periodo"))
    return (
        familia_de(evento.tipo_evento),
        evento.cuenta_medica_id,
        evento.lote_id,
        evento.datos.get("observacion_id"),
        evento.datos.get("tipo_trabajo"),
        evento.datos.get("plataforma"),
    )


@dataclass(frozen=True, slots=True)
class Aviso:
    evento_id: str
    tipo_evento: str
    titulo: str
    severidad: str
    ocurrido_en: datetime
    datos: dict[str, Any]
    cuenta_medica_id: int | None
    identificacion_interna: str | None
    lote_id: int | None
    numero_lote: str | None
    atendido: bool
    repeticiones: int
