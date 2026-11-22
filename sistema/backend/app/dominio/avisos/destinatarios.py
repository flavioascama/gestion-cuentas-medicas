"""Quien ve cada aviso (2026-11-19). Por regla, los roles del catalogo.
Los avisos de una observacion (reasignada, proxima a vencer, vencida y la
entrega de su respuesta que agoto sus intentos) siguen a la persona: si la
observacion tiene una persona asignada, los ve esa persona y la jefatura
(la tesis: el plazo se avisa "al responsable y a la jefatura" y la
reasignacion "al nuevo responsable"); sin persona asignada, el reparto por
rol de siempre. La falla de la entrega la sigue viendo el administrador
(RNF-20)."""

from __future__ import annotations

from app.dominio.acceso.entidades import NombreRol
from app.dominio.avisos.valores import (
    CATALOGO_AVISOS,
    TIPO_AVISO_TRABAJO_AGOTADO,
    TIPOS_AVISO_ANULACION,
    EventoAviso,
    tipos_para_roles,
)

TIPOS_AVISO_OBSERVACION = frozenset(
    {
        "OBSERVACION_REASIGNADA",
        "OBSERVACION_PLAZO_PROXIMO_A_VENCER",
        "OBSERVACION_PLAZO_VENCIDO_ESCALADO",
    }
)
TRABAJO_ENTREGA_RESPUESTA = "ENVIAR_RESPUESTA_IAFAS"
_ROLES_PERSONALES = frozenset({NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE})


def es_entrega_agotada(evento: EventoAviso) -> bool:
    return (
        evento.tipo_evento == TIPO_AVISO_TRABAJO_AGOTADO
        and evento.datos.get("tipo_trabajo") == TRABAJO_ENTREGA_RESPUESTA
        and evento.datos.get("observacion_id") is not None
    )


def es_aviso_de_observacion(evento: EventoAviso) -> bool:
    return evento.tipo_evento in TIPOS_AVISO_OBSERVACION or es_entrega_agotada(evento)


def tipos_a_consultar(roles: frozenset[NombreRol]) -> list[str]:
    """Los del rol, mas los de observacion para quien puede ser responsable
    o es jefe: el filtro fino lo hace `es_destinatario`."""
    tipos = set(tipos_para_roles(roles))
    if roles & _ROLES_PERSONALES:
        tipos |= TIPOS_AVISO_OBSERVACION | {TIPO_AVISO_TRABAJO_AGOTADO}
    return sorted(tipos)


def _por_rol(evento: EventoAviso, roles: frozenset[NombreRol]) -> bool:
    return bool(CATALOGO_AVISOS[evento.tipo_evento].roles & roles)


def _entrega_por_rol(evento: EventoAviso, roles: frozenset[NombreRol]) -> bool:
    responsable = evento.responsable_rol
    return _por_rol(evento, roles) or (responsable is not None and responsable in roles)


def es_destinatario(
    evento: EventoAviso,
    roles: frozenset[NombreRol],
    usuario_id: int | None,
    nombre_usuario: str | None = None,
) -> bool:
    if evento.tipo_evento in TIPOS_AVISO_ANULACION:
        # Solo quien pidio la anulacion.
        solicitante = evento.datos.get("solicitado_por")
        return solicitante is not None and solicitante == nombre_usuario
    if not es_aviso_de_observacion(evento):
        return _por_rol(evento, roles)
    entrega = es_entrega_agotada(evento)
    if entrega and roles & {NombreRol.JEFE, NombreRol.ADMINISTRADOR}:
        return True
    asignado = evento.responsable_usuario_id
    if asignado is None:
        return _entrega_por_rol(evento, roles) if entrega else _por_rol(evento, roles)
    return asignado == usuario_id or NombreRol.JEFE in roles
