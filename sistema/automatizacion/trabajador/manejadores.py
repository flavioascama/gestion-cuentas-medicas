"""Manejadores por tipo de trabajo y manejo de errores del trabajador
(AD-02). Separado de principal.py (que se queda con el bucle y el
arranque) para no superar el limite de 400 lineas por archivo
(GUIA_ESTILO_CODIGO.md, Seccion 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from app.dominio.acreditacion.casos_uso import TIPO_TRABAJO_CONSULTAR_COBERTURA, VerificarCobertura
from app.dominio.acreditacion.puertos import AcreditacionWeb
from app.dominio.comunicaciones.casos_uso import (
    TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS,
    TIPO_TRABAJO_MONITOREAR_COMUNICACIONES,
)
from app.dominio.integracion.casos_uso import (
    TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS,
    MonitorearRespuestaIafas,
)
from app.dominio.integracion.casos_uso_validacion import (
    TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR,
    TIPO_TRABAJO_ENVIAR_LOTE_SUSALUD,
    EnviarLoteSusalud,
    LoteEnvioSusalud,
    RegistrarArchivoTransmision,
    RegistrarResultadoValidador,
)
from app.dominio.integracion.puertos import ConsultorRespuestaReceptor
from app.dominio.integracion.puertos_validacion import ValidadorTedefWeb
from app.dominio.integracion.vigencia_lote import ErrorLoteDesactualizado
from app.dominio.plataformas.casos_uso import (
    TIPO_TRABAJO_INICIAR_SESION_PLATAFORMA,
    IniciarSesionPlataforma,
)
from app.dominio.plataformas.puertos import AsistenteSesionPlataforma, ErrorSesionFallida
from app.dominio.puertos_comunes import Observabilidad, TrabajoPendiente
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_acreditacion_sql import (
    RepositorioAcreditacionSql,
)
from app.infraestructura.persistencia.repositorio_monitoreo_respuesta_sql import (
    RepositorioMonitoreoRespuestaSql,
)
from app.infraestructura.persistencia.repositorio_sesion_plataforma_sql import (
    RepositorioSesionPlataformaSql,
)
from app.infraestructura.persistencia.repositorio_validacion_oficial_sql import (
    RepositorioValidacionOficialSql,
)
from app.infraestructura.reloj import RelojSistema
from app.infraestructura.tedef.cargar_lote_en_validador import (
    CargarLoteEnValidador,
    DependenciasCargaValidador,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trabajador.configuracion import configuracion
from trabajador.manejadores_comunicaciones import (
    FuentesComunicaciones,
    procesar_enviar_respuesta_iafas,
    procesar_monitorear_comunicaciones,
)
from trabajador.soporte.errores import ErrorSesionNoDisponible, ErrorSinResultado
from trabajador.soporte.pasos import RegistradorPasos

registro = structlog.get_logger(__name__)

# Seccion 8.4, punto 6: que tipos de trabajo dependen de cada plataforma,
# para reactivar los que quedaron en REQUIERE_SESION cuando esa sesion se
# activa. Es una decision de orquestacion (que robot usa que portal), no
# una regla del dominio de sesiones -- por eso vive aqui y no en
# app/dominio/plataformas/.
_TIPOS_TRABAJO_POR_PLATAFORMA = {
    "acredita_salud": (TIPO_TRABAJO_CONSULTAR_COBERTURA,),
    "tedef_web": (TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR, TIPO_TRABAJO_ENVIAR_LOTE_SUSALUD),
}


@dataclass(frozen=True, slots=True)
class Adaptadores:
    acreditacion: AcreditacionWeb
    consultor_receptor: ConsultorRespuestaReceptor
    sesion_plataforma: AsistenteSesionPlataforma
    validador_tedef_web: ValidadorTedefWeb
    comunicaciones: FuentesComunicaciones
    # Navegacion visible del robot, si el administrador la activo.
    pasos: RegistradorPasos | None = None


async def _procesar_consultar_cobertura(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    cuenta_medica_id = trabajo.carga_util["cuenta_medica_id"]
    async with fabrica_sesiones() as sesion:
        caso_uso = VerificarCobertura(
            repositorio=RepositorioAcreditacionSql(sesion),
            adaptador=adaptadores.acreditacion,
            registro_eventos=RegistroEventosSql(sesion),
            registro_mediciones=RegistroMedicionesSql(sesion),
            reloj=RelojSistema(),
        )
        acreditacion_id = await caso_uso.ejecutar(
            trabajo_id=trabajo.id,
            cuenta_medica_id=cuenta_medica_id,
            actor="trabajador_automatizacion",
            # Control C-07 (Seccion 5.2.7): quien pidio la verificacion
            # desde la API, no quien la ejecuta (ver SolicitarVerificacionCobertura).
            usuario_origen=trabajo.carga_util.get("usuario_origen"),
        )
    registro.info(
        "trabajo_procesado",
        trabajo_id=trabajo.id,
        cuenta_medica_id=cuenta_medica_id,
        acreditacion_id=acreditacion_id,
    )
    async with fabrica_sesiones() as sesion:
        await RepositorioTrabajosSql(sesion).marcar_completado(trabajo.id)


async def _procesar_iniciar_sesion_plataforma(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    sesion_id = trabajo.carga_util["sesion_id"]
    plataforma = trabajo.carga_util["plataforma"]
    tipos_dependientes = _TIPOS_TRABAJO_POR_PLATAFORMA.get(plataforma, ())
    async with fabrica_sesiones() as sesion:
        caso_uso = IniciarSesionPlataforma(
            repositorio=RepositorioSesionPlataformaSql(sesion),
            repositorio_trabajos=RepositorioTrabajosSql(sesion),
            asistente=adaptadores.sesion_plataforma,
            observabilidad=Observabilidad(
                eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
            ),
            reloj=RelojSistema(),
        )
        await caso_uso.ejecutar(
            sesion_id=sesion_id,
            plataforma=plataforma,
            actor="trabajador_automatizacion",
            tipos_trabajo_dependientes=tipos_dependientes,
            usuario_origen=trabajo.carga_util.get("usuario_origen"),
        )
    registro.info(
        "trabajo_procesado", trabajo_id=trabajo.id, sesion_id=sesion_id, plataforma=plataforma
    )
    async with fabrica_sesiones() as sesion:
        await RepositorioTrabajosSql(sesion).marcar_completado(trabajo.id)


async def _procesar_monitorear_respuesta(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    """A diferencia de `_procesar_consultar_cobertura`, este manejador
    decide su propio estado final para `trabajo` (Seccion 8.3): puede
    terminar COMPLETADO (hubo respuesta), PENDIENTE otra vez con un nuevo
    `proximo_intento` (todavia no hay respuesta, sin que eso sea un
    error), o AGOTADO (se supero la ventana maxima de espera)."""

    lote_id = trabajo.carga_util["lote_id"]
    intervalo_reconsulta = timedelta(minutes=configuracion.intervalo_reconsulta_monitoreo_minutos)
    async with fabrica_sesiones() as sesion:
        caso_uso = MonitorearRespuestaIafas(
            repositorio=RepositorioMonitoreoRespuestaSql(sesion),
            consultor=adaptadores.consultor_receptor,
            observabilidad=Observabilidad(
                eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
            ),
            reloj=RelojSistema(),
            intervalo_reconsulta=intervalo_reconsulta,
        )
        resultado = await caso_uso.ejecutar(
            lote_id=lote_id,
            trabajo_creado_en=trabajo.creado_en,
            actor="trabajador_automatizacion",
            usuario_origen=trabajo.carga_util.get("usuario_origen"),
        )

    async with fabrica_sesiones() as sesion:
        repositorio_trabajos = RepositorioTrabajosSql(sesion)
        if resultado.resultado == "respondido":
            await repositorio_trabajos.marcar_completado(trabajo.id)
            registro.info("trabajo_procesado", trabajo_id=trabajo.id, lote_id=lote_id)
        elif resultado.resultado == "agotado":
            await repositorio_trabajos.marcar_agotado(
                trabajo.id, "Venció el plazo de espera y la IAFAS no respondió."
            )
            registro.warning("trabajo_agotado", trabajo_id=trabajo.id, lote_id=lote_id)
        else:  # "sin_respuesta"
            assert resultado.proximo_intento is not None
            await repositorio_trabajos.marcar_para_reintento(
                trabajo.id, "Aún no hay respuesta de la IAFAS.", resultado.proximo_intento
            )
            registro.info(
                "trabajo_reencolado",
                trabajo_id=trabajo.id,
                lote_id=lote_id,
                proximo_intento=resultado.proximo_intento.isoformat(),
            )


async def _procesar_cargar_lote_validador(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    lote_id = trabajo.carga_util["lote_id"]
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioValidacionOficialSql(sesion)
        observabilidad = Observabilidad(
            eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
        )
        caso_uso = CargarLoteEnValidador(
            DependenciasCargaValidador(
                repositorio=repositorio,
                validador=adaptadores.validador_tedef_web,
                registrar_resultado=RegistrarResultadoValidador(repositorio, observabilidad),
                registrar_archivo=RegistrarArchivoTransmision(repositorio, observabilidad),
                reloj=RelojSistema(),
                directorio_reportes=configuracion.ruta_reportes,
                directorio_artefactos=configuracion.ruta_artefactos_s01,
            )
        )
        await caso_uso.ejecutar(
            lote_id=lote_id,
            trabajo_id=trabajo.id,
            actor="trabajador_automatizacion",
            usuario_origen=trabajo.carga_util.get("usuario_origen"),
        )
    registro.info("trabajo_procesado", trabajo_id=trabajo.id, lote_id=lote_id)
    async with fabrica_sesiones() as sesion:
        await RepositorioTrabajosSql(sesion).marcar_completado(trabajo.id)


async def _procesar_enviar_lote_susalud(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    adaptadores: Adaptadores,
    trabajo: TrabajoPendiente,
) -> None:
    periodo = trabajo.carga_util["periodo"]
    lotes = tuple(
        LoteEnvioSusalud(lote_id=dato["lote_id"], numero=dato["numero"], periodo=dato["periodo"])
        for dato in trabajo.carga_util["lotes"]
    )
    async with fabrica_sesiones() as sesion:
        caso_uso = EnviarLoteSusalud(
            repositorio=RepositorioValidacionOficialSql(sesion),
            validador=adaptadores.validador_tedef_web,
            observabilidad=Observabilidad(
                eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
            ),
            reloj=RelojSistema(),
        )
        await caso_uso.ejecutar(
            lotes=lotes,
            periodo=periodo,
            actor="trabajador_automatizacion",
            usuario_origen=trabajo.carga_util.get("usuario_origen"),
        )
    registro.info("trabajo_procesado", trabajo_id=trabajo.id, periodo=periodo, lotes=len(lotes))
    async with fabrica_sesiones() as sesion:
        await RepositorioTrabajosSql(sesion).marcar_completado(trabajo.id)


# La plataforma cuya sesion asistida necesita cada trabajo del robot.
_PLATAFORMA_DEL_TRABAJO = {
    TIPO_TRABAJO_CONSULTAR_COBERTURA: "acredita_salud",
    TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR: "tedef_web",
    TIPO_TRABAJO_ENVIAR_LOTE_SUSALUD: "tedef_web",
}


async def manejar_error(
    fabrica_sesiones: async_sessionmaker[AsyncSession], trabajo: TrabajoPendiente, error: Exception
) -> None:
    """Seccion 8.1, punto 6: retroceso exponencial hasta el maximo
    configurado; el trabajo no se pierde (vuelve a PENDIENTE, no se
    borra). Solo para fallos genuinos (excepciones) -- distinto del
    reencolado sin error de `_procesar_monitorear_respuesta`.

    Seccion 8.4, punto 6: `ErrorSesionNoDisponible` es un caso aparte, no
    un fallo comun -- el trabajo pasa a REQUIERE_SESION, sin consumir
    intentos, hasta que una sesion asistida de esa plataforma se active.

    `ErrorSesionFallida` (Fase 20, bug encontrado al verificar contra el
    simulador real) es otro caso aparte, pero terminal: la lanza
    `IniciarSesionPlataforma` cuando el CAPTCHA se agoto o las
    credenciales de la plataforma son invalidas, y en ambos casos
    `sesion_plataforma` ya quedo FALLIDA (Seccion 8.4). Reintentar el
    MISMO trabajo con backoff exponencial no tiene ningun efecto util:
    vuelve a abrir Playwright, reingresa usuario/clave, y espera hasta
    tres rondas de `tiempo_limite_captcha_segundos` a un humano que no
    esta mirando ese reintento automatico -- bloqueando al trabajador
    (un solo proceso, un trabajo a la vez) por minutos, cada vez. Para
    reintentar de verdad, el usuario pulsa "Reiniciar" en la pantalla de
    Conexiones con plataformas (Seccion 12), que encola una sesion NUEVA
    (otro `sesion_id`), no reactiva esta."""

    if isinstance(error, ErrorSesionNoDisponible):
        async with fabrica_sesiones() as sesion:
            await RepositorioTrabajosSql(sesion).marcar_requiere_sesion(trabajo.id, str(error))
            # La plataforma ya no acepta la sesion guardada: deja de contar
            # como ACTIVA, para que se pueda pedir otra (2026-11-18).
            plataforma = _PLATAFORMA_DEL_TRABAJO.get(trabajo.tipo)
            if plataforma is not None:
                await RepositorioSesionPlataformaSql(sesion).expirar_activas(plataforma)
        registro.info("trabajo_requiere_sesion", trabajo_id=trabajo.id, motivo=str(error))
        return

    if isinstance(error, ErrorSinResultado):
        async with fabrica_sesiones() as sesion:
            await RepositorioTrabajosSql(sesion).marcar_sin_resultado(trabajo.id, str(error))
        registro.info("trabajo_sin_resultado", trabajo_id=trabajo.id, motivo=str(error))
        return

    # Reintentar no sirve: el lote cambio y se arma uno nuevo.
    if isinstance(error, (ErrorSesionFallida, ErrorLoteDesactualizado)):
        async with fabrica_sesiones() as sesion:
            await RepositorioTrabajosSql(sesion).marcar_agotado(trabajo.id, str(error))
        registro.warning("trabajo_agotado_sesion_fallida", trabajo_id=trabajo.id, error=str(error))
        return

    async with fabrica_sesiones() as sesion:
        repositorio_trabajos = RepositorioTrabajosSql(sesion)
        if trabajo.intentos + 1 >= configuracion.maximo_intentos:
            await repositorio_trabajos.marcar_agotado(trabajo.id, str(error))
            registro.error("trabajo_agotado", trabajo_id=trabajo.id, error=str(error))
        else:
            espera_segundos = configuracion.backoff_base_segundos * (2**trabajo.intentos)
            proximo_intento = datetime.now(UTC) + timedelta(seconds=espera_segundos)
            await repositorio_trabajos.marcar_para_reintento(
                trabajo.id, str(error), proximo_intento
            )
            registro.warning(
                "trabajo_reintentara",
                trabajo_id=trabajo.id,
                intentos=trabajo.intentos + 1,
                proximo_intento=proximo_intento.isoformat(),
                error=str(error),
            )


MANEJADORES = {
    TIPO_TRABAJO_CONSULTAR_COBERTURA: _procesar_consultar_cobertura,
    TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS: _procesar_monitorear_respuesta,
    TIPO_TRABAJO_INICIAR_SESION_PLATAFORMA: _procesar_iniciar_sesion_plataforma,
    TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR: _procesar_cargar_lote_validador,
    TIPO_TRABAJO_ENVIAR_LOTE_SUSALUD: _procesar_enviar_lote_susalud,
    TIPO_TRABAJO_MONITOREAR_COMUNICACIONES: procesar_monitorear_comunicaciones,
    TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS: procesar_enviar_respuesta_iafas,
}
