"""El usuario cambia su propia clave (2026-11-18).

Hasta ahora la clave solo la ponia el administrador al crear al usuario, y
nadie podia cambiarla: el administrador seguia conociendo la clave de cada
persona. Desde esta fecha quien recibe una clave puesta por el administrador
debe cambiarla en su primer ingreso (`Usuario.debe_cambiar_clave`), y
cualquier usuario puede cambiar la suya cuando quiera.

Reglas (control C-01): se exige la clave actual; la nueva cumple la politica
de claves y es distinta de la actual; los intentos con una clave actual
equivocada cuentan igual que los ingresos fallidos y bloquean la cuenta; al
cambiarla se revoca la credencial con la que se hizo y se emite una nueva.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from math import ceil

from app.dominio.acceso.casos_uso import PoliticaBloqueoSesion
from app.dominio.acceso.entidades import Usuario
from app.dominio.acceso.errores import (
    ClaveActualIncorrectaError,
    ClaveRepetidaError,
    CuentaBloqueadaError,
    UsuarioNoEncontradoError,
)
from app.dominio.acceso.puertos import (
    CargaSesion,
    GestorSesion,
    RegistroRevocaciones,
    RepositorioUsuarios,
    VerificadorClave,
)
from app.dominio.acceso.valores import validar_politica_clave
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj


@dataclass(frozen=True, slots=True)
class ColaboradoresCambioClave:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2)."""

    gestor_sesion: GestorSesion
    registro_eventos: RegistroEventos
    registro_revocaciones: RegistroRevocaciones


class CambiarClavePropia:
    def __init__(
        self,
        repositorio: RepositorioUsuarios,
        verificador: VerificadorClave,
        colaboradores: ColaboradoresCambioClave,
        reloj: Reloj,
        politica: PoliticaBloqueoSesion,
    ) -> None:
        self._repositorio = repositorio
        self._verificador = verificador
        self._colaboradores = colaboradores
        self._reloj = reloj
        self._politica = politica

    async def ejecutar(self, sesion: CargaSesion, clave_actual: str, clave_nueva: str) -> str:
        """Devuelve la credencial nueva; la anterior queda revocada."""
        usuario = await self._repositorio.obtener_por_id(sesion.usuario_id)
        if usuario is None or usuario.id is None or not usuario.activo:
            raise UsuarioNoEncontradoError(sesion.usuario_id)
        ahora = self._reloj.ahora()
        if usuario.bloqueado_hasta is not None and usuario.bloqueado_hasta > ahora:
            segundos = (usuario.bloqueado_hasta - ahora).total_seconds()
            raise CuentaBloqueadaError(max(1, ceil(segundos / 60)))
        if not self._verificador.verificar(clave_actual, usuario.hash_clave):
            await self._registrar_rechazo(usuario, usuario.id, ahora)
            raise ClaveActualIncorrectaError()
        if clave_nueva == clave_actual:
            raise ClaveRepetidaError()
        validar_politica_clave(clave_nueva)

        await self._repositorio.cambiar_clave(
            usuario.id, self._verificador.generar_hash(clave_nueva)
        )
        await self._colaboradores.registro_revocaciones.revocar(sesion.jti, sesion.expira_en)
        await self._registrar(usuario, usuario.id, "CLAVE_CAMBIADA")
        return self._colaboradores.gestor_sesion.emitir(replace(usuario, debe_cambiar_clave=False))

    async def _registrar_rechazo(self, usuario: Usuario, usuario_id: int, ahora: datetime) -> None:
        intentos = await self._repositorio.incrementar_intentos_fallidos(usuario_id)
        if intentos >= self._politica.maximo_intentos_fallidos:
            hasta = ahora + timedelta(minutes=self._politica.duracion_bloqueo_minutos)
            await self._repositorio.bloquear(usuario_id, hasta)
        await self._registrar(usuario, usuario_id, "CAMBIO_DE_CLAVE_RECHAZADO")

    async def _registrar(self, usuario: Usuario, usuario_id: int, tipo_evento: str) -> None:
        # Sin datos: ni la clave ni nada que la describa va a la bitacora.
        await self._colaboradores.registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento=tipo_evento,
                actor=usuario.nombre_usuario,
                estado_previo=None,
                estado_nuevo=None,
            )
        )
