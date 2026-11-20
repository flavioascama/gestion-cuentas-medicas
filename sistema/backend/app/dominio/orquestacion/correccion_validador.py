"""Cuenta en correccion por el validador TEDEF Web. El lote observado no
se vuelve a cargar y sus cuentas siguen FACTURADA; sin esta regla ninguna
podria corregirse y el error se repetiria en el lote nuevo. Es la unica
excepcion a los estados editables de cada caso de uso, y no agrega estados
ni transiciones (Tabla 58)."""

from __future__ import annotations

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta


async def admite_correccion(
    estado_cuenta: RepositorioEstadoCuenta, cuenta_medica_id: int, estado_admitido: bool
) -> bool:
    """`estado_admitido` es la regla propia del caso de uso; solo si la
    rechaza se consulta el lote, para no leerlo en el camino comun."""
    if estado_admitido:
        return True
    return await estado_cuenta.en_correccion_validador(cuenta_medica_id)
