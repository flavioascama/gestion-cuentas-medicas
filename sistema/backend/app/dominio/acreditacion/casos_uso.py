"""Casos de uso del contexto de acreditacion (Seccion 8.1, CU-01)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from app.dominio.acreditacion.puertos import (
    AcreditacionRegistrada,
    AcreditacionWeb,
    ErrorAcreditacion,
    ErrorCuentaNoEncontrada,
    RepositorioAcreditacion,
)
from app.dominio.acreditacion.valores import ResultadoAcreditacion, admite_consulta
from app.dominio.puertos_comunes import (
    Evento,
    MedicionPaso,
    RegistroEventos,
    RegistroMediciones,
    Reloj,
    RepositorioTrabajos,
)

TIPO_TRABAJO_CONSULTAR_COBERTURA = "CONSULTAR_COBERTURA"
_COMPONENTE_EJECUTOR = "robot_acreditacion_playwright"


class ErrorCuentaYaAcreditada(ErrorAcreditacion):
    pass


class SolicitarVerificacionCobertura:
    """Seccion 8.1, CU-01, punto 1: 'el analista solicita la
    verificacion... crea el trabajo CONSULTAR_COBERTURA y responde de
    inmediato con el identificador del trabajo'."""

    def __init__(
        self,
        repositorio: RepositorioAcreditacion,
        repositorio_trabajos: RepositorioTrabajos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._repositorio_trabajos = repositorio_trabajos
        self._reloj = reloj

    async def ejecutar(self, cuenta_medica_id: int, solicitado_por: str) -> int:
        contexto = await self._repositorio.obtener_contexto_cuenta(cuenta_medica_id)
        if contexto is None:
            raise ErrorCuentaNoEncontrada("No existe la cuenta.")
        ya_acreditada = await self._repositorio.existe_acreditacion(cuenta_medica_id)
        if not admite_consulta(contexto, ya_acreditada):
            raise ErrorCuentaYaAcreditada(
                "La cobertura de la cuenta ya no se puede volver a consultar: la cuenta "
                "tiene comprobante o ya no está registrada."
            )
        return await self._repositorio_trabajos.encolar(
            tipo=TIPO_TRABAJO_CONSULTAR_COBERTURA,
            # Control C-07 (Seccion 5.2.7): el robot ejecuta esto mas
            # tarde, en otro proceso -- "usuario_origen" es como
            # COBERTURA_VERIFICADA sabe a quien atribuirselo.
            carga_util={"cuenta_medica_id": cuenta_medica_id, "usuario_origen": solicitado_por},
            proximo_intento=self._reloj.ahora(),
        )


@dataclass(frozen=True, slots=True)
class _ResultadoVerificacion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo que
    `_registrar_resultado` necesita para dejar constancia (evento y
    medicion) de una verificacion de cobertura ya persistida."""

    cuenta_medica_id: int
    trabajo_id: int
    actor: str
    inicio: datetime
    fin: datetime
    resultado: ResultadoAcreditacion
    acreditacion_id: int
    usuario_origen: str | None = None


class VerificarCobertura:
    """Seccion 8.1, CU-01, puntos 3-5: ejecuta el robot, registra el
    resultado en `acreditacion` y emite `COBERTURA_VERIFICADA`. Vive en
    dominio porque no toca infraestructura directamente -- delega en el
    puerto `AcreditacionWeb`, cuya unica implementacion (Playwright) corre
    en el proceso trabajador (AD-02), no aqui."""

    def __init__(
        self,
        repositorio: RepositorioAcreditacion,
        adaptador: AcreditacionWeb,
        registro_eventos: RegistroEventos,
        registro_mediciones: RegistroMediciones,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._adaptador = adaptador
        self._registro_eventos = registro_eventos
        self._registro_mediciones = registro_mediciones
        self._reloj = reloj

    async def ejecutar(
        self,
        trabajo_id: int,
        cuenta_medica_id: int,
        actor: str,
        usuario_origen: str | None = None,
    ) -> int | None:
        """Devuelve el id de la acreditacion guardada, o None si la cuenta
        ya tiene una y no admite otra consulta (idempotencia, Seccion 8.1:
        'un reintento no duplica registros') -- en ese caso no repite la
        consulta ni la medicion. Una nueva consulta admitida guarda otra
        acreditacion, que pasa a ser la vigente; la anterior se conserva."""

        inicio = self._reloj.ahora()
        contexto = await self._repositorio.obtener_contexto_cuenta(cuenta_medica_id)
        if contexto is None:
            raise ErrorCuentaNoEncontrada("No existe la cuenta.")
        ya_acreditada = await self._repositorio.existe_acreditacion(cuenta_medica_id)
        if not admite_consulta(contexto, ya_acreditada):
            return None

        resultado = await self._adaptador.verificar_cobertura(contexto, trabajo_id)
        fin = self._reloj.ahora()
        acreditacion_id = await self._repositorio.guardar_acreditacion(
            cuenta_medica_id=cuenta_medica_id,
            resultado=resultado,
            instante=fin,
            duracion_ms=int((fin - inicio).total_seconds() * 1000),
            componente_ejecutor=_COMPONENTE_EJECUTOR,
        )
        await self._registrar_resultado(
            _ResultadoVerificacion(
                cuenta_medica_id=cuenta_medica_id,
                trabajo_id=trabajo_id,
                actor=actor,
                inicio=inicio,
                fin=fin,
                resultado=resultado,
                acreditacion_id=acreditacion_id,
                usuario_origen=usuario_origen,
            )
        )
        return acreditacion_id

    async def _registrar_resultado(self, r: _ResultadoVerificacion) -> None:
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=r.cuenta_medica_id,
                tipo_evento="COBERTURA_VERIFICADA",
                actor=r.actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "acreditacion_id": r.acreditacion_id,
                    "condicion_cobertura": r.resultado.condicion_cobertura,
                    "codigo_autorizacion": r.resultado.codigo_autorizacion,
                },
                usuario_origen=r.usuario_origen,
            )
        )
        await self._registro_mediciones.registrar(
            MedicionPaso(
                paso="verificacion_cobertura",
                inicio=r.inicio,
                fin=r.fin,
                actor=r.actor,
                cuenta_medica_id=r.cuenta_medica_id,
                resultado="acreditado",
                datos={
                    "acreditacion_id": r.acreditacion_id,
                    "trabajo_id": r.trabajo_id,
                    "usuario_origen": r.usuario_origen,
                },
            )
        )


class ObtenerAcreditacion:
    """Seccion 11: `GET /cuentas/{id}/acreditacion` (Fase 18)."""

    def __init__(self, repositorio: RepositorioAcreditacion) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> AcreditacionRegistrada | None:
        """La vigente (la mas reciente), con si se puede volver a consultar."""
        acreditacion = await self._repositorio.obtener_acreditacion(cuenta_medica_id)
        if acreditacion is None:
            return None
        contexto = await self._repositorio.obtener_contexto_cuenta(cuenta_medica_id)
        admite = contexto is not None and admite_consulta(contexto, ya_acreditada=True)
        return replace(acreditacion, admite_reconsulta=admite)
