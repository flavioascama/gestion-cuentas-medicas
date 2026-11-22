"""CU-18, RF-19: administracion de usuarios y roles. Solo rol administrador.

No enumerado en la tabla de la Seccion 10.1 (que solo lista /auth/sesion
para este contexto), pero RF-19 y CU-18 exigen esta capacidad y la
Seccion 6.1 exige la tabla `usuario`. Ver docs/DECISIONES.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.dependencias import (
    construir_actualizar_usuario,
    construir_listar_usuarios,
    construir_registrar_usuario,
    construir_restablecer_clave_usuario,
    requiere_rol,
)
from app.api.esquemas_acceso import (
    RespuestaUsuario,
    SolicitudActualizarUsuario,
    SolicitudCrearUsuario,
    SolicitudRestablecerClave,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.casos_uso import (
    ActualizarUsuario,
    ListarUsuarios,
    RegistrarUsuario,
    RestablecerClaveUsuario,
)
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.errores import (
    ClaveDebilError,
    NombreUsuarioDuplicadoError,
    NoPuedeCambiarSusRolesError,
    NoPuedeRestablecerSuClaveError,
    RolDesconocidoError,
    RolesRequeridosError,
    UsuarioNoEncontradoError,
)
from app.dominio.acceso.puertos import CargaSesion
from app.infraestructura.observabilidad.registro import obtener_registrador

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
_registrador = obtener_registrador("api.usuarios")

_solo_administrador = requiere_rol(NombreRol.ADMINISTRADOR)


@router.post("", response_model=RespuestaUsuario, status_code=status.HTTP_201_CREATED)
async def crear_usuario(
    solicitud: SolicitudCrearUsuario,
    caso_uso: RegistrarUsuario = Depends(construir_registrar_usuario),
    actor: CargaSesion = Depends(_solo_administrador),
) -> RespuestaUsuario:
    try:
        usuario = await caso_uso.ejecutar(
            nombre_usuario=solicitud.nombre_usuario,
            clave=solicitud.clave,
            nombres=solicitud.nombres,
            roles=frozenset(solicitud.roles),
            actor=actor.nombre_usuario,
        )
    except NombreUsuarioDuplicadoError as error:
        raise ErrorAplicacion(
            "NOMBRE_USUARIO_DUPLICADO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except RolesRequeridosError as error:
        raise ErrorAplicacion(
            "ROLES_REQUERIDOS", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    except ClaveDebilError as error:
        raise ErrorAplicacion(
            "CLAVE_DEBIL", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error

    _registrador.info(
        "usuario_creado",
        caso_uso="crear_usuario",
        actor=actor.nombre_usuario,
        nombre_usuario_creado=usuario.nombre_usuario,
    )
    return RespuestaUsuario.desde_entidad(usuario)


@router.get("", response_model=list[RespuestaUsuario])
async def listar_usuarios(
    caso_uso: ListarUsuarios = Depends(construir_listar_usuarios),
    actor: CargaSesion = Depends(_solo_administrador),
) -> list[RespuestaUsuario]:
    usuarios = await caso_uso.ejecutar()
    return [RespuestaUsuario.desde_entidad(usuario) for usuario in usuarios]


@router.patch("/{usuario_id}", response_model=RespuestaUsuario)
async def actualizar_usuario(
    usuario_id: int,
    solicitud: SolicitudActualizarUsuario,
    caso_uso: ActualizarUsuario = Depends(construir_actualizar_usuario),
    actor: CargaSesion = Depends(_solo_administrador),
) -> RespuestaUsuario:
    try:
        usuario = await caso_uso.ejecutar(
            usuario_id,
            nombres=solicitud.nombres,
            roles=frozenset(solicitud.roles) if solicitud.roles is not None else None,
            activo=solicitud.activo,
            actor=actor.nombre_usuario,
        )
    except UsuarioNoEncontradoError as error:
        raise ErrorAplicacion(
            "USUARIO_NO_ENCONTRADO", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except NoPuedeCambiarSusRolesError as error:
        raise ErrorAplicacion(
            "NO_PUEDE_CAMBIAR_SUS_ROLES", str(error), estado_http=status.HTTP_403_FORBIDDEN
        ) from error
    except RolesRequeridosError as error:
        raise ErrorAplicacion(
            "ROLES_REQUERIDOS", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    except RolDesconocidoError as error:
        raise ErrorAplicacion(
            "ROL_DESCONOCIDO", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error

    _registrador.info(
        "usuario_actualizado",
        caso_uso="actualizar_usuario",
        actor=actor.nombre_usuario,
        usuario_id=usuario_id,
    )
    return RespuestaUsuario.desde_entidad(usuario)


@router.post("/{usuario_id}/restablecer-clave", response_model=RespuestaUsuario)
async def restablecer_clave_usuario(
    usuario_id: int,
    solicitud: SolicitudRestablecerClave,
    caso_uso: RestablecerClaveUsuario = Depends(construir_restablecer_clave_usuario),
    actor: CargaSesion = Depends(_solo_administrador),
) -> RespuestaUsuario:
    try:
        usuario = await caso_uso.ejecutar(usuario_id, solicitud.clave, actor.nombre_usuario)
    except UsuarioNoEncontradoError as error:
        raise ErrorAplicacion(
            "USUARIO_NO_ENCONTRADO", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except NoPuedeRestablecerSuClaveError as error:
        raise ErrorAplicacion(
            "NO_PUEDE_RESTABLECER_SU_CLAVE", str(error), estado_http=status.HTTP_403_FORBIDDEN
        ) from error
    except ClaveDebilError as error:
        raise ErrorAplicacion(
            "CLAVE_DEBIL", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error

    _registrador.info(
        "clave_restablecida",
        caso_uso="restablecer_clave_usuario",
        actor=actor.nombre_usuario,
        usuario_id=usuario_id,
    )
    return RespuestaUsuario.desde_entidad(usuario)
