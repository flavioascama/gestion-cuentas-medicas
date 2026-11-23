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
    RegistrarRemisionRespuesta,
    RemisionRespuesta,
)
from app.dominio.comunicaciones.correos import (
    CorreoRecibido,
    RegistrarCorreoIafas,
    comunicacion_autorizada,
)
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.comunicaciones.fabrica import construir_procesar_comunicacion
from app.infraestructura.comunicaciones.fuentes import FuenteCorreoImap, FuentePortalIafas
from app.infraestructura.persistencia.adjunto_respuesta_sql import obtener_adjunto
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_comunicaciones_sql import (
    RepositorioComunicacionesSql,
)
from app.infraestructura.persistencia.repositorio_correos_sql import RepositorioCorreosSql
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


async def _leer_correo(fuentes: FuentesComunicaciones) -> list[tuple[str, CorreoRecibido]]:
    if fuentes.correo is None:
        return []
    return await asyncio.to_thread(fuentes.correo.leer_no_leidos)


async def _registrar_correos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    correos: list[CorreoRecibido],
    resultados: Counter[str],
) -> None:
    """Deja en el sistema cada correo leido, con su estado: procesado, si
    su comunicacion se aplico a una cuenta, o por revisar."""
    for correo in correos:
        async with fabrica_sesiones() as sesion:
            estado = await RegistrarCorreoIafas(
                RepositorioCorreosSql(sesion), RepositorioComunicacionesSql(sesion), RelojSistema()
            ).ejecutar(correo)
        if estado is not None:
            resultados[f"CORREO_{estado.value}"] += 1


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


async def _leer_antes_respuesta_de_lotes(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    documentos: set[str],
) -> None:
    """Si la IAFAS ya comunica sobre un comprobante cuyo lote sigue
    remitido, primero se lee la respuesta de ese lote: sin eso la cuenta
    aun no esta en auditoria y la comunicacion no se podria aplicar."""
    from trabajador.manejadores import (  # noqa: PLC0415 - evita el ciclo de importacion
        TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS,
        _procesar_monitorear_respuesta,
    )

    if not documentos:
        return
    async with fabrica_sesiones() as sesion:
        adelantados = await RepositorioComunicacionesSql(sesion).adelantar_respuesta_de_lotes(
            documentos
        )
    for _ in range(adelantados):
        async with fabrica_sesiones() as sesion:
            trabajo = await RepositorioTrabajosSql(sesion).tomar_siguiente(
                (TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS,)
            )
        if trabajo is None:
            return
        await _procesar_monitorear_respuesta(fabrica_sesiones, adaptadores, trabajo)


async def procesar_monitorear_comunicaciones(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    """Primero el correo (si una comunicacion llego por los dos canales,
    queda registrada como recibida por correo), despues el portal. Se
    aplican en el orden en que la IAFAS las emitio; cada una en su propia
    transaccion. Del correo solo se aplica sola la comunicacion cuyo
    remitente esta registrado para la IAFAS que la emite; los demas correos
    quedan por revisar. Todos se registran y, al final, se marcan como
    leidos."""

    fuentes = adaptadores.comunicaciones
    leidos = await _leer_correo(fuentes)
    correos = [correo for _, correo in leidos]
    async with fabrica_sesiones() as sesion:
        remitentes = await RepositorioCorreosSql(sesion).remitentes_por_iafas()
    pendientes = {
        correo.comunicacion.codigo: correo.comunicacion
        for correo in correos
        if correo.comunicacion is not None and comunicacion_autorizada(correo, remitentes)
    }
    for codigo in await _codigos_nuevos_del_portal(
        fabrica_sesiones, fuentes.portal, set(pendientes)
    ):
        pendientes[codigo] = await fuentes.portal.obtener(codigo)
    await _leer_antes_respuesta_de_lotes(
        fabrica_sesiones, adaptadores, {c.documento for c in pendientes.values()}
    )

    resultados: Counter[str] = Counter()
    for codigo in sorted(pendientes):
        async with fabrica_sesiones() as sesion:
            resultado = await construir_procesar_comunicacion(sesion).ejecutar(pendientes[codigo])
        resultados[resultado.value] += 1
    await _registrar_correos(fabrica_sesiones, correos, resultados)

    if fuentes.correo is not None and leidos:
        await asyncio.to_thread(fuentes.correo.marcar_leidos, [uid for uid, _ in leidos])
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
            adjunto = await obtener_adjunto(sesion, carga["observacion_id"])
            await adaptadores.comunicaciones.portal.responder(
                carga["codigo"],
                carga["codigo_ipress"],
                carga["respuesta"],
                carga,
                None if adjunto is None else (adjunto.nombre, adjunto.contenido),
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
