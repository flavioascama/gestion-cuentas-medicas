"""Copago cobrado al paciente en la clinica (2026-11-19): una fila por
cuenta. Lo trae la atencion importada del sistema hospitalario o lo
registra el analista desde la pantalla (RegistrarCopagoCobrado)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.orquestacion.valores import ESTADOS_TERMINALES
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

ORIGEN_SISTEMA_HOSPITALARIO = "sistema_hospitalario"
ORIGEN_MANUAL = "manual"
ORIGENES_COPAGO = (ORIGEN_SISTEMA_HOSPITALARIO, ORIGEN_MANUAL)


@dataclass(frozen=True, slots=True)
class CopagoCobrado:
    monto: Decimal
    fecha: date
    referencia: str
    origen: str
    registrado_por: str
    registrado_en: datetime | None = None


class RepositorioCopagoCobrado(Protocol):
    async def obtener(self, cuenta_medica_id: int) -> CopagoCobrado | None: ...

    async def registrar(self, cuenta_medica_id: int, copago: CopagoCobrado) -> int:
        """Guarda el copago de la cuenta sin confirmar la transaccion.
        Devuelve el id de la fila."""
        ...


class ConsultarCopagoCobrado:
    def __init__(self, repositorio: RepositorioCopagoCobrado) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> CopagoCobrado | None:
        return await self._repositorio.obtener(cuenta_medica_id)


class ErrorCopagoCobrado(Exception):
    pass


class ErrorCuentaInexistenteCopago(ErrorCopagoCobrado):
    pass


class ErrorCopagoInvalido(ErrorCopagoCobrado):
    pass


class ErrorCopagoYaRegistrado(ErrorCopagoCobrado):
    pass


class ErrorCuentaCerradaCopago(ErrorCopagoCobrado):
    pass


LONGITUD_MAXIMA_REFERENCIA = 60


@dataclass(frozen=True, slots=True)
class DatosCobroCopago:
    """Lo que digita el analista desde el comprobante de caja."""

    monto: Decimal
    fecha: date
    referencia: str


def _validar(datos: DatosCobroCopago, hoy: date) -> str:
    referencia = datos.referencia.strip()
    if datos.monto <= 0:
        raise ErrorCopagoInvalido("El monto del copago cobrado debe ser mayor que cero.")
    if datos.fecha > hoy:
        raise ErrorCopagoInvalido("La fecha del cobro es posterior a hoy.")
    if not referencia or len(referencia) > LONGITUD_MAXIMA_REFERENCIA:
        raise ErrorCopagoInvalido(
            "La referencia del comprobante de caja es obligatoria "
            f"(hasta {LONGITUD_MAXIMA_REFERENCIA} caracteres)."
        )
    return referencia


class RegistrarCopagoCobrado:
    """Registro manual del copago que la clinica cobro al paciente, cuando
    no llego con la atencion importada: una sola vez por cuenta y nunca en
    una cuenta cerrada o anulada."""

    def __init__(
        self,
        repositorio: RepositorioCopagoCobrado,
        estado_cuenta: RepositorioEstadoCuenta,
        registro_eventos: RegistroEventos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(
        self, cuenta_medica_id: int, datos: DatosCobroCopago, actor: str
    ) -> CopagoCobrado:
        estado = await self._estado_cuenta.obtener_estado(cuenta_medica_id)
        if estado is None:
            raise ErrorCuentaInexistenteCopago(f"No existe la cuenta medica {cuenta_medica_id}.")
        if estado in ESTADOS_TERMINALES:
            raise ErrorCuentaCerradaCopago(
                f"La cuenta {cuenta_medica_id} esta en estado {estado!r}: no admite el cobro."
            )
        ahora = self._reloj.ahora()
        referencia = _validar(datos, ahora.date())
        if await self._repositorio.obtener(cuenta_medica_id) is not None:
            raise ErrorCopagoYaRegistrado(
                f"La cuenta {cuenta_medica_id} ya tiene su copago cobrado registrado."
            )
        copago = CopagoCobrado(
            monto=datos.monto,
            fecha=datos.fecha,
            referencia=referencia,
            origen=ORIGEN_MANUAL,
            registrado_por=actor,
            registrado_en=ahora,
        )
        await self._repositorio.registrar(cuenta_medica_id, copago)
        # El evento confirma la transaccion junto con la fila del cobro.
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="COPAGO_COBRADO_REGISTRADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"monto": str(datos.monto), "origen": ORIGEN_MANUAL},
            )
        )
        return copago
