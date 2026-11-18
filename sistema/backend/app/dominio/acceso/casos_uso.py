"""Casos de uso del contexto de acceso: CU-17 (autenticarse) y CU-18
(administrar usuarios y roles). Orquestan puertos, sin conocer SQLAlchemy,
passlib, PyJWT ni FastAPI (Seccion 5.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil

from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.errores import (
    CredencialesInvalidasError,
    CuentaBloqueadaError,
    NombreUsuarioDuplicadoError,
    RolesRequeridosError,
    UsuarioNoEncontradoError,
)
from app.dominio.acceso.puertos import (
    GestorSesion,
    RegistroRevocaciones,
    RepositorioUsuarios,
    VerificadorClave,
)
from app.dominio.acceso.valores import validar_politica_clave
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj


@dataclass(frozen=True, slots=True)
class PoliticaBloqueoSesion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): agrupa
    los dos parametros del control C-01 que vienen de Configuracion, para
    que IniciarSesion no supere el limite de cinco parametros por
    constructor (Seccion 3) al sumarle `reloj`."""

    maximo_intentos_fallidos: int
    duracion_bloqueo_minutos: int


@dataclass(frozen=True, slots=True)
class ColaboradoresIniciarSesion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): agrupa
    `gestor_sesion` y `registro_eventos` para que IniciarSesion no
    supere el limite de cinco parametros por constructor al sumarle
    este ultimo (RT-08/control C-08, Fase 29: la bitacora de accesos
    exige registrar tambien los inicios de sesion, no solo su cierre,
    que ya lo hacia desde la Fase 18)."""

    gestor_sesion: GestorSesion
    registro_eventos: RegistroEventos


class IniciarSesion:
    """CU-17. RF-18: autentica antes de permitir cualquier operacion.

    Control C-01 (Seccion 5.2.7): tras `politica.maximo_intentos_fallidos`
    intentos fallidos seguidos sobre una cuenta activa, esa cuenta queda
    bloqueada por `politica.duracion_bloqueo_minutos`. El bloqueo se evalua
    ANTES de verificar la clave (si no, un atacante seguiria pudiendo
    probar claves contra una cuenta ya bloqueada)."""

    def __init__(
        self,
        repositorio: RepositorioUsuarios,
        verificador: VerificadorClave,
        colaboradores: ColaboradoresIniciarSesion,
        reloj: Reloj,
        politica: PoliticaBloqueoSesion,
    ) -> None:
        self._repositorio = repositorio
        self._verificador = verificador
        self._gestor_sesion = colaboradores.gestor_sesion
        self._registro_eventos = colaboradores.registro_eventos
        self._reloj = reloj
        self._politica = politica

    async def ejecutar(self, nombre_usuario: str, clave: str) -> str:
        usuario = await self._repositorio.obtener_por_nombre_usuario(nombre_usuario)
        ahora = self._reloj.ahora()

        bloqueado_hasta = usuario.bloqueado_hasta if usuario is not None else None
        if bloqueado_hasta is not None and bloqueado_hasta > ahora:
            segundos_restantes = (bloqueado_hasta - ahora).total_seconds()
            minutos_restantes = max(1, ceil(segundos_restantes / 60))
            await self._registrar_rechazo(nombre_usuario, usuario, "cuenta_bloqueada")
            raise CuentaBloqueadaError(minutos_restantes)

        motivo = self._motivo_rechazo(usuario, clave)
        if motivo is not None:
            if usuario is not None and usuario.activo:
                assert usuario.id is not None, "Un usuario ya persistido siempre tiene id"
                await self._registrar_intento_fallido(usuario.id, ahora)
            await self._registrar_rechazo(nombre_usuario, usuario, motivo)
            raise CredencialesInvalidasError("Nombre de usuario o clave incorrectos.")
        assert usuario is not None, "Sin motivo de rechazo, el usuario existe"

        assert usuario.id is not None, "Un usuario ya persistido siempre tiene id"
        await self._repositorio.registrar_inicio_exitoso(usuario.id)
        # RT-08/control C-08 (Seccion 6.2.1, Fase 29): la bitacora de
        # accesos se lee directo del almacen de eventos -- "inicio de
        # sesion" es, igual que "sesion cerrada" desde la Fase 18, un
        # evento mas sobre el agregado de la sesion de usuario.
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario.id,
                tipo_evento="SESION_INICIADA",
                actor=nombre_usuario,
                estado_previo=None,
                estado_nuevo=None,
            )
        )
        return self._gestor_sesion.emitir(usuario)

    def _motivo_rechazo(self, usuario: Usuario | None, clave: str) -> str | None:
        if usuario is None:
            return "usuario_inexistente"
        if not usuario.activo:
            return "usuario_inactivo"
        if not self._verificador.verificar(clave, usuario.hash_clave):
            return "clave_incorrecta"
        return None

    async def _registrar_rechazo(
        self, nombre_usuario: str, usuario: Usuario | None, motivo: str
    ) -> None:
        """RF-20, C-08 y RT-08 (verificacion de cumplimiento, 2026-11-12):
        la bitacora registra tambien el ingreso rechazado, no solo el
        exitoso. Va al agregado de sesion del usuario; un nombre de usuario
        que no existe va al agregado 0 ("usuario inexistente"), para que
        los intentos contra nombres inventados tambien queden."""
        agregado = usuario.id if usuario is not None and usuario.id is not None else 0
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=agregado,
                tipo_evento="SESION_RECHAZADA",
                actor=nombre_usuario,
                estado_previo=None,
                estado_nuevo=None,
                datos={"motivo": motivo},
            )
        )

    async def _registrar_intento_fallido(self, usuario_id: int, ahora: datetime) -> None:
        intentos = await self._repositorio.incrementar_intentos_fallidos(usuario_id)
        if intentos >= self._politica.maximo_intentos_fallidos:
            hasta = ahora + timedelta(minutes=self._politica.duracion_bloqueo_minutos)
            await self._repositorio.bloquear(usuario_id, hasta)


async def _registrar_administracion(
    registro_eventos: RegistroEventos | None,
    usuario: Usuario,
    tipo_evento: str,
    actor: str,
    datos: dict[str, object],
) -> None:
    """CU-18 (verificacion de cumplimiento, 2026-11-12): la administracion
    de usuarios queda en la bitacora, en el agregado de sesion del usuario
    administrado. Sin datos personales (C-11): los roles y que campos
    cambiaron, nunca los nombres."""
    if registro_eventos is None:
        return
    assert usuario.id is not None, "Un usuario ya persistido siempre tiene id"
    await registro_eventos.registrar(
        Evento(
            cuenta_medica_id=None,
            sesion_usuario_id=usuario.id,
            tipo_evento=tipo_evento,
            actor=actor,
            estado_previo=None,
            estado_nuevo=None,
            datos=datos,
        )
    )


class RegistrarUsuario:
    """CU-18, parte de RF-19: crear un usuario con sus roles iniciales.

    `clave_temporal` (2026-11-18): la clave la pone el administrador desde
    la pantalla, asi que la persona debe cambiarla en su primer ingreso.
    Las cargas iniciales y las pruebas crean usuarios sin esa obligacion."""

    def __init__(
        self,
        repositorio: RepositorioUsuarios,
        verificador: VerificadorClave,
        registro_eventos: RegistroEventos | None = None,
        clave_temporal: bool = False,
    ) -> None:
        self._repositorio = repositorio
        self._verificador = verificador
        self._registro_eventos = registro_eventos
        self._clave_temporal = clave_temporal

    async def ejecutar(
        self,
        nombre_usuario: str,
        clave: str,
        nombres: str,
        roles: frozenset[NombreRol],
        actor: str = "sistema",
    ) -> Usuario:
        if await self._repositorio.obtener_por_nombre_usuario(nombre_usuario) is not None:
            raise NombreUsuarioDuplicadoError(nombre_usuario)
        if not roles:
            raise RolesRequeridosError()
        validar_politica_clave(clave)
        usuario = Usuario(
            id=None,
            nombre_usuario=nombre_usuario,
            nombres=nombres,
            hash_clave=self._verificador.generar_hash(clave),
            activo=True,
            roles=roles,
            debe_cambiar_clave=self._clave_temporal,
        )
        creado = await self._repositorio.crear(usuario)
        await _registrar_administracion(
            self._registro_eventos,
            creado,
            "USUARIO_CREADO",
            actor,
            {
                "nombre_usuario": creado.nombre_usuario,
                "roles": sorted(str(r) for r in creado.roles),
            },
        )
        return creado


class ActualizarUsuario:
    """CU-18, parte de RF-19: editar nombres, roles o activar/desactivar
    un usuario existente. No hay borrado fisico: "eliminar" un usuario
    desde la pantalla de administracion desactiva su acceso (activo=False,
    IniciarSesion ya lo rechaza), pero conserva la fila -- RNF-08 exige
    que el actor de cada evento pasado siga siendo identificable, y
    borrar la fila lo perderia o violaria la integridad referencial."""

    def __init__(
        self, repositorio: RepositorioUsuarios, registro_eventos: RegistroEventos | None = None
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(
        self,
        usuario_id: int,
        nombres: str | None = None,
        roles: frozenset[NombreRol] | None = None,
        activo: bool | None = None,
        actor: str = "sistema",
    ) -> Usuario:
        if roles is not None and not roles:
            raise RolesRequeridosError()
        usuario = await self._repositorio.actualizar(usuario_id, nombres, roles, activo)
        if usuario is None:
            raise UsuarioNoEncontradoError(usuario_id)
        campos = [
            campo
            for campo, valor in (("nombres", nombres), ("roles", roles), ("activo", activo))
            if valor is not None
        ]
        tipo_evento = "USUARIO_ACTUALIZADO"
        if activo is not None:
            tipo_evento = "USUARIO_REACTIVADO" if activo else "USUARIO_DESACTIVADO"
        await _registrar_administracion(
            self._registro_eventos,
            usuario,
            tipo_evento,
            actor,
            {
                "campos": campos,
                "roles": sorted(str(r) for r in usuario.roles),
                "activo": usuario.activo,
            },
        )
        return usuario


class ListarUsuarios:
    """CU-18: listado para administracion. No expone hash_clave (ver esquemas_acceso.py)."""

    def __init__(self, repositorio: RepositorioUsuarios) -> None:
        self._repositorio = repositorio

    async def ejecutar(self) -> list[Usuario]:
        return await self._repositorio.listar()


class CerrarSesion:
    """Seccion 11: `DELETE /auth/sesion` (Fase 18), revisada por el control
    C-01 de la Seccion 5.2.7 ("se revoca al cerrar la sesion o al
    desactivar al usuario"): a diferencia del diseno original (AD-06, JWT
    enteramente sin estado), este caso de uso ahora SI invalida el token
    -- registra su `jti` en la lista de revocacion, ademas de dejar
    constancia del cierre para auditoria (RF-16). Ver docs/DECISIONES.md,
    Fase 18 y Fase 22."""

    def __init__(
        self, registro_eventos: RegistroEventos, registro_revocaciones: RegistroRevocaciones
    ) -> None:
        self._registro_eventos = registro_eventos
        self._registro_revocaciones = registro_revocaciones

    async def ejecutar(self, actor: str, usuario_id: int, jti: str, expira_en: datetime) -> None:
        await self._registro_revocaciones.revocar(jti, expira_en)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento="SESION_CERRADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
            )
        )
