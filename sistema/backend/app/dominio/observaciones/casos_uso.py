"""Casos de uso del contexto de observaciones/glosas: CU-08 (registrar y
clasificar), CU-09 (asignar/reasignar el responsable) y CU-10, su mitad
de "elaborar la respuesta" (la refacturacion de CU-10 es del modulo de
codificacion CPMS, Seccion 5.2.4.2 y 8.2 -- este caso de uso solo cierra
el lado de la observacion y de la cuenta)."""

from __future__ import annotations

from dataclasses import dataclass

from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.puertos import RepositorioUsuarios
from app.dominio.observaciones.errores import (
    ErrorMotivoInexistente,
    ErrorObservacionInexistente,
    ErrorObservacionYaRespondida,
    ErrorResponsableNoValido,
)
from app.dominio.observaciones.puertos import RepositorioCatalogoMotivos, RepositorioObservaciones
from app.dominio.observaciones.valores import (
    ROL_RESPONSABLE_POR_NATURALEZA,
    DatosNuevaObservacion,
    DatosRegistroObservacion,
    MotivoObservacion,
    Naturaleza,
    Observacion,
)
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.orquestacion.valores import TipoTransicion
from app.dominio.puertos_comunes import Evento, Observabilidad, Reloj


def _transicion_de_registro(estado_actual: str | None, es_parcial: bool) -> TipoTransicion:
    """CU-08: la precondicion admite dos estados de origen distintos
    (Seccion 5.2.3.3) -- EN_AUDITORIA (primera observacion, T-07) o
    SUBSANADA (la aseguradora insiste tras una respuesta, T-09, que la
    Tabla 58 solo define para el caso total). Fuera de ambos, se
    devuelve GLOSA igual: el motor es quien debe rechazarla, con el
    mismo error que cualquier otra transicion no definida."""

    if estado_actual == "SUBSANADA":
        return TipoTransicion.NUEVA_OBSERVACION
    return TipoTransicion.GLOSA_PARCIAL if es_parcial else TipoTransicion.GLOSA


@dataclass(frozen=True, slots=True)
class ResultadoRegistroObservacion:
    observacion_id: int
    naturaleza: Naturaleza
    responsable_rol: NombreRol
    estado_cuenta: str


class RegistrarObservacion:
    """CU-08 (RF-09, RF-10, RF-16): clasifica por el motivo, asigna el
    responsable por naturaleza y lleva la cuenta a GLOSADA, GLOSADA_
    PARCIAL (T-07) o de vuelta a GLOSADA desde SUBSANADA (T-09)."""

    def __init__(
        self,
        repositorio: RepositorioObservaciones,
        catalogo: RepositorioCatalogoMotivos,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._catalogo = catalogo
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(self, datos: DatosRegistroObservacion) -> ResultadoRegistroObservacion:
        motivo = await self._catalogo.obtener(datos.motivo_codigo)
        if motivo is None:
            raise ErrorMotivoInexistente(
                f"El motivo {datos.motivo_codigo!r} no existe en el catalogo vigente."
            )

        estado_actual = await self._estado_cuenta.obtener_estado(datos.cuenta_medica_id)
        transicion = _transicion_de_registro(estado_actual, datos.es_parcial)
        estado_nuevo = validar_transicion(estado_actual, transicion)

        responsable_rol = ROL_RESPONSABLE_POR_NATURALEZA[motivo.naturaleza]
        ahora = self._reloj.ahora()
        observacion_id = await self._repositorio.crear(
            DatosNuevaObservacion(
                cuenta_medica_id=datos.cuenta_medica_id,
                motivo_codigo=motivo.codigo,
                naturaleza=motivo.naturaleza,
                es_parcial=datos.es_parcial,
                detalle_campo_objetado=datos.detalle_campo_objetado,
                responsable_rol=responsable_rol,
                registrado_en=ahora,
            )
        )
        await self._estado_cuenta.fijar_estado(datos.cuenta_medica_id, estado_nuevo)
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=datos.cuenta_medica_id,
                tipo_evento=transicion.value,
                actor=datos.actor,
                estado_previo=estado_actual,
                estado_nuevo=estado_nuevo,
                datos={
                    "observacion_id": observacion_id,
                    "motivo_codigo": motivo.codigo,
                    "naturaleza": motivo.naturaleza.value,
                    "es_parcial": datos.es_parcial,
                    "responsable_rol": responsable_rol.value,
                },
                usuario_origen=datos.usuario_origen,
            )
        )
        return ResultadoRegistroObservacion(
            observacion_id=observacion_id,
            naturaleza=motivo.naturaleza,
            responsable_rol=responsable_rol,
            estado_cuenta=estado_nuevo,
        )


class AsignarResponsableObservacion:
    """CU-09 (RF-10, RF-16): el jefe confirma o reasigna. Si corrige la
    naturaleza, el responsable propuesto se recalcula (Seccion 5.2.4.2);
    no mueve el estado de la cuenta, por eso no pasa por el motor.

    Con `usuarios` (2026-11-18) comprueba que la persona elegida exista,
    este activa y tenga el rol que responde esa naturaleza: antes se
    aceptaba cualquier numero de usuario."""

    def __init__(
        self,
        repositorio: RepositorioObservaciones,
        observabilidad: Observabilidad,
        usuarios: RepositorioUsuarios | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._observabilidad = observabilidad
        self._usuarios = usuarios

    async def ejecutar(
        self,
        observacion_id: int,
        actor: str,
        responsable_usuario_id: int | None,
        naturaleza_corregida: Naturaleza | None = None,
    ) -> None:
        observacion = await self._repositorio.obtener(observacion_id)
        if observacion is None:
            raise ErrorObservacionInexistente(f"No existe la observacion {observacion_id}.")

        naturaleza_final = naturaleza_corregida or observacion.naturaleza
        responsable_rol = ROL_RESPONSABLE_POR_NATURALEZA[naturaleza_final]
        await self._exigir_responsable_valido(responsable_usuario_id, responsable_rol)
        await self._repositorio.reasignar(
            observacion_id, naturaleza_final, responsable_rol, responsable_usuario_id
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=observacion.cuenta_medica_id,
                tipo_evento="OBSERVACION_REASIGNADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "observacion_id": observacion_id,
                    "naturaleza_anterior": observacion.naturaleza.value,
                    "naturaleza_nueva": naturaleza_final.value,
                    "responsable_rol": responsable_rol.value,
                    "responsable_usuario_id": responsable_usuario_id,
                },
            )
        )

    async def _exigir_responsable_valido(self, usuario_id: int | None, rol: NombreRol) -> None:
        if usuario_id is None or self._usuarios is None:
            return
        usuario = await self._usuarios.obtener_por_id(usuario_id)
        if usuario is None or not usuario.activo or rol not in usuario.roles:
            raise ErrorResponsableNoValido(
                f"El responsable debe ser un usuario activo con el rol {rol.value}."
            )


class ListarResponsablesPosibles:
    """CU-09: las personas a las que el jefe puede asignar una observacion
    (2026-11-18: antes escribia el numero interno del usuario). Son los
    usuarios activos con un rol que responde observaciones (Tabla 60)."""

    def __init__(self, usuarios: RepositorioUsuarios) -> None:
        self._usuarios = usuarios

    async def ejecutar(self) -> list[Usuario]:
        roles = frozenset(ROL_RESPONSABLE_POR_NATURALEZA.values())
        usuarios = await self._usuarios.listar()
        return [u for u in usuarios if u.activo and u.tiene_alguno(roles)]


class ResponderObservacion:
    """CU-10, lado de la observacion y la cuenta (RF-08, RF-11, RF-16):
    una observacion total cierra su control de plazo y lleva la cuenta
    de GLOSADA a SUBSANADA (T-08); una parcial no mueve la cuenta --
    Tabla 58/65/66 solo definen GLOSADA_PARCIAL -> LIQUIDADA_PARCIAL
    (T-10, CU-12, a cargo de tesoreria), no un subsanada parcial propio."""

    def __init__(
        self,
        repositorio: RepositorioObservaciones,
        estado_cuenta: RepositorioEstadoCuenta,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(
        self,
        observacion_id: int,
        respuesta_texto: str,
        respuesta_sustento: str | None,
        actor: str,
        usuario_origen: str | None = None,
    ) -> None:
        observacion = await self._repositorio.obtener(observacion_id)
        if observacion is None:
            raise ErrorObservacionInexistente(f"No existe la observacion {observacion_id}.")
        if observacion.estado == "RESPONDIDA":
            raise ErrorObservacionYaRespondida(
                f"La observacion {observacion_id} ya tiene una respuesta registrada."
            )

        ahora = self._reloj.ahora()
        estado_previo: str | None = None
        estado_nuevo: str | None = None
        if not observacion.es_parcial:
            estado_actual = await self._estado_cuenta.obtener_estado(observacion.cuenta_medica_id)
            estado_nuevo = validar_transicion(estado_actual, TipoTransicion.SUBSANACION)
            await self._estado_cuenta.fijar_estado(observacion.cuenta_medica_id, estado_nuevo)
            estado_previo = estado_actual

        await self._repositorio.responder(
            observacion_id, respuesta_texto, respuesta_sustento, ahora
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=observacion.cuenta_medica_id,
                tipo_evento="OBSERVACION_RESPONDIDA",
                actor=actor,
                estado_previo=estado_previo,
                estado_nuevo=estado_nuevo,
                datos={
                    "observacion_id": observacion_id,
                    "es_parcial": observacion.es_parcial,
                },
                usuario_origen=usuario_origen,
            )
        )


class ListarObservacionesPorCuenta:
    """Consulta de solo lectura (Seccion 5.2: "ninguna regla de negocio
    en una ruta" -- hasta una consulta directa pasa por un caso de uso,
    nunca un repositorio llamado desde la ruta)."""

    def __init__(self, repositorio: RepositorioObservaciones) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> list[Observacion]:
        return await self._repositorio.listar_por_cuenta(cuenta_medica_id)


class ListarCatalogoMotivos:
    """CU-08, flujo alternativo: la pantalla necesita listar las
    opciones del catalogo para que el analista elija el codigo."""

    def __init__(self, catalogo: RepositorioCatalogoMotivos) -> None:
        self._catalogo = catalogo

    async def ejecutar(self) -> list[MotivoObservacion]:
        return await self._catalogo.listar()
