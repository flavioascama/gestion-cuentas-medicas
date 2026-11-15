"""Errores del contexto de cierre y anulacion de la cuenta medica."""

from __future__ import annotations


class ErrorDiferenciaPendiente(Exception):
    """CU-13: "el sistema verifica que el monto conciliado corresponda
    al liquidado" antes de cerrar (Tabla 52) -- no se puede cerrar con
    una diferencia de conciliacion sin resolver."""


class ErrorObservacionPendiente(Exception):
    """CU-13: precondicion del cierre, "sin observaciones pendientes"
    (Tabla 52)."""


class ErrorSinLiquidacion(Exception):
    """CU-13: no se puede cerrar una cuenta que todavia no tiene una
    liquidacion conciliada."""


class ErrorSolicitudAnulacionInexistente(Exception):
    """CU-13: no existe la solicitud de anulacion que se quiere
    resolver."""


class ErrorSolicitudAnulacionYaPendiente(Exception):
    """CU-13: ya existe una solicitud PENDIENTE para esta cuenta; se
    resuelve esa antes de registrar una nueva."""


class ErrorSolicitudAnulacionYaResuelta(Exception):
    """CU-13: no se puede aprobar o rechazar dos veces la misma
    solicitud."""
