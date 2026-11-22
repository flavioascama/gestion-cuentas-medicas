"""RF-13 y CU-06: la carta de garantia de la IAFAS, con su numero, su
vigencia y su monto, registrada desde el detalle de la cuenta. Hasta la
verificacion de cumplimiento del 2026-11-12 no existia como documento: el
aviso de vencimiento usaba la vigencia de la acreditacion como sustituto,
que sigue valiendo para las cuentas sin carta registrada."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.compartido.nombres_estados import nombre_estado
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

# Auditoria final (hallazgo 11): la carta se registra y se corrige en los
# mismos estados. Su numero viaja en la trama del lote (T2, campos 14 y 15):
# no cambia en una cuenta ya enviada. En Rechazada si, porque el rechazo
# puede deberse a la carta, antes del reenvio. Cada correccion queda como un
# evento nuevo.
ESTADOS_CARTA = frozenset({"REGISTRADA", "RECHAZADA"})
_EN_QUE_ESTADOS = "mientras la cuenta está Registrada o Rechazada"
TIPO_EVENTO_CARTA_CORREGIDA = "CARTA_GARANTIA_CORREGIDA"
LONGITUD_MAXIMA_NUMERO = 30


class ErrorCartaGarantia(Exception):
    pass


class ErrorCuentaInexistenteCarta(ErrorCartaGarantia):
    pass


class ErrorCuentaSinRegistroCarta(ErrorCartaGarantia):
    pass


class ErrorCartaGarantiaYaRegistrada(ErrorCartaGarantia):
    pass


class ErrorCartaGarantiaInvalida(ErrorCartaGarantia):
    pass


class ErrorCartaGarantiaInexistente(ErrorCartaGarantia):
    pass


class ErrorCartaGarantiaNoCorregible(ErrorCartaGarantia):
    pass


@dataclass(frozen=True, slots=True)
class DatosCartaGarantia:
    numero: str
    vigente_desde: date
    vigente_hasta: date
    monto: Decimal


@dataclass(frozen=True, slots=True)
class CartaGarantia:
    cuenta_medica_id: int
    numero: str
    vigente_desde: date
    vigente_hasta: date
    monto: Decimal
    registrado_en: datetime
    registrado_por: str


class RepositorioCartaGarantia(Protocol):
    async def obtener(self, cuenta_medica_id: int) -> CartaGarantia | None: ...

    async def guardar(self, carta: CartaGarantia) -> None: ...

    async def actualizar(self, carta: CartaGarantia) -> None:
        """Reemplaza numero, vigencia y monto de la carta de la cuenta."""
        ...


def _validar(datos: DatosCartaGarantia) -> None:
    numero = datos.numero.strip()
    if not numero or len(numero) > LONGITUD_MAXIMA_NUMERO:
        raise ErrorCartaGarantiaInvalida(
            f"El número de la carta es obligatorio (hasta {LONGITUD_MAXIMA_NUMERO} caracteres)."
        )
    if datos.vigente_hasta < datos.vigente_desde:
        raise ErrorCartaGarantiaInvalida("La vigencia termina antes de empezar.")
    if datos.monto <= 0:
        raise ErrorCartaGarantiaInvalida("El monto de la carta debe ser mayor que cero.")


class RegistrarCartaGarantia:
    def __init__(
        self,
        repositorio: RepositorioCartaGarantia,
        estado_cuenta: RepositorioEstadoCuenta,
        registro_eventos: RegistroEventos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(
        self, cuenta_medica_id: int, datos: DatosCartaGarantia, actor: str
    ) -> CartaGarantia:
        estado = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        if estado is None:
            raise ErrorCuentaInexistenteCarta("No existe la cuenta.")
        if estado not in ESTADOS_CARTA:
            raise ErrorCuentaSinRegistroCarta(
                f"La cuenta está en estado {nombre_estado(estado)}: la carta de garantía "
                f"solo se registra {_EN_QUE_ESTADOS}."
            )
        _validar(datos)
        if await self._repositorio.obtener(cuenta_medica_id) is not None:
            raise ErrorCartaGarantiaYaRegistrada(
                "La cuenta ya tiene una carta de garantía registrada."
            )
        carta = CartaGarantia(
            cuenta_medica_id=cuenta_medica_id,
            numero=datos.numero.strip(),
            vigente_desde=datos.vigente_desde,
            vigente_hasta=datos.vigente_hasta,
            monto=datos.monto,
            registrado_en=self._reloj.ahora(),
            registrado_por=actor,
        )
        await self._repositorio.guardar(carta)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="CARTA_GARANTIA_REGISTRADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "numero": carta.numero,
                    "vigente_hasta": carta.vigente_hasta.isoformat(),
                    "monto": str(carta.monto),
                },
            )
        )
        return carta


def _datos_evento(carta: CartaGarantia) -> dict[str, str]:
    return {
        "numero": carta.numero,
        "vigente_desde": carta.vigente_desde.isoformat(),
        "vigente_hasta": carta.vigente_hasta.isoformat(),
        "monto": str(carta.monto),
    }


class CorregirCartaGarantia:
    """Corrige numero, vigencia o monto de la carta mientras la cuenta este
    REGISTRADA o RECHAZADA. La carta guarda los datos nuevos; el historial conserva los
    anteriores en el evento de la correccion (nunca se modifica un evento)."""

    def __init__(
        self,
        repositorio: RepositorioCartaGarantia,
        estado_cuenta: RepositorioEstadoCuenta,
        registro_eventos: RegistroEventos,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos

    async def ejecutar(
        self, cuenta_medica_id: int, datos: DatosCartaGarantia, actor: str
    ) -> CartaGarantia:
        estado = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        if estado is None:
            raise ErrorCuentaInexistenteCarta("No existe la cuenta.")
        if estado not in ESTADOS_CARTA:
            raise ErrorCartaGarantiaNoCorregible(
                f"La cuenta está en estado {nombre_estado(estado)}: la carta de garantía "
                f"solo se corrige {_EN_QUE_ESTADOS}."
            )
        anterior = await self._repositorio.obtener(cuenta_medica_id)
        if anterior is None:
            raise ErrorCartaGarantiaInexistente("La cuenta no tiene carta de garantía.")
        _validar(datos)
        corregida = replace(
            anterior,
            numero=datos.numero.strip(),
            vigente_desde=datos.vigente_desde,
            vigente_hasta=datos.vigente_hasta,
            monto=datos.monto,
        )
        await self._repositorio.actualizar(corregida)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento=TIPO_EVENTO_CARTA_CORREGIDA,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"anterior": _datos_evento(anterior), "nuevo": _datos_evento(corregida)},
            )
        )
        return corregida


class ObtenerCartaGarantia:
    def __init__(self, repositorio: RepositorioCartaGarantia) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> CartaGarantia | None:
        return await self._repositorio.obtener(cuenta_medica_id)
