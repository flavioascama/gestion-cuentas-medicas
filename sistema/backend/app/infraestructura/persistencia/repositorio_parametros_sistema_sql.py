"""Valor vigente de los parametros del sistema y adaptador de
RepositorioParametrosSistema (CU-18)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.configuracion import obtener_configuracion
from app.dominio.plazos.parametros_sistema import (
    CLAVES_PARAMETROS_SISTEMA,
    RepositorioParametrosSistema,
)
from app.infraestructura.persistencia.modelos_parametros_sistema import ParametroSistemaModelo


async def valor_vigente(sesion: AsyncSession, clave: str) -> str:
    """El valor que fijo el administrador o, si no hay, el de la configuracion."""
    fila = await sesion.get(ParametroSistemaModelo, clave)
    if fila is not None:
        return fila.valor
    # Cada clave es el alias de su campo en Configuracion, en mayusculas.
    return str(getattr(obtener_configuracion(), clave.lower()))


class RepositorioParametrosSistemaSql(RepositorioParametrosSistema):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def vigentes(self) -> dict[str, str]:
        return {
            clave: await valor_vigente(self._sesion, clave) for clave in CLAVES_PARAMETROS_SISTEMA
        }

    async def guardar(self, clave: str, valor: str, actor: str) -> None:
        fila = await self._sesion.get(ParametroSistemaModelo, clave)
        if fila is None:
            self._sesion.add(
                ParametroSistemaModelo(clave=clave, valor=valor, actualizado_por=actor)
            )
        else:
            fila.valor = valor
            fila.actualizado_por = actor
        await self._sesion.flush()
