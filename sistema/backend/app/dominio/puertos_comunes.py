"""Puertos de dominio compartidos por mas de un contexto (Seccion 5.2: la fila
'Puerto y adaptador' de la tabla de patrones incluye 'reloj' junto a
acreditacion, transmision, catalogo y repositorios).

No confundir con `app/compartido/`, que son utilidades de infraestructura
(configuracion de despliegue, formato de error HTTP) sin reglas de negocio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


class Reloj(Protocol):
    """Fuente del instante actual. Permite fijar el tiempo en las pruebas
    (por ejemplo, para verificar la expiracion de una sesion) sin depender
    de time.sleep ni de datetime.now() directo en el dominio."""

    def ahora(self) -> datetime: ...


# Control C-11 (Seccion 5.2.7 de la tesis, RNF-10): "los datos adicionales
# solo contienen referencias a entidades del sistema y no admiten datos
# personales del asegurado". Diccionario revisado de claves que un payload
# de evento nunca debe llevar -- los nombres de campo que, en el resto del
# dominio (AseguradoModelo, CuentaMedicaModelo), identifican a la persona
# o a su atencion, no a un identificador o codigo operativo. Se verifica
# por clave, no por contenido: el payload de un evento son siempre
# identificadores, codigos y textos operativos (motivos, nombres de
# archivo), nunca los datos del paciente en si.
_CLAVES_PERSONALES_PROHIBIDAS: frozenset[str] = frozenset(
    {
        "nombres",
        "apellidos",
        "nombres_asegurado",
        "apellidos_asegurado",
        "tipo_documento",
        "numero_documento",
        "tipo_documento_asegurado",
        "numero_documento_asegurado",
        "documento_paciente",
        "documento_asegurado",
        "numero_historia_clinica",
        "diagnostico_principal_cie10",
        "diagnosticos_secundarios_cie10",
        "fecha_nacimiento",
        "direccion",
        "telefono",
        "correo",
        "email",
    }
)


class ErrorEventoConDatosPersonales(Exception):
    """Un caso de uso intento registrar, en el payload de un evento, una
    clave del diccionario `_CLAVES_PERSONALES_PROHIBIDAS` (control C-11)."""


class ErrorEventoSinAgregado(Exception):
    """Fase 24 (Seccion 6.2.2, Tabla 68): todo evento pertenece a
    exactamente un agregado -- la cuenta, el lote, la sesion de usuario o
    la sesion de plataforma -- nunca a cero ni a mas de uno."""


# Fase 24: los cuatro tipos de agregado del almacen de eventos. Los dos
# primeros son los del motor de orquestacion (Seccion 6.2.2); los otros
# dos ya existian como eventos sin agregado explicito desde el OE1
# (sesion de usuario, sesion asistida de plataforma) y se formalizan aqui
# para que ningun evento quede sin tipo_agregado/agregado_id.
TIPO_AGREGADO_CUENTA = "CUENTA"
TIPO_AGREGADO_LOTE = "LOTE"
TIPO_AGREGADO_SESION_USUARIO = "SESION_USUARIO"
TIPO_AGREGADO_SESION_PLATAFORMA = "SESION_PLATAFORMA"


def _contiene_clave_prohibida(valor: object) -> bool:
    if isinstance(valor, dict):
        return any(
            str(clave).lower() in _CLAVES_PERSONALES_PROHIBIDAS or _contiene_clave_prohibida(sub)
            for clave, sub in valor.items()
        )
    if isinstance(valor, list | tuple):
        return any(_contiene_clave_prohibida(elemento) for elemento in valor)
    return False


@dataclass(frozen=True, slots=True)
class Evento:
    """RF-16, Seccion 6.3 y 6.2.2 (Fase 24): registro de solo insercion, un
    evento por cada transicion. Exactamente uno de los cuatro campos de
    agregado debe venir dado; el adaptador de persistencia (Fase 24) lo
    traduce a tipo_agregado/agregado_id antes de calcular `version` y
    `hash_evento`, que no son responsabilidad del dominio (dependen de lo
    que ya hay guardado)."""

    cuenta_medica_id: int | None
    tipo_evento: str
    actor: str
    estado_previo: str | None
    estado_nuevo: str | None
    datos: dict[str, Any] = field(default_factory=dict)
    # Control C-07/C-01 (Seccion 5.2.7, "custodia de credenciales externas
    # y atribucion"): cuando `actor` es el proceso de automatizacion, este
    # es el usuario interno que solicito la operacion -- None cuando el
    # propio actor ya es una persona (la mayoria de los eventos que no
    # pasan por la cola de trabajos).
    usuario_origen: str | None = None
    # Fase 24: los otros tres agregados posibles, ademas de
    # cuenta_medica_id. Un evento del motor de orquestacion sobre un lote
    # usa lote_id; los dos de sesion son preexistentes del OE1.
    lote_id: int | None = None
    sesion_usuario_id: int | None = None
    sesion_plataforma_id: int | None = None

    def __post_init__(self) -> None:
        if _contiene_clave_prohibida(self.datos):
            raise ErrorEventoConDatosPersonales(
                f"El evento {self.tipo_evento!r} intenta registrar en su payload una clave "
                "de datos personales del asegurado; el almacen de eventos solo admite "
                "referencias a entidades del sistema (control C-11)."
            )
        agregados = (
            self.cuenta_medica_id,
            self.lote_id,
            self.sesion_usuario_id,
            self.sesion_plataforma_id,
        )
        if sum(1 for valor in agregados if valor is not None) != 1:
            raise ErrorEventoSinAgregado(
                f"El evento {self.tipo_evento!r} debe pertenecer a exactamente un agregado "
                "(cuenta, lote, sesion de usuario o sesion de plataforma)."
            )

    @property
    def tipo_agregado(self) -> str:
        if self.cuenta_medica_id is not None:
            return TIPO_AGREGADO_CUENTA
        if self.lote_id is not None:
            return TIPO_AGREGADO_LOTE
        if self.sesion_usuario_id is not None:
            return TIPO_AGREGADO_SESION_USUARIO
        return TIPO_AGREGADO_SESION_PLATAFORMA

    @property
    def agregado_id(self) -> int:
        # `or` encadenado trataria un id legitimo 0 (centinela de prueba,
        # ver pruebas_integracion/prueba_inmutabilidad_evento.py) como
        # "no dado" y seguiria al siguiente campo -- por eso `is not None`
        # explicito en vez de la cadena corta habitual.
        for valor in (
            self.cuenta_medica_id,
            self.lote_id,
            self.sesion_usuario_id,
            self.sesion_plataforma_id,
        ):
            if valor is not None:
                return valor
        raise AssertionError("inalcanzable: garantizado por __post_init__")


class RegistroEventos(Protocol):
    """Puerto de la Seccion 6.3: el OE3 puede sustituir la implementacion
    sin tocar el OE1. Ningun caso de uso escribe la tabla evento directo."""

    async def registrar(self, evento: Evento) -> None: ...


@dataclass(frozen=True, slots=True)
class MedicionPaso:
    """Seccion 6.4: una fila por ejecucion de paso automatizado, nunca un
    promedio. El OE1 solo puebla esta tabla; no agrega ni proyecta."""

    paso: str
    inicio: datetime
    fin: datetime
    actor: str
    resultado: str
    cuenta_medica_id: int | None = None
    lote_id: int | None = None
    datos: dict[str, Any] = field(default_factory=dict)

    @property
    def duracion_ms(self) -> int:
        return int((self.fin - self.inicio).total_seconds() * 1000)


class RegistroMediciones(Protocol):
    """Puerto de la Seccion 6.4: implementado en infraestructura."""

    async def registrar(self, medicion: MedicionPaso) -> None: ...


@dataclass(frozen=True, slots=True)
class Observabilidad:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): agrupa
    los dos puertos de registro que casi todo caso de uso recibe juntos,
    para no superar el limite de 5 parametros por funcion (Seccion 3)
    cuando el caso de uso ademas necesita mas de un repositorio (por
    ejemplo RemitirLote, Fase 13: repositorio de remision, transmisor,
    repositorio de trabajos, reloj y esta observabilidad)."""

    eventos: RegistroEventos
    mediciones: RegistroMediciones


@dataclass(frozen=True, slots=True)
class TrabajoPendiente:
    """Lo que devuelve `RepositorioTrabajos.tomar_siguiente` (Seccion 5.2:
    cola transaccional, tabla `trabajo` con `SELECT ... FOR UPDATE SKIP
    LOCKED`) -- ya marcado EN_PROCESO por el propio repositorio.
    `creado_en` es el instante en que se encolo (no el de esta toma en
    particular): la Fase 12 lo usa para calcular si ya se supero la
    ventana maxima de espera de un monitoreo (Seccion 8.3, punto 5)."""

    id: int
    tipo: str
    carga_util: dict[str, Any]
    intentos: int
    creado_en: datetime


@dataclass(frozen=True, slots=True)
class DetalleTrabajo:
    """Lo que devuelve `RepositorioTrabajos.obtener` (Fase 18, `GET
    /trabajos/{id}`): el estado completo de una fila de la cola, no solo
    lo que necesita quien la toma para procesarla (a diferencia de
    `TrabajoPendiente`)."""

    id: int
    tipo: str
    carga_util: dict[str, Any]
    estado: str
    intentos: int
    error: str | None
    creado_en: datetime
    actualizado_en: datetime


class RepositorioTrabajos(Protocol):
    """Puerto de la cola (Seccion 6.1, AD-02/AD-03): tanto quien encola
    (`RemitirLote`, `SolicitarVerificacionCobertura`) como quien consume
    (el trabajador de `sistema/automatizacion/`, en un proceso aparte que
    importa este mismo paquete) usan el mismo puerto y el mismo adaptador
    -- la tabla vive en un solo lugar, con una sola forma de tomarla y
    liberarla."""

    async def encolar(
        self, tipo: str, carga_util: dict[str, Any], proximo_intento: datetime
    ) -> int:
        """Devuelve el id del trabajo creado, en estado PENDIENTE."""
        ...

    async def obtener(self, trabajo_id: int) -> DetalleTrabajo | None:
        """None si no existe ese trabajo (Fase 18, `GET /trabajos/{id}`:
        seguimiento de un trabajo encolado por cualquier caso de uso)."""
        ...

    async def tomar_siguiente(self, tipos: tuple[str, ...]) -> TrabajoPendiente | None:
        """None si no hay ningun trabajo PENDIENTE de esos tipos con
        `proximo_intento` ya vencido. Si hay uno, lo marca EN_PROCESO
        dentro de la misma transaccion que lo toma (SELECT ... FOR UPDATE
        SKIP LOCKED), para que dos trabajadores nunca tomen el mismo."""
        ...

    async def marcar_completado(self, trabajo_id: int) -> None: ...

    async def marcar_para_reintento(
        self, trabajo_id: int, error: str, proximo_intento: datetime
    ) -> None:
        """Vuelve a PENDIENTE (no se pierde, Seccion 8.1 punto 6) e
        incrementa `intentos`."""
        ...

    async def marcar_agotado(self, trabajo_id: int, error: str) -> None:
        """Superado el maximo de reintentos configurado; requiere
        intervencion o reencolado manual."""
        ...

    async def marcar_requiere_sesion(self, trabajo_id: int, motivo: str | None = None) -> None:
        """Seccion 8.4, punto 6: 'si no la hay o expiro, el trabajo pasa
        a REQUIERE_SESION, sin consumir intentos'. "motivo" queda en
        "error" para que la pantalla de detalle lo muestre (antes se
        perdia: solo quedaba en el log del trabajador)."""
        ...

    async def reactivar_requieren_sesion(self, tipos: tuple[str, ...]) -> int:
        """Seccion 8.4, punto 6: 'al activarse una sesion, los trabajos
        en REQUIERE_SESION de esa plataforma vuelven a PENDIENTE'.
        Devuelve cuantos trabajos reactivo."""
        ...

    async def hay_sin_terminar(self, tipo: str, lote_id: int) -> bool:
        """True si ese lote tiene un trabajo de ese tipo todavia
        PENDIENTE, EN_PROCESO o REQUIERE_SESION (evita encolar dos
        iguales)."""
        ...

    async def adelantar(self, tipo: str, lote_id: int) -> int | None:
        """Deja para ahora el trabajo PENDIENTE de ese tipo y lote y
        devuelve su id; None si no hay ninguno en espera."""
        ...
