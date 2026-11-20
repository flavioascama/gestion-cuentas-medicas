"""Puerto compartido del motor de orquestacion (Seccion 5.2.4): leer el
estado vigente de una cuenta y fijar el que resulta de una transicion ya
validada por `motor.validar_transicion`. Un solo puerto para todos los
casos de uso que disparan una transicion de la Tabla 58 (observaciones,
plazos, carta de garantia, liquidacion, pago, cierre, anulacion), en vez
de que cada uno reimplemente su propio acceso a `cuenta_medica.estado` --
el patron ya establecido en el modulo de integracion (varios repositorios
angostos sobre las mismas tablas, Seccion 5.2: RNF-13)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class RepositorioEstadoCuenta(Protocol):
    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        """None si la cuenta no existe."""
        ...

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None: ...

    async def en_correccion_validador(self, cuenta_medica_id: int) -> bool:
        """True si la cuenta esta FACTURADA y el lote mas reciente que
        contiene su comprobante quedo OBSERVADO_VALIDADOR: ese lote no se
        vuelve a cargar y la correccion va en un lote nuevo. Deja de serlo
        cuando la cuenta entra a otro lote."""
        ...


@dataclass(frozen=True, slots=True)
class RechazoCuenta:
    """El ultimo rechazo de la IAFAS que alcanzo a la cuenta (T-04): de que
    lote vino, con que motivo y cuando. Es lo que el analista necesita ver
    para corregir la cuenta antes del reenvio (T-05)."""

    lote_id: int
    numero_lote: str
    motivo: str | None
    rechazado_en: datetime | None


class RepositorioRechazoCuenta(Protocol):
    async def obtener_ultimo_rechazo(self, cuenta_medica_id: int) -> RechazoCuenta | None:
        """None si ningun lote de la cuenta fue rechazado por la IAFAS."""
        ...
