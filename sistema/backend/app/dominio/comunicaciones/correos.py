"""Correos que la clinica recibe en su buzon de cuentas medicas (2026-11-15).

El robot de comunicaciones ya aplicaba a la cuenta los correos que traen la
comunicacion con el formato de la IAFAS. Todo lo demas -- un correo de texto
libre, uno con un PDF, uno de un remitente que no esta registrado o uno de
un comprobante desconocido -- quedaba en el buzon sin rastro en el sistema,
y la persona tenia que seguir abriendo la bandeja de correo.

Ahora cada correo recibido se registra una vez, con su remitente, asunto,
texto y adjuntos. El que no pudo aplicarse solo queda POR_REVISAR, con un
aviso, hasta que una persona lo vincula a una cuenta o lo descarta con un
motivo. Controles: solo se aplica automaticamente la comunicacion cuyo
remitente esta registrado para esa IAFAS; los adjuntos se limitan por tipo
y tamano y se guardan con su huella; cada consulta, descarga, vinculacion y
descarte queda en la bitacora (C-08)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.dominio.comunicaciones.casos_uso import ComunicacionIafas, ComunicacionRegistrada
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

LONGITUD_MAXIMA_ASUNTO = 300
LONGITUD_MAXIMA_TEXTO = 20_000
LONGITUD_MAXIMA_NOMBRE_ADJUNTO = 120
TAMANO_MAXIMO_ADJUNTO = 5 * 1024 * 1024
MAXIMO_ADJUNTOS = 10
EXTENSIONES_PERMITIDAS = frozenset(
    {"pdf", "json", "txt", "csv", "xls", "xlsx", "doc", "docx", "png", "jpg", "jpeg", "xml"}
)
LONGITUD_MINIMA_MOTIVO = 5


class ErrorCorreos(Exception):
    pass


class ErrorCorreoInexistente(ErrorCorreos):
    pass


class ErrorCorreoYaResuelto(ErrorCorreos):
    pass


class ErrorCuentaDesconocida(ErrorCorreos):
    pass


class ErrorMotivoRequerido(ErrorCorreos):
    pass


class ErrorCorreoRemitenteInvalido(ErrorCorreos):
    pass


class EstadoCorreo(StrEnum):
    PROCESADO = "PROCESADO"  # su comunicacion se aplico a la cuenta
    POR_REVISAR = "POR_REVISAR"  # una persona debe verlo
    VINCULADO = "VINCULADO"  # una persona lo asocio a una cuenta
    DESCARTADO = "DESCARTADO"  # una persona indico que no corresponde


class MotivoRevision(StrEnum):
    SIN_FORMATO = "SIN_FORMATO"
    REMITENTE_NO_REGISTRADO = "REMITENTE_NO_REGISTRADO"
    COMPROBANTE_DESCONOCIDO = "COMPROBANTE_DESCONOCIDO"


class MotivoOmision(StrEnum):
    TIPO_NO_PERMITIDO = "TIPO_NO_PERMITIDO"
    EXCEDE_TAMANO = "EXCEDE_TAMANO"
    EXCEDE_CANTIDAD = "EXCEDE_CANTIDAD"


@dataclass(frozen=True, slots=True)
class AdjuntoRecibido:
    nombre: str
    tipo: str
    contenido: bytes


@dataclass(frozen=True, slots=True)
class CorreoRecibido:
    """Un mensaje tal como lo leyo el robot del buzon de la clinica."""

    huella: str  # SHA-256 del mensaje completo: lo identifica y prueba su integridad
    remitente: str
    asunto: str
    fecha: datetime | None
    texto: str
    adjuntos: tuple[AdjuntoRecibido, ...]
    comunicacion: ComunicacionIafas | None


@dataclass(frozen=True, slots=True)
class AdjuntoEvaluado:
    nombre: str
    tipo: str
    tamano: int
    huella: str
    contenido: bytes | None  # None cuando no se almacena
    motivo_omision: MotivoOmision | None


@dataclass(frozen=True, slots=True)
class CorreoPorRegistrar:
    correo: CorreoRecibido
    codigo_iafas: str | None
    estado: EstadoCorreo
    motivo_revision: MotivoRevision | None
    comunicacion_codigo: str | None
    cuenta_medica_id: int | None
    adjuntos: tuple[AdjuntoEvaluado, ...]


@dataclass(frozen=True, slots=True)
class AdjuntoRegistrado:
    id: int
    nombre: str
    tipo: str
    tamano: int
    huella: str
    almacenado: bool
    motivo_omision: str | None


@dataclass(frozen=True, slots=True)
class CorreoRegistrado:
    id: int
    remitente: str
    codigo_iafas: str | None
    asunto: str
    fecha: datetime | None
    recibido_en: datetime
    estado: str
    motivo_revision: str | None
    comunicacion_codigo: str | None
    cuenta_medica_id: int | None
    identificacion_interna: str | None
    huella: str
    resuelto_por: str | None
    resuelto_en: datetime | None
    nota_resolucion: str | None
    cantidad_adjuntos: int
    # Solo en el detalle: la bandeja no entrega el texto ni los adjuntos.
    texto: str | None = None
    adjuntos: tuple[AdjuntoRegistrado, ...] = ()


@dataclass(frozen=True, slots=True)
class ContenidoAdjunto:
    nombre: str
    tipo: str
    huella: str
    contenido: bytes


@dataclass(frozen=True, slots=True)
class Resolucion:
    estado: EstadoCorreo
    cuenta_medica_id: int | None
    usuario: str
    instante: datetime
    nota: str | None


class ComunicacionesRegistradas(Protocol):
    """Lo unico que el registro de un correo consulta de las comunicaciones."""

    async def obtener(self, codigo: str) -> ComunicacionRegistrada | None: ...


class RepositorioCorreos(Protocol):
    async def ya_registrado(self, huella: str) -> bool: ...

    async def remitentes_por_iafas(self) -> dict[str, str]:
        """Codigo de cada IAFAS con el remitente registrado para ella."""
        ...

    async def registrar(self, correo: CorreoPorRegistrar, recibido_en: datetime) -> int: ...

    async def obtener(self, correo_id: int) -> CorreoRegistrado | None: ...

    async def listar(
        self, estado: str | None, cuenta_medica_id: int | None, limite: int = 200
    ) -> list[CorreoRegistrado]: ...

    async def contenido_adjunto(
        self, correo_id: int, adjunto_id: int
    ) -> ContenidoAdjunto | None: ...

    async def resolver(self, correo_id: int, resolucion: Resolucion) -> None: ...

    async def cuenta_por_identificacion(self, identificacion_interna: str) -> int | None: ...


def huella_de(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _extension(nombre: str) -> str:
    return nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""


def evaluar_adjuntos(adjuntos: tuple[AdjuntoRecibido, ...]) -> tuple[AdjuntoEvaluado, ...]:
    """Decide que adjuntos se almacenan. De los demas solo queda el nombre,
    el tamano y la huella: su contenido nunca entra a la base."""
    evaluados = []
    for posicion, adjunto in enumerate(adjuntos):
        motivo: MotivoOmision | None = None
        if posicion >= MAXIMO_ADJUNTOS:
            motivo = MotivoOmision.EXCEDE_CANTIDAD
        elif _extension(adjunto.nombre) not in EXTENSIONES_PERMITIDAS:
            motivo = MotivoOmision.TIPO_NO_PERMITIDO
        elif len(adjunto.contenido) > TAMANO_MAXIMO_ADJUNTO:
            motivo = MotivoOmision.EXCEDE_TAMANO
        evaluados.append(
            AdjuntoEvaluado(
                nombre=adjunto.nombre[:LONGITUD_MAXIMA_NOMBRE_ADJUNTO],
                tipo=adjunto.tipo[:100],
                tamano=len(adjunto.contenido),
                huella=huella_de(adjunto.contenido),
                contenido=adjunto.contenido if motivo is None else None,
                motivo_omision=motivo,
            )
        )
    return tuple(evaluados)


def normalizar_remitentes(valor: str | None) -> tuple[str, ...]:
    """El remitente registrado de una IAFAS: una o varias direcciones, o
    dominios escritos como @dominio, separados por coma."""
    return tuple(parte.strip().lower() for parte in (valor or "").split(",") if parte.strip())


def remitente_coincide(remitente: str, registrados: str | None) -> bool:
    direccion = remitente.strip().lower()
    for registrado in normalizar_remitentes(registrados):
        if registrado.startswith("@"):
            if direccion.endswith(registrado):
                return True
        elif direccion == registrado:
            return True
    return False


def iafas_del_remitente(remitente: str, remitentes_por_iafas: dict[str, str]) -> frozenset[str]:
    return frozenset(
        codigo
        for codigo, registrados in remitentes_por_iafas.items()
        if remitente_coincide(remitente, registrados)
    )


def comunicacion_autorizada(correo: CorreoRecibido, remitentes_por_iafas: dict[str, str]) -> bool:
    """La comunicacion adjunta solo se aplica sola cuando el remitente del
    correo esta registrado para la IAFAS que dice emitirla."""
    comunicacion = correo.comunicacion
    if comunicacion is None:
        return False
    return comunicacion.codigo_iafas in iafas_del_remitente(correo.remitente, remitentes_por_iafas)


class RegistrarCorreoIafas:
    """Registra un correo leido del buzon. La comunicacion autorizada ya fue
    aplicada por ProcesarComunicacionIafas antes de llamar a este caso."""

    def __init__(
        self,
        correos: RepositorioCorreos,
        comunicaciones: ComunicacionesRegistradas,
        reloj: Reloj,
    ) -> None:
        self._correos = correos
        self._comunicaciones = comunicaciones
        self._reloj = reloj

    async def ejecutar(self, correo: CorreoRecibido) -> EstadoCorreo | None:
        if await self._correos.ya_registrado(correo.huella):
            return None
        remitentes = await self._correos.remitentes_por_iafas()
        iafas = iafas_del_remitente(correo.remitente, remitentes)
        codigo_iafas = sorted(iafas)[0] if len(iafas) == 1 else None
        estado, motivo = EstadoCorreo.POR_REVISAR, MotivoRevision.REMITENTE_NO_REGISTRADO
        comunicacion_codigo: str | None = None
        cuenta_id: int | None = None
        if correo.comunicacion is None:
            if iafas:
                motivo = MotivoRevision.SIN_FORMATO
        elif comunicacion_autorizada(correo, remitentes):
            codigo_iafas = correo.comunicacion.codigo_iafas
            comunicacion_codigo = correo.comunicacion.codigo
            registrada = await self._comunicaciones.obtener(comunicacion_codigo)
            cuenta_id = registrada.cuenta_medica_id if registrada is not None else None
            if cuenta_id is None:
                motivo = MotivoRevision.COMPROBANTE_DESCONOCIDO
            else:
                estado = EstadoCorreo.PROCESADO
        await self._correos.registrar(
            CorreoPorRegistrar(
                correo=correo,
                codigo_iafas=codigo_iafas,
                estado=estado,
                motivo_revision=motivo if estado is EstadoCorreo.POR_REVISAR else None,
                comunicacion_codigo=comunicacion_codigo,
                cuenta_medica_id=cuenta_id,
                adjuntos=evaluar_adjuntos(correo.adjuntos),
            ),
            self._reloj.ahora(),
        )
        return estado


@dataclass(frozen=True, slots=True)
class Solicitante:
    usuario_id: int
    nombre_usuario: str


def _evento_de_sesion(
    solicitante: Solicitante, tipo_evento: str, datos: dict[str, object]
) -> Evento:
    # La consulta de un correo no pertenece a una cuenta: va al agregado de
    # sesion de quien la hizo, como el resto de la bitacora de accesos.
    return Evento(
        cuenta_medica_id=None,
        sesion_usuario_id=solicitante.usuario_id,
        tipo_evento=tipo_evento,
        actor=solicitante.nombre_usuario,
        estado_previo=None,
        estado_nuevo=None,
        datos=dict(datos),
    )


class ListarCorreosIafas:
    def __init__(self, correos: RepositorioCorreos) -> None:
        self._correos = correos

    async def ejecutar(
        self, estado: str | None, cuenta_medica_id: int | None
    ) -> list[CorreoRegistrado]:
        return await self._correos.listar(estado, cuenta_medica_id)


class ConsultarCorreoIafas:
    def __init__(self, correos: RepositorioCorreos, registro_eventos: RegistroEventos) -> None:
        self._correos = correos
        self._registro_eventos = registro_eventos

    async def ejecutar(self, correo_id: int, solicitante: Solicitante) -> CorreoRegistrado:
        correo = await self._correos.obtener(correo_id)
        if correo is None:
            raise ErrorCorreoInexistente(f"No existe el correo {correo_id}.")
        await self._registro_eventos.registrar(
            _evento_de_sesion(solicitante, "CORREO_IAFAS_CONSULTADO", {"correo_id": correo_id})
        )
        return correo


class DescargarAdjuntoCorreo:
    def __init__(self, correos: RepositorioCorreos, registro_eventos: RegistroEventos) -> None:
        self._correos = correos
        self._registro_eventos = registro_eventos

    async def ejecutar(
        self, correo_id: int, adjunto_id: int, solicitante: Solicitante
    ) -> ContenidoAdjunto:
        adjunto = await self._correos.contenido_adjunto(correo_id, adjunto_id)
        if adjunto is None:
            raise ErrorCorreoInexistente("No existe el adjunto o su contenido no se almacenó.")
        if huella_de(adjunto.contenido) != adjunto.huella:
            raise ErrorCorreos("El adjunto no coincide con la huella registrada al recibirlo.")
        await self._registro_eventos.registrar(
            _evento_de_sesion(
                solicitante,
                "ADJUNTO_CORREO_IAFAS_DESCARGADO",
                {"correo_id": correo_id, "adjunto_id": adjunto_id, "huella": adjunto.huella},
            )
        )
        return adjunto


class VincularCorreoIafas:
    def __init__(
        self, correos: RepositorioCorreos, registro_eventos: RegistroEventos, reloj: Reloj
    ) -> None:
        self._correos = correos
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(
        self, correo_id: int, identificacion_interna: str, solicitante: Solicitante
    ) -> CorreoRegistrado:
        identificacion = identificacion_interna.strip()
        correo = await self._correos.obtener(correo_id)
        if correo is None:
            raise ErrorCorreoInexistente(f"No existe el correo {correo_id}.")
        if correo.estado != EstadoCorreo.POR_REVISAR:
            raise ErrorCorreoYaResuelto("El correo ya fue revisado.")
        cuenta_id = await self._correos.cuenta_por_identificacion(identificacion)
        if cuenta_id is None:
            raise ErrorCuentaDesconocida(f"No existe la cuenta {identificacion}.")
        await self._correos.resolver(
            correo_id,
            Resolucion(
                estado=EstadoCorreo.VINCULADO,
                cuenta_medica_id=cuenta_id,
                usuario=solicitante.nombre_usuario,
                instante=self._reloj.ahora(),
                nota=None,
            ),
        )
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="CORREO_IAFAS_VINCULADO",
                actor=solicitante.nombre_usuario,
                estado_previo=None,
                estado_nuevo=None,
                datos={"correo_id": correo_id, "huella": correo.huella},
            )
        )
        actualizado = await self._correos.obtener(correo_id)
        assert actualizado is not None
        return actualizado


class DescartarCorreoIafas:
    def __init__(
        self, correos: RepositorioCorreos, registro_eventos: RegistroEventos, reloj: Reloj
    ) -> None:
        self._correos = correos
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(
        self, correo_id: int, motivo: str, solicitante: Solicitante
    ) -> CorreoRegistrado:
        motivo = motivo.strip()[:300]
        if len(motivo) < LONGITUD_MINIMA_MOTIVO:
            raise ErrorMotivoRequerido("Indique el motivo por el que el correo no corresponde.")
        correo = await self._correos.obtener(correo_id)
        if correo is None:
            raise ErrorCorreoInexistente(f"No existe el correo {correo_id}.")
        if correo.estado != EstadoCorreo.POR_REVISAR:
            raise ErrorCorreoYaResuelto("El correo ya fue revisado.")
        await self._correos.resolver(
            correo_id,
            Resolucion(
                estado=EstadoCorreo.DESCARTADO,
                cuenta_medica_id=None,
                usuario=solicitante.nombre_usuario,
                instante=self._reloj.ahora(),
                nota=motivo,
            ),
        )
        await self._registro_eventos.registrar(
            _evento_de_sesion(
                solicitante,
                "CORREO_IAFAS_DESCARTADO",
                {"correo_id": correo_id, "huella": correo.huella, "motivo": motivo},
            )
        )
        actualizado = await self._correos.obtener(correo_id)
        assert actualizado is not None
        return actualizado


def validar_remitentes(valor: str | None) -> str | None:
    """Acepta direcciones completas o dominios escritos como @dominio."""
    partes = normalizar_remitentes(valor)
    if not partes:
        return None
    for parte in partes:
        _, arroba, dominio = parte.partition("@")
        if not arroba or "." not in dominio or " " in parte or "@" in dominio:
            raise ErrorCorreoRemitenteInvalido(
                f"«{parte}» no es una dirección de correo ni un dominio escrito como @dominio."
            )
    unido = ", ".join(partes)
    if len(unido) > 200:
        raise ErrorCorreoRemitenteInvalido("El remitente registrado supera los 200 caracteres.")
    return unido
