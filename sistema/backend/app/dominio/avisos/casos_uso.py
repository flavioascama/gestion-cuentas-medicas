"""Bandeja de avisos (CU-08, CU-09, CU-11, CU-14): cada usuario ve los
avisos destinados a alguno de sus roles, uno por hito (el mas reciente,
con cuantas veces se repitio) y marcados como atendidos cuando ya se
actuo sobre ellos. Consulta de solo lectura."""

from __future__ import annotations

from app.dominio.acceso.entidades import NombreRol
from app.dominio.avisos.destinatarios import es_destinatario, tipos_a_consultar
from app.dominio.avisos.puertos import RepositorioAvisos
from app.dominio.avisos.valores import (
    CATALOGO_AVISOS,
    Aviso,
    EventoAviso,
    clave_agrupacion,
)

# Cuantos eventos se leen antes de agrupar: los repetidos de un mismo hito
# se colapsan en uno, asi que hace falta leer mas de los que se muestran.
_EVENTOS_A_AGRUPAR = 2000


def agrupar(eventos: list[EventoAviso]) -> list[tuple[EventoAviso, int]]:
    """Conserva el primero (el mas reciente: llegan ordenados) de cada
    hito y cuenta las repeticiones, sin alterar el orden."""
    primeros: dict[tuple[object, ...], EventoAviso] = {}
    cuentas: dict[tuple[object, ...], int] = {}
    for evento in eventos:
        clave = clave_agrupacion(evento)
        primeros.setdefault(clave, evento)
        cuentas[clave] = cuentas.get(clave, 0) + 1
    return [(evento, cuentas[clave]) for clave, evento in primeros.items()]


class ListarAvisos:
    def __init__(self, repositorio: RepositorioAvisos) -> None:
        self._repositorio = repositorio

    async def ejecutar(
        self, roles: frozenset[NombreRol], limite: int, usuario_id: int | None = None
    ) -> list[Aviso]:
        tipos = tipos_a_consultar(roles)
        if not tipos:
            return []
        eventos = await self._repositorio.listar(tipos, _EVENTOS_A_AGRUPAR)
        visibles = [e for e in eventos if es_destinatario(e, roles, usuario_id)]
        agrupados = agrupar(visibles)[:limite]
        evaluados = await self._repositorio.evaluar_atencion([evento for evento, _ in agrupados])
        return [
            Aviso(
                evento_id=evento.evento_id,
                tipo_evento=evento.tipo_evento,
                titulo=CATALOGO_AVISOS[evento.tipo_evento].titulo,
                severidad=CATALOGO_AVISOS[evento.tipo_evento].severidad.value,
                ocurrido_en=evento.ocurrido_en,
                datos=evento.datos,
                cuenta_medica_id=evento.cuenta_medica_id,
                identificacion_interna=evento.identificacion_interna,
                lote_id=evento.lote_id,
                numero_lote=evento.numero_lote,
                atendido=evento.atendido,
                repeticiones=repeticiones,
            )
            for evento, (_, repeticiones) in zip(evaluados, agrupados, strict=True)
        ]
