"""Cableado de FastAPI: instancia adaptadores de infraestructura detras de
los puertos de dominio, y expone `requiere_rol` como el componente
transversal de autorizacion que exige AD-06.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC

import structlog
from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.configuracion import Configuracion, obtener_configuracion
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.cambio_clave import CambiarClavePropia, ColaboradoresCambioClave
from app.dominio.acceso.casos_uso import (
    ActualizarUsuario,
    CerrarSesion,
    ColaboradoresIniciarSesion,
    IniciarSesion,
    ListarUsuarios,
    PoliticaBloqueoSesion,
    RegistrarUsuario,
    RestablecerClaveUsuario,
)
from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.errores import (
    SesionExpiradaError,
    SesionInvalidaError,
    SesionRevocadaError,
)
from app.dominio.acceso.puertos import (
    CargaSesion,
    GestorSesion,
    RegistroRevocaciones,
    RepositorioUsuarios,
    VerificadorClave,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_revocaciones_sql import RegistroRevocacionesSql
from app.infraestructura.persistencia.repositorio_parametros_sistema_sql import valor_vigente
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.reloj import RelojSistema
from app.infraestructura.seguridad.gestor_sesion_jwt import GestorSesionJwt
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt

_esquema_portador = HTTPBearer(auto_error=False)

# Los adaptadores sin estado por solicitud se comparten como instancias de
# proceso; no abren conexion ni dependen de la sesion de base de datos.
_reloj_sistema = RelojSistema()
_verificador_clave = VerificadorClaveBcrypt()


def obtener_reloj() -> Reloj:
    return _reloj_sistema


def obtener_verificador_clave() -> VerificadorClave:
    return _verificador_clave


async def obtener_gestor_sesion(
    configuracion: Configuracion = Depends(obtener_configuracion),
    reloj: Reloj = Depends(obtener_reloj),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> GestorSesion:
    return GestorSesionJwt(
        clave_firma=configuracion.clave_firma_sesion,
        duracion_minutos=int(await valor_vigente(sesion, "DURACION_SESION_MINUTOS")),
        reloj=reloj,
    )


async def obtener_politica_bloqueo(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> PoliticaBloqueoSesion:
    return PoliticaBloqueoSesion(
        maximo_intentos_fallidos=int(
            await valor_vigente(sesion, "MAXIMO_INTENTOS_FALLIDOS_SESION")
        ),
        duracion_bloqueo_minutos=int(
            await valor_vigente(sesion, "DURACION_BLOQUEO_SESION_MINUTOS")
        ),
    )


def obtener_repositorio_usuarios(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioUsuarios:
    return RepositorioUsuariosSql(sesion)


def obtener_repositorio_revocaciones(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RegistroRevocaciones:
    return RegistroRevocacionesSql(sesion)


def obtener_registro_eventos(sesion: AsyncSession = Depends(obtener_sesion)) -> RegistroEventos:
    return RegistroEventosSql(sesion)


def obtener_colaboradores_iniciar_sesion(
    gestor_sesion: GestorSesion = Depends(obtener_gestor_sesion),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
) -> ColaboradoresIniciarSesion:
    return ColaboradoresIniciarSesion(
        gestor_sesion=gestor_sesion, registro_eventos=registro_eventos
    )


def construir_iniciar_sesion(
    repositorio: RepositorioUsuarios = Depends(obtener_repositorio_usuarios),
    verificador: VerificadorClave = Depends(obtener_verificador_clave),
    colaboradores: ColaboradoresIniciarSesion = Depends(obtener_colaboradores_iniciar_sesion),
    reloj: Reloj = Depends(obtener_reloj),
    politica: PoliticaBloqueoSesion = Depends(obtener_politica_bloqueo),
) -> IniciarSesion:
    return IniciarSesion(repositorio, verificador, colaboradores, reloj, politica)


def construir_registrar_usuario(
    repositorio: RepositorioUsuarios = Depends(obtener_repositorio_usuarios),
    verificador: VerificadorClave = Depends(obtener_verificador_clave),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
) -> RegistrarUsuario:
    # La clave que pone el administrador es temporal: se cambia al ingresar.
    return RegistrarUsuario(repositorio, verificador, registro_eventos, clave_temporal=True)


def construir_restablecer_clave_usuario(
    repositorio: RepositorioUsuarios = Depends(obtener_repositorio_usuarios),
    verificador: VerificadorClave = Depends(obtener_verificador_clave),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
) -> RestablecerClaveUsuario:
    return RestablecerClaveUsuario(repositorio, verificador, registro_eventos)


def construir_listar_usuarios(
    repositorio: RepositorioUsuarios = Depends(obtener_repositorio_usuarios),
) -> ListarUsuarios:
    return ListarUsuarios(repositorio)


def construir_actualizar_usuario(
    repositorio: RepositorioUsuarios = Depends(obtener_repositorio_usuarios),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
) -> ActualizarUsuario:
    return ActualizarUsuario(repositorio, registro_eventos)


def construir_cerrar_sesion(
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
    registro_revocaciones: RegistroRevocaciones = Depends(obtener_repositorio_revocaciones),
) -> CerrarSesion:
    return CerrarSesion(registro_eventos, registro_revocaciones)


def obtener_colaboradores_cambio_clave(
    gestor_sesion: GestorSesion = Depends(obtener_gestor_sesion),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
    registro_revocaciones: RegistroRevocaciones = Depends(obtener_repositorio_revocaciones),
) -> ColaboradoresCambioClave:
    return ColaboradoresCambioClave(gestor_sesion, registro_eventos, registro_revocaciones)


def construir_cambiar_clave(
    repositorio: RepositorioUsuarios = Depends(obtener_repositorio_usuarios),
    verificador: VerificadorClave = Depends(obtener_verificador_clave),
    colaboradores: ColaboradoresCambioClave = Depends(obtener_colaboradores_cambio_clave),
    reloj: Reloj = Depends(obtener_reloj),
    politica: PoliticaBloqueoSesion = Depends(obtener_politica_bloqueo),
) -> CambiarClavePropia:
    return CambiarClavePropia(repositorio, verificador, colaboradores, reloj, politica)


async def autenticar_sesion(
    credencial: HTTPAuthorizationCredentials | None = Depends(_esquema_portador),
    gestor_sesion: GestorSesion = Depends(obtener_gestor_sesion),
    registro_revocaciones: RegistroRevocaciones = Depends(obtener_repositorio_revocaciones),
    repositorio_usuarios: RepositorioUsuarios = Depends(obtener_repositorio_usuarios),
) -> CargaSesion:
    """RF-18: autentica antes de permitir cualquier operacion protegida.

    Control C-01 (Seccion 5.2.7): un JWT con firma y vigencia validas ya
    no basta. Esta dependencia ademas rechaza la credencial si su `jti`
    esta en la lista de revocacion (se cerro sesion con ella) o si el
    usuario que la emitio ya no esta activo (se le desactivo despues) --
    las dos formas de revocacion que exige el control.

    Solo autentica: las operaciones usan `obtener_usuario_actual`, que
    ademas exige que la persona ya haya cambiado su clave temporal."""

    if credencial is None:
        raise ErrorAplicacion(
            "SESION_REQUERIDA",
            "Se requiere iniciar sesión.",
            estado_http=status.HTTP_401_UNAUTHORIZED,
        )
    try:
        carga = gestor_sesion.verificar(credencial.credentials)
    except SesionExpiradaError as error:
        raise ErrorAplicacion(
            "SESION_EXPIRADA", str(error), estado_http=status.HTTP_401_UNAUTHORIZED
        ) from error
    except SesionInvalidaError as error:
        raise ErrorAplicacion(
            "SESION_INVALIDA", str(error), estado_http=status.HTTP_401_UNAUTHORIZED
        ) from error

    try:
        usuario = await _verificar_no_revocada(carga, registro_revocaciones, repositorio_usuarios)
    except SesionRevocadaError as error:
        raise ErrorAplicacion(
            "SESION_REVOCADA", str(error), estado_http=status.HTTP_401_UNAUTHORIZED
        ) from error

    structlog.contextvars.bind_contextvars(actor=carga.nombre_usuario)
    # Manda el dato del usuario, no el que viaja en la credencial.
    return replace(carga, debe_cambiar_clave=usuario.debe_cambiar_clave)


async def obtener_usuario_actual(
    carga: CargaSesion = Depends(autenticar_sesion),
) -> CargaSesion:
    """Quien todavia tiene la clave que le puso el administrador solo puede
    cambiarla o cerrar sesion (2026-11-18): cualquier otra operacion se
    rechaza aqui, no solo en la pantalla."""
    if carga.debe_cambiar_clave:
        raise ErrorAplicacion(
            "CAMBIO_DE_CLAVE_REQUERIDO",
            "Debe cambiar su contraseña antes de continuar.",
            estado_http=status.HTTP_403_FORBIDDEN,
        )
    return carga


async def _verificar_no_revocada(
    carga: CargaSesion,
    registro_revocaciones: RegistroRevocaciones,
    repositorio_usuarios: RepositorioUsuarios,
) -> Usuario:
    if await registro_revocaciones.esta_revocado(carga.jti):
        raise SesionRevocadaError("La sesión fue cerrada; vuelva a iniciar sesión.")
    usuario = await repositorio_usuarios.obtener_por_id(carga.usuario_id)
    if usuario is None or not usuario.activo:
        raise SesionRevocadaError("El usuario ya no tiene acceso; vuelva a iniciar sesión.")
    if _emitida_antes_del_restablecimiento(carga, usuario):
        raise SesionRevocadaError("Su contraseña fue restablecida; vuelva a iniciar sesión.")
    return usuario


def _emitida_antes_del_restablecimiento(carga: CargaSesion, usuario: Usuario) -> bool:
    """Al restablecer la contraseña, las sesiones que la persona tenia
    abiertas dejan de valer. `iat` va en segundos enteros: se compara sin
    los microsegundos de la columna, para que valga la sesion que se abre
    con la contraseña temporal en el mismo segundo."""
    desde = usuario.sesiones_validas_desde
    if desde is None:
        return False
    if carga.emitida_en is None:
        return True
    if desde.tzinfo is None:
        desde = desde.replace(tzinfo=UTC)
    return carga.emitida_en < desde.replace(microsecond=0)


def requiere_rol(
    *roles_permitidos: NombreRol,
) -> Callable[..., Awaitable[CargaSesion]]:
    """Componente transversal de autorizacion por rol (AD-06, RF-19).

    Uso: `Depends(requiere_rol(NombreRol.ADMINISTRADOR))`.
    """

    permitidos = frozenset(roles_permitidos)

    async def verificar(
        solicitud: Request,
        carga: CargaSesion = Depends(obtener_usuario_actual),
        sesion: AsyncSession = Depends(obtener_sesion),
    ) -> CargaSesion:
        if not carga.roles & permitidos:
            # RT-10 y C-08 (verificacion de cumplimiento, 2026-11-12): el
            # acceso indebido queda en la bitacora, con la operacion intentada.
            await RegistroEventosSql(sesion).registrar(
                Evento(
                    cuenta_medica_id=None,
                    sesion_usuario_id=carga.usuario_id,
                    tipo_evento="ACCESO_DENEGADO",
                    actor=carga.nombre_usuario,
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"metodo": solicitud.method, "ruta": solicitud.url.path},
                )
            )
            raise ErrorAplicacion(
                "ROL_NO_AUTORIZADO",
                "Su rol no tiene permiso para esta operación.",
                estado_http=status.HTTP_403_FORBIDDEN,
                detalles={"roles_permitidos": sorted(r.value for r in permitidos)},
            )
        return carga

    return verificar
