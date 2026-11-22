"""Cuando procede el comprobante de reemplazo (tercera auditoria, menor 3):
la misma regla de la pantalla (`admite_reemplazo`). Procede si el
comprobante vigente ya no refleja la cuenta o si el validador observo el
lote; con el comprobante al dia, en Rechazada o Glosada, no hace falta."""

from __future__ import annotations

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.pse.puertos import RepositorioCotejoComprobante

REEMPLAZO_INNECESARIO = (
    "El comprobante vigente ya refleja la cuenta: el comprobante de reemplazo solo se emite si "
    "el comprobante ya no refleja la cuenta o si el validador observó el lote de la cuenta."
)


async def estados_con_reemplazo(
    base: frozenset[str],
    cotejo: RepositorioCotejoComprobante | None,
    estado_cuenta: RepositorioEstadoCuenta,
    cuenta_medica_id: int,
) -> frozenset[str] | None:
    """Los estados en que procede el reemplazo (Facturada, solo con el
    comprobante desfasado); None si no hace falta. Sin cotejo no se sabe si
    el comprobante refleja la cuenta y rige solo `base`."""
    if cotejo is None:
        return base
    if (await cotejo.cotejar(cuenta_medica_id)).desfasado:
        return base | {"FACTURADA"}
    if await estado_cuenta.en_correccion_validador(cuenta_medica_id):
        return base
    estado = await estado_cuenta.obtener_estado(cuenta_medica_id)
    return None if estado in base else base
