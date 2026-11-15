"""Pruebas unitarias de los casos de uso de acceso, con un repositorio falso
en memoria: no dependen de SQLAlchemy ni de una base de datos (Seccion 12.1).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.dominio.acceso.casos_uso import (
    ActualizarUsuario,
    CerrarSesion,
    ColaboradoresIniciarSesion,
    IniciarSesion,
    ListarUsuarios,
    PoliticaBloqueoSesion,
    RegistrarUsuario,
)
from app.dominio.acceso.entidades import NombreRol, Usuario
from app.dominio.acceso.errores import (
    ClaveDebilError,
    CredencialesInvalidasError,
    CuentaBloqueadaError,
    NombreUsuarioDuplicadoError,
    RolesRequeridosError,
    UsuarioNoEncontradoError,
)
from app.dominio.acceso.puertos import (
    CargaSesion,
    GestorSesion,
    RegistroRevocaciones,
    RepositorioUsuarios,
    VerificadorClave,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos

_AHORA = datetime(2026, 1, 1, 10, 0, 0)
# Control C-01 (Seccion 5.2.7): cinco intentos, quince minutos de bloqueo --
# los mismos valores por defecto de Configuracion (app/compartido/configuracion.py).
_POLITICA_BLOQUEO = PoliticaBloqueoSesion(maximo_intentos_fallidos=5, duracion_bloqueo_minutos=15)


class _RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante


def _iniciar_sesion(
    repositorio: RepositorioUsuariosFalso,
    verificador: VerificadorClaveFalso,
    instante: datetime = _AHORA,
    politica: PoliticaBloqueoSesion = _POLITICA_BLOQUEO,
    registro_eventos: RegistroEventos | None = None,
) -> IniciarSesion:
    colaboradores = ColaboradoresIniciarSesion(
        gestor_sesion=GestorSesionFalso(),
        registro_eventos=registro_eventos
        if registro_eventos is not None
        else RegistroEventosFalso(),
    )
    return IniciarSesion(repositorio, verificador, colaboradores, _RelojFijo(instante), politica)


class RepositorioUsuariosFalso(RepositorioUsuarios):
    def __init__(self) -> None:
        self._usuarios: dict[str, Usuario] = {}
        self._siguiente_id = 1

    async def obtener_por_nombre_usuario(self, nombre_usuario: str) -> Usuario | None:
        return self._usuarios.get(nombre_usuario)

    async def obtener_por_id(self, usuario_id: int) -> Usuario | None:
        return next((u for u in self._usuarios.values() if u.id == usuario_id), None)

    async def listar(self) -> list[Usuario]:
        return sorted(self._usuarios.values(), key=lambda u: u.nombre_usuario)

    async def crear(self, usuario: Usuario) -> Usuario:
        creado = Usuario(
            id=self._siguiente_id,
            nombre_usuario=usuario.nombre_usuario,
            nombres=usuario.nombres,
            hash_clave=usuario.hash_clave,
            activo=usuario.activo,
            roles=usuario.roles,
        )
        self._siguiente_id += 1
        self._usuarios[creado.nombre_usuario] = creado
        return creado

    async def actualizar(
        self,
        usuario_id: int,
        nombres: str | None = None,
        roles: frozenset[NombreRol] | None = None,
        activo: bool | None = None,
    ) -> Usuario | None:
        actual = await self.obtener_por_id(usuario_id)
        if actual is None:
            return None
        actualizado = Usuario(
            id=actual.id,
            nombre_usuario=actual.nombre_usuario,
            nombres=nombres if nombres is not None else actual.nombres,
            hash_clave=actual.hash_clave,
            activo=activo if activo is not None else actual.activo,
            roles=roles if roles is not None else actual.roles,
            # El adaptador real (RepositorioUsuariosSql.actualizar) solo
            # modifica nombres/activo/roles en la fila; intentos_fallidos
            # y bloqueado_hasta quedan intactos. Este falso reproduce lo
            # mismo, en vez de resetearlos a los valores por defecto.
            intentos_fallidos=actual.intentos_fallidos,
            bloqueado_hasta=actual.bloqueado_hasta,
        )
        self._usuarios[actual.nombre_usuario] = actualizado
        return actualizado

    async def incrementar_intentos_fallidos(self, usuario_id: int) -> int:
        actual = await self.obtener_por_id(usuario_id)
        assert actual is not None
        actualizado = Usuario(
            id=actual.id,
            nombre_usuario=actual.nombre_usuario,
            nombres=actual.nombres,
            hash_clave=actual.hash_clave,
            activo=actual.activo,
            roles=actual.roles,
            intentos_fallidos=actual.intentos_fallidos + 1,
            bloqueado_hasta=actual.bloqueado_hasta,
        )
        self._usuarios[actual.nombre_usuario] = actualizado
        return actualizado.intentos_fallidos

    async def bloquear(self, usuario_id: int, hasta: datetime) -> None:
        actual = await self.obtener_por_id(usuario_id)
        assert actual is not None
        self._usuarios[actual.nombre_usuario] = Usuario(
            id=actual.id,
            nombre_usuario=actual.nombre_usuario,
            nombres=actual.nombres,
            hash_clave=actual.hash_clave,
            activo=actual.activo,
            roles=actual.roles,
            intentos_fallidos=actual.intentos_fallidos,
            bloqueado_hasta=hasta,
        )

    async def registrar_inicio_exitoso(self, usuario_id: int) -> None:
        actual = await self.obtener_por_id(usuario_id)
        assert actual is not None
        self._usuarios[actual.nombre_usuario] = Usuario(
            id=actual.id,
            nombre_usuario=actual.nombre_usuario,
            nombres=actual.nombres,
            hash_clave=actual.hash_clave,
            activo=actual.activo,
            roles=actual.roles,
            intentos_fallidos=0,
            bloqueado_hasta=None,
        )


class VerificadorClaveFalso(VerificadorClave):
    """No usa bcrypt: prefija el hash para que las pruebas sean instantaneas."""

    def generar_hash(self, clave: str) -> str:
        return f"hash::{clave}"

    def verificar(self, clave: str, hash_clave: str) -> bool:
        return hash_clave == f"hash::{clave}"


class GestorSesionFalso(GestorSesion):
    def emitir(self, usuario: Usuario) -> str:
        assert usuario.id is not None
        return f"token::{usuario.id}"

    def verificar(self, token: str) -> CargaSesion:
        raise NotImplementedError("no usado en estas pruebas")


class RegistroRevocacionesFalso(RegistroRevocaciones):
    def __init__(self) -> None:
        self.revocados: dict[str, datetime] = {}

    async def revocar(self, jti: str, expira_en: datetime) -> None:
        self.revocados[jti] = expira_en

    async def esta_revocado(self, jti: str) -> bool:
        return jti in self.revocados


class RegistroEventosFalso(RegistroEventos):
    def __init__(self) -> None:
        self.eventos: list[Evento] = []

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@pytest.fixture
def repositorio() -> RepositorioUsuariosFalso:
    return RepositorioUsuariosFalso()


@pytest.fixture
def verificador() -> VerificadorClaveFalso:
    return VerificadorClaveFalso()


async def prueba_registrar_y_luego_iniciar_sesion(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    registrar = RegistrarUsuario(repositorio, verificador)
    usuario = await registrar.ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    assert usuario.id is not None

    registro_eventos = RegistroEventosFalso()
    token = await _iniciar_sesion(
        repositorio, verificador, registro_eventos=registro_eventos
    ).ejecutar("ana.analista", "Clave-Valida-123")
    assert token == f"token::{usuario.id}"

    # RT-08/control C-08 (Fase 29): la bitacora de accesos se lee del
    # almacen de eventos -- el inicio de sesion exitoso queda registrado.
    assert registro_eventos.eventos[0].tipo_evento == "SESION_INICIADA"
    assert registro_eventos.eventos[0].sesion_usuario_id == usuario.id
    assert registro_eventos.eventos[0].actor == "ana.analista"


async def prueba_iniciar_sesion_con_clave_incorrecta_falla(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    with pytest.raises(CredencialesInvalidasError):
        await _iniciar_sesion(repositorio, verificador).ejecutar("ana.analista", "clave-equivocada")


async def prueba_iniciar_sesion_con_usuario_inexistente_falla(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    with pytest.raises(CredencialesInvalidasError):
        await _iniciar_sesion(repositorio, verificador).ejecutar("no.existe", "cualquiera")


async def prueba_iniciar_sesion_con_usuario_inactivo_falla(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    usuario = await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    repositorio._usuarios[usuario.nombre_usuario] = Usuario(
        id=usuario.id,
        nombre_usuario=usuario.nombre_usuario,
        nombres=usuario.nombres,
        hash_clave=usuario.hash_clave,
        activo=False,
        roles=usuario.roles,
    )

    with pytest.raises(CredencialesInvalidasError):
        await _iniciar_sesion(repositorio, verificador).ejecutar("ana.analista", "Clave-Valida-123")


async def prueba_registrar_usuario_duplicado_falla(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    registrar = RegistrarUsuario(repositorio, verificador)
    await registrar.ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    with pytest.raises(NombreUsuarioDuplicadoError):
        await registrar.ejecutar(
            nombre_usuario="ana.analista",
            clave="Otra-Clave-123",
            nombres="Otra Persona",
            roles=frozenset({NombreRol.AUDITOR}),
        )


async def prueba_registrar_usuario_sin_roles_falla(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    registrar = RegistrarUsuario(repositorio, verificador)
    with pytest.raises(RolesRequeridosError):
        await registrar.ejecutar(
            nombre_usuario="ana.analista",
            clave="Clave-Valida-123",
            nombres="Ana Analista",
            roles=frozenset(),
        )


@pytest.mark.parametrize(
    "clave",
    [
        "Corta1",  # menos de doce caracteres
        "clave-valida-123",  # sin mayuscula
        "CLAVE-VALIDA-123",  # sin minuscula
        "Clave-Valida-sss",  # sin digito
    ],
)
async def prueba_registrar_usuario_con_clave_debil_falla(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso, clave: str
) -> None:
    """Control C-01 (Seccion 5.2.7): doce caracteres, con mayuscula,
    minuscula y digito."""
    with pytest.raises(ClaveDebilError):
        await RegistrarUsuario(repositorio, verificador).ejecutar(
            nombre_usuario="ana.analista",
            clave=clave,
            nombres="Ana Analista",
            roles=frozenset({NombreRol.ANALISTA}),
        )


async def prueba_listar_usuarios_devuelve_los_registrados(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    registrar = RegistrarUsuario(repositorio, verificador)
    await registrar.ejecutar(
        nombre_usuario="beto.jefe",
        clave="Clave-Valida-123",
        nombres="Beto Jefe",
        roles=frozenset({NombreRol.JEFE}),
    )
    await registrar.ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )

    usuarios = await ListarUsuarios(repositorio).ejecutar()
    assert [u.nombre_usuario for u in usuarios] == ["ana.analista", "beto.jefe"]


async def prueba_desactivar_usuario_le_impide_iniciar_sesion(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    usuario = await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    assert usuario.id is not None

    await ActualizarUsuario(repositorio).ejecutar(usuario.id, activo=False)

    with pytest.raises(CredencialesInvalidasError):
        await _iniciar_sesion(repositorio, verificador).ejecutar("ana.analista", "Clave-Valida-123")


async def prueba_actualizar_usuario_cambia_nombres_y_roles(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    usuario = await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    assert usuario.id is not None

    actualizado = await ActualizarUsuario(repositorio).ejecutar(
        usuario.id, nombres="Ana Maria Analista", roles=frozenset({NombreRol.AUDITOR})
    )
    assert actualizado.nombres == "Ana Maria Analista"
    assert actualizado.roles == frozenset({NombreRol.AUDITOR})
    assert actualizado.activo is True


async def prueba_actualizar_usuario_inexistente_falla(
    repositorio: RepositorioUsuariosFalso,
) -> None:
    with pytest.raises(UsuarioNoEncontradoError):
        await ActualizarUsuario(repositorio).ejecutar(999, nombres="Quien Sea")


async def prueba_actualizar_usuario_con_roles_vacios_falla(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    usuario = await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    assert usuario.id is not None
    with pytest.raises(RolesRequeridosError):
        await ActualizarUsuario(repositorio).ejecutar(usuario.id, roles=frozenset())


# --- Control C-01 (Seccion 5.2.7): bloqueo por intentos fallidos --------


async def prueba_iniciar_sesion_bloquea_tras_cinco_intentos_fallidos(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    caso_uso = _iniciar_sesion(repositorio, verificador)

    for _ in range(5):
        with pytest.raises(CredencialesInvalidasError):
            await caso_uso.ejecutar("ana.analista", "clave-equivocada")

    with pytest.raises(CuentaBloqueadaError) as excepcion:
        await caso_uso.ejecutar("ana.analista", "clave-equivocada")
    assert excepcion.value.minutos_restantes == 15


async def prueba_cuenta_bloqueada_rechaza_incluso_la_clave_correcta(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    """La cuenta bloqueada no admite ningun intento, ni siquiera con la
    clave correcta: si no fuera asi, el bloqueo no protegeria nada."""
    await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    caso_uso = _iniciar_sesion(repositorio, verificador)
    for _ in range(5):
        with pytest.raises(CredencialesInvalidasError):
            await caso_uso.ejecutar("ana.analista", "clave-equivocada")

    with pytest.raises(CuentaBloqueadaError):
        await caso_uso.ejecutar("ana.analista", "Clave-Valida-123")


async def prueba_cuenta_se_desbloquea_pasado_el_plazo(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    for _ in range(5):
        with pytest.raises(CredencialesInvalidasError):
            await _iniciar_sesion(repositorio, verificador).ejecutar(
                "ana.analista", "clave-equivocada"
            )

    # Dieciseis minutos despues (un minuto pasado el bloqueo de quince):
    # un reloj distinto, no el mismo caso de uso, porque IniciarSesion
    # recibe su reloj en el constructor (Seccion 2.2, objeto de parametros).
    despues_del_bloqueo = _AHORA + timedelta(minutes=16)
    token = await _iniciar_sesion(repositorio, verificador, instante=despues_del_bloqueo).ejecutar(
        "ana.analista", "Clave-Valida-123"
    )
    assert token.startswith("token::")


async def prueba_inicio_exitoso_reinicia_el_contador_de_intentos_fallidos(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    caso_uso = _iniciar_sesion(repositorio, verificador)
    for _ in range(3):
        with pytest.raises(CredencialesInvalidasError):
            await caso_uso.ejecutar("ana.analista", "clave-equivocada")

    await caso_uso.ejecutar("ana.analista", "Clave-Valida-123")

    usuario = await repositorio.obtener_por_nombre_usuario("ana.analista")
    assert usuario is not None
    assert usuario.intentos_fallidos == 0
    assert usuario.bloqueado_hasta is None

    # Tres intentos fallidos mas, tras el reinicio, no deberian alcanzar
    # el bloqueo (harian falta cinco de nuevo).
    for _ in range(3):
        with pytest.raises(CredencialesInvalidasError):
            await caso_uso.ejecutar("ana.analista", "clave-equivocada")
    usuario = await repositorio.obtener_por_nombre_usuario("ana.analista")
    assert usuario is not None
    assert usuario.bloqueado_hasta is None


# --- Control C-01 (Seccion 5.2.7): revocacion al cerrar sesion ----------


async def prueba_cerrar_sesion_revoca_el_token() -> None:
    registro_eventos = RegistroEventosFalso()
    registro_revocaciones = RegistroRevocacionesFalso()
    expira_en = _AHORA + timedelta(minutes=60)

    await CerrarSesion(registro_eventos, registro_revocaciones).ejecutar(
        "ana.analista", 1, "jti-de-prueba", expira_en
    )

    assert await registro_revocaciones.esta_revocado("jti-de-prueba") is True
    assert registro_revocaciones.revocados["jti-de-prueba"] == expira_en
    assert [e.tipo_evento for e in registro_eventos.eventos] == ["SESION_CERRADA"]


async def prueba_un_ingreso_rechazado_queda_en_la_bitacora(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    """RF-20, C-08 y RT-08: el ingreso rechazado tambien se registra, con
    su motivo; un nombre inexistente va al agregado 0."""
    usuario = await RegistrarUsuario(repositorio, verificador).ejecutar(
        nombre_usuario="ana.analista",
        clave="Clave-Valida-123",
        nombres="Ana Analista",
        roles=frozenset({NombreRol.ANALISTA}),
    )
    registro_eventos = RegistroEventosFalso()
    caso_uso = _iniciar_sesion(repositorio, verificador, registro_eventos=registro_eventos)
    for nombre, clave in (("ana.analista", "otra-clave"), ("no.existe", "x")):
        with pytest.raises(CredencialesInvalidasError):
            await caso_uso.ejecutar(nombre, clave)

    rechazos = [
        (e.tipo_evento, e.sesion_usuario_id, e.datos["motivo"]) for e in registro_eventos.eventos
    ]
    assert rechazos == [
        ("SESION_RECHAZADA", usuario.id, "clave_incorrecta"),
        ("SESION_RECHAZADA", 0, "usuario_inexistente"),
    ]


async def prueba_administracion_de_usuarios_queda_en_la_bitacora(
    repositorio: RepositorioUsuariosFalso, verificador: VerificadorClaveFalso
) -> None:
    """CU-18: alta, cambio y desactivacion dejan un evento en el agregado
    de sesion del usuario administrado, sin sus nombres (C-11)."""
    registro_eventos = RegistroEventosFalso()
    usuario = await RegistrarUsuario(repositorio, verificador, registro_eventos).ejecutar(
        nombre_usuario="teo.tesoreria",
        clave="Clave-Valida-123",
        nombres="Teo Tesoreria",
        roles=frozenset({NombreRol.TESORERIA}),
        actor="admin.prueba",
    )
    assert usuario.id is not None
    actualizar = ActualizarUsuario(repositorio, registro_eventos)
    await actualizar.ejecutar(usuario.id, nombres="Teo T.", actor="admin.prueba")
    await actualizar.ejecutar(usuario.id, activo=False, actor="admin.prueba")

    tipos = [e.tipo_evento for e in registro_eventos.eventos]
    assert tipos == ["USUARIO_CREADO", "USUARIO_ACTUALIZADO", "USUARIO_DESACTIVADO"]
    assert all(e.sesion_usuario_id == usuario.id for e in registro_eventos.eventos)
    assert all(e.actor == "admin.prueba" for e in registro_eventos.eventos)
    assert registro_eventos.eventos[0].datos["roles"] == ["tesoreria"]
    assert registro_eventos.eventos[1].datos["campos"] == ["nombres"]
    assert all("nombres" not in e.datos for e in registro_eventos.eventos)
