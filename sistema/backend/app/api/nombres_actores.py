"""Quien actuo, con el nombre de la persona en lugar de su usuario, para lo
que se muestra (el aviso de la anulacion, el historial y el expediente).

El evento guardado no cambia (su actor entra en la cadena de integridad):
solo la respuesta. Una sola consulta de usuarios por respuesta; si el
usuario no se encuentra queda tal cual, y los actores que no son personas
(el temporizador, la automatizacion) tampoco cambian."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.esquemas_trazabilidad import HistorialCuentaRespuesta, HistorialLoteRespuesta
from app.dominio.avisos.valores import Aviso
from app.infraestructura.persistencia.modelos_acceso import UsuarioModelo


async def _nombres_de_personas(
    sesion: AsyncSession, actores: Iterable[str | None]
) -> dict[str, str]:
    pedidos = {actor for actor in actores if actor}
    if not pedidos:
        return {}
    filas = await sesion.execute(
        sa.select(UsuarioModelo.nombre_usuario, UsuarioModelo.nombres).where(
            UsuarioModelo.nombre_usuario.in_(pedidos)
        )
    )
    return {usuario: nombres for usuario, nombres in filas.tuples() if nombres.strip()}


async def con_nombres_en_historial(
    sesion: AsyncSession, historial: HistorialCuentaRespuesta | HistorialLoteRespuesta
) -> None:
    nombres = await _nombres_de_personas(sesion, (e.actor for e in historial.eventos))
    for evento in historial.eventos:
        evento.actor = nombres.get(evento.actor, evento.actor)


async def con_nombres_en_filas(
    sesion: AsyncSession, filas: Sequence[BaseModel], campos: Mapping[str, str]
) -> None:
    """Para las bandejas (anulaciones, contingencias, actividad del robot):
    cada campo de origen con un usuario deja el nombre en su campo destino."""
    nombres = await _nombres_de_personas(
        sesion, (getattr(fila, origen) for fila in filas for origen in campos)
    )
    for fila in filas:
        for origen, destino in campos.items():
            usuario = getattr(fila, origen)
            setattr(fila, destino, nombres.get(usuario, usuario) if usuario else usuario)


async def con_nombres_en_avisos(sesion: AsyncSession, avisos: list[Aviso]) -> list[Aviso]:
    nombres = await _nombres_de_personas(sesion, (a.actor for a in avisos))
    return [dataclasses.replace(a, actor=nombres.get(a.actor or "", a.actor)) for a in avisos]
