"""Robot de comunicaciones de la IAFAS (2026-11-13): hace lo que la persona
de cuentas medicas hacia a mano -- revisar la bandeja de correo y el portal
de la aseguradora, y registrar en el sistema la conformidad, la glosa, la
liquidacion y el aviso de pago que encuentre -- y entrega en el portal la
respuesta que la persona responsable elaboro para una observacion.

Separado de manejadores.py para no superar el limite de 400 lineas por
archivo (GUIA_ESTILO_CODIGO.md, Seccion 3)."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog
from app.dominio.comunicaciones.casos_uso import (
    ComunicacionIafas,
    RegistrarRemisionRespuesta,
    RemisionRespuesta,
)
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.comunicaciones.fabrica import construir_procesar_comunicacion
from app.infraestructura.comunicaciones.fuentes import FuenteCorreoImap, FuentePortalIafas
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_comunicaciones_sql import (
    RepositorioComunicacionesSql,
)
from app.infraestructura.reloj import RelojSistema
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

if TYPE_CHECKING:
    from app.dominio.puertos_comunes import TrabajoPendiente

    from trabajador.manejadores import Adaptadores

registro = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FuentesComunicaciones:
    portal: FuentePortalIafas
    correo: FuenteCorreoImap | None


async def _leer_correo(fuentes: FuentesComunicaciones) -> tuple[list[str], list[ComunicacionIafas]]:
    if fuentes.correo is None:
        return [], []
    leidos = await asyncio.to_thread(fuentes.correo.leer_no_leidos)
    return [uid for uid, _ in leidos], [comunicacion for _, comunicacion in leidos]


async def _codigos_nuevos_del_portal(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    portal: FuentePortalIafas,
    ya_leidos: set[str],
) -> list[str]:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioComunicacionesSql(sesion)
        nuevos = []
        for codigo_ipress in await repositorio.codigos_ipress():
            for codigo in await portal.codigos(codigo_ipress):
                if codigo not in ya_leidos and not await repositorio.ya_registrada(codigo):
                    nuevos.append(codigo)
    return nuevos


async def procesar_monitorear_comunicaciones(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    """Primero el correo (si una comunicacion llego por los dos canales,
    queda registrada como recibida por correo), despues el portal. Se
    aplican en el orden en que la IAFAS las emitio; cada una en su propia
    transaccion. Los correos se marcan como leidos al final, cuando todas
    quedaron registradas."""

    fuentes = adaptadores.comunicaciones
    uids, del_correo = await _leer_correo(fuentes)
    pendientes = {comunicacion.codigo: comunicacion for comunicacion in del_correo}
    for codigo in await _codigos_nuevos_del_portal(
        fabrica_sesiones, fuentes.portal, set(pendientes)
    ):
        pendientes[codigo] = await fuentes.portal.obtener(codigo)

    resultados: Counter[str] = Counter()
    for codigo in sorted(pendientes):
        async with fabrica_sesiones() as sesion:
            resultado = await construir_procesar_comunicacion(sesion).ejecutar(pendientes[codigo])
        resultados[resultado.value] += 1

    if fuentes.correo is not None and uids:
        await asyncio.to_thread(fuentes.correo.marcar_leidos, uids)
    async with fabrica_sesiones() as sesion:
        await RepositorioTrabajosSql(sesion).marcar_completado(trabajo.id)
    registro.info("comunicaciones_iafas_revisadas", trabajo_id=trabajo.id, **resultados)


async def procesar_enviar_respuesta_iafas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    carga = trabajo.carga_util
    async with fabrica_sesiones() as sesion:
        caso_uso = RegistrarRemisionRespuesta(
            RepositorioComunicacionesSql(sesion), RegistroEventosSql(sesion), RelojSistema()
        )
        if not await caso_uso.ya_remitida(carga["codigo"]):
            await adaptadores.comunicaciones.portal.responder(
                carga["codigo"], carga["codigo_ipress"], carga["respuesta"], carga.get("sustento")
            )
            await caso_uso.ejecutar(
                RemisionRespuesta(
                    codigo=carga["codigo"],
                    cuenta_medica_id=carga["cuenta_medica_id"],
                    observacion_id=carga["observacion_id"],
                    usuario_origen=carga.get("usuario_origen"),
                )
            )
    async with fabrica_sesiones() as sesion:
        await RepositorioTrabajosSql(sesion).marcar_completado(trabajo.id)
    registro.info("respuesta_iafas_remitida", trabajo_id=trabajo.id, codigo=carga["codigo"])
