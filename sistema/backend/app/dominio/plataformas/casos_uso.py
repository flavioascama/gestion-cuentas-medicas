"""Casos de uso de sesiones asistidas (Seccion 8.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.dominio.plataformas.puertos import (
    AsistenteSesionPlataforma,
    ErrorPlataformaInvalida,
    ErrorSesionFallida,
    ErrorSesionNoEncontrada,
    ErrorSesionPlataforma,
    RepositorioSesionPlataforma,
)
from app.dominio.plataformas.valores import PLATAFORMAS_VALIDAS, SesionPlataforma
from app.dominio.puertos_comunes import (
    Evento,
    MedicionPaso,
    Observabilidad,
    Reloj,
    RepositorioTrabajos,
)

TIPO_TRABAJO_INICIAR_SESION_PLATAFORMA = "INICIAR_SESION_PLATAFORMA"


class SolicitarSesionPlataforma:
    """Seccion 8.4, punto 1: 'el usuario pulsa Iniciar sesion para una
    plataforma. La API crea la fila con estado SOLICITADA y encola
    INICIAR_SESION_PLATAFORMA'. Idempotente si ya hay una sesion ACTIVA
    (mismo criterio que `VerificarCobertura`: un reintento no duplica)."""

    def __init__(
        self,
        repositorio: RepositorioSesionPlataforma,
        repositorio_trabajos: RepositorioTrabajos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._repositorio_trabajos = repositorio_trabajos
        self._reloj = reloj

    async def ejecutar(self, plataforma: str, solicitada_por: str) -> int:
        if plataforma not in PLATAFORMAS_VALIDAS:
            raise ErrorPlataformaInvalida(f"Plataforma invalida: {plataforma!r}")

        activa = await self._repositorio.obtener_activa(plataforma)
        if activa is not None:
            return activa.id

        sesion_id = await self._repositorio.crear_solicitud(plataforma, solicitada_por)
        await self._repositorio_trabajos.encolar(
            tipo=TIPO_TRABAJO_INICIAR_SESION_PLATAFORMA,
            # Control C-07 (Seccion 5.2.7): `sesion_plataforma.solicitada_por`
            # ya deja esto en la fila de la sesion; se repite aqui para que
            # el evento SESION_PLATAFORMA_* del robot tambien lo lleve, sin
            # que verlo exija un cruce con esa otra tabla.
            carga_util={
                "sesion_id": sesion_id,
                "plataforma": plataforma,
                "usuario_origen": solicitada_por,
            },
            proximo_intento=self._reloj.ahora(),
        )
        return sesion_id


class ResponderCaptcha:
    """Seccion 8.4, punto 3: 'la aplicacion web consulta el estado,
    muestra la imagen en un dialogo y el usuario escribe el texto. La API
    guarda la respuesta con estado CAPTCHA_RESPONDIDO'. Sin interfaz
    todavia (Fase 18), la ejercita una herramienta actuando como el
    usuario humano -- nunca el robot (Seccion 8.4: 'la prueba actua como
    el usuario humano llamando a la API del sistema')."""

    def __init__(self, repositorio: RepositorioSesionPlataforma) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, sesion_id: int, respuesta: str) -> None:
        sesion = await self._repositorio.obtener(sesion_id)
        if sesion is None:
            raise ErrorSesionNoEncontrada(f"No existe la sesion {sesion_id}.")
        if sesion.estado != "ESPERANDO_CAPTCHA":
            raise ErrorSesionPlataforma(
                f"La sesion {sesion_id} no esta esperando un CAPTCHA "
                f"(estado actual: {sesion.estado})."
            )
        await self._repositorio.registrar_respuesta(sesion_id, respuesta)


@dataclass(frozen=True, slots=True)
class _ResultadoInicioSesion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2)."""

    sesion_id: int
    plataforma: str
    actor: str
    inicio: datetime
    fin: datetime
    resultado: str
    motivo: str | None = None
    usuario_origen: str | None = None


class IniciarSesionPlataforma:
    """Seccion 8.4, puntos 2 a 6: ejecuta el robot de ingreso asistido y
    registra el resultado (evento y medicion `inicio_sesion_plataforma`).
    Al activarse la sesion, reactiva a PENDIENTE los trabajos que habian
    quedado en REQUIERE_SESION para esa plataforma (punto 6); quien llama
    decide que tipos de trabajo dependen de cada plataforma, porque ese
    mapeo es de orquestacion, no una regla del dominio de sesiones."""

    def __init__(
        self,
        repositorio: RepositorioSesionPlataforma,
        repositorio_trabajos: RepositorioTrabajos,
        asistente: AsistenteSesionPlataforma,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._repositorio_trabajos = repositorio_trabajos
        self._asistente = asistente
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(
        self,
        sesion_id: int,
        plataforma: str,
        actor: str,
        tipos_trabajo_dependientes: tuple[str, ...],
        usuario_origen: str | None = None,
    ) -> None:
        inicio = self._reloj.ahora()
        try:
            await self._asistente.iniciar_sesion(sesion_id, plataforma)
        except ErrorSesionFallida as error:
            fin = self._reloj.ahora()
            await self._registrar(
                _ResultadoInicioSesion(
                    sesion_id,
                    plataforma,
                    actor,
                    inicio,
                    fin,
                    "fallida",
                    str(error),
                    usuario_origen,
                )
            )
            raise

        fin = self._reloj.ahora()
        if tipos_trabajo_dependientes:
            await self._repositorio_trabajos.reactivar_requieren_sesion(tipos_trabajo_dependientes)
        await self._registrar(
            _ResultadoInicioSesion(
                sesion_id, plataforma, actor, inicio, fin, "activa", usuario_origen=usuario_origen
            )
        )

    async def _registrar(self, r: _ResultadoInicioSesion) -> None:
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_plataforma_id=r.sesion_id,
                tipo_evento=f"SESION_PLATAFORMA_{r.resultado.upper()}",
                actor=r.actor,
                estado_previo=None,
                estado_nuevo=r.resultado.upper(),
                datos={"sesion_id": r.sesion_id, "plataforma": r.plataforma, "motivo": r.motivo},
                usuario_origen=r.usuario_origen,
            )
        )
        await self._observabilidad.mediciones.registrar(
            MedicionPaso(
                paso="inicio_sesion_plataforma",
                inicio=r.inicio,
                fin=r.fin,
                actor=r.actor,
                resultado=r.resultado,
                datos={
                    "sesion_id": r.sesion_id,
                    "plataforma": r.plataforma,
                    "usuario_origen": r.usuario_origen,
                },
            )
        )


class ListarSesionesPlataforma:
    """Seccion 11: `GET /plataformas/sesiones` (Fase 18)."""

    def __init__(self, repositorio: RepositorioSesionPlataforma) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, plataforma: str | None) -> list[SesionPlataforma]:
        return await self._repositorio.listar(plataforma)


class ObtenerSesionPlataforma:
    """Seccion 11: `GET /plataformas/sesiones/{id}/captcha` (Fase 18)
    necesita la sesion completa (incluida `imagen_captcha`), no solo el
    listado resumido."""

    def __init__(self, repositorio: RepositorioSesionPlataforma) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, sesion_id: int) -> SesionPlataforma | None:
        return await self._repositorio.obtener(sesion_id)
