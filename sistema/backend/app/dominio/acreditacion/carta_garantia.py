"""RF-13 y CU-06: la carta de garantia de la IAFAS, con su numero, su
vigencia y su monto, registrada desde el detalle de la cuenta. Hasta la
verificacion de cumplimiento del 2026-11-12 no existia como documento: el
aviso de vencimiento usaba la vigencia de la acreditacion como sustituto,
que sigue valiendo para las cuentas sin carta registrada."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

# Tabla 69: nada se registra sobre una cuenta cerrada o anulada.
ESTADOS_SIN_REGISTRO = frozenset({"CERRADA", "ANULADA"})
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


def _validar(datos: DatosCartaGarantia) -> None:
    numero = datos.numero.strip()
    if not numero or len(numero) > LONGITUD_MAXIMA_NUMERO:
        raise ErrorCartaGarantiaInvalida(
            f"El numero de la carta es obligatorio (hasta {LONGITUD_MAXIMA_NUMERO} caracteres)."
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
            raise ErrorCuentaInexistenteCarta(f"No existe la cuenta {cuenta_medica_id}.")
        if estado in ESTADOS_SIN_REGISTRO:
            raise ErrorCuentaSinRegistroCarta(
                f"La cuenta {cuenta_medica_id} esta en estado {estado!r}."
            )
        _validar(datos)
        if await self._repositorio.obtener(cuenta_medica_id) is not None:
            raise ErrorCartaGarantiaYaRegistrada(
                f"La cuenta {cuenta_medica_id} ya tiene una carta de garantia registrada."
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


class ObtenerCartaGarantia:
    def __init__(self, repositorio: RepositorioCartaGarantia) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> CartaGarantia | None:
        return await self._repositorio.obtener(cuenta_medica_id)
