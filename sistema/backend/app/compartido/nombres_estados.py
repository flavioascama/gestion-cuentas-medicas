"""Nombres legibles de los estados, iguales a los que muestra la pantalla
(`mapa_estados.ts`)."""

from __future__ import annotations

_NOMBRES_ESTADOS = {
    # Estados de la cuenta.
    "REGISTRADA": "Registrada",
    "FACTURADA": "Facturada",
    "ENVIADA": "Enviada",
    "RECHAZADA": "Rechazada",
    "EN_AUDITORIA": "En auditoría",
    "GLOSADA": "Glosada",
    "GLOSADA_PARCIAL": "Glosada parcial",
    "SUBSANADA": "Subsanada",
    "LIQUIDADA": "Liquidada",
    "LIQUIDADA_PARCIAL": "Liquidada parcial",
    "PAGADA": "Pagada",
    "PAGADA_PARCIAL": "Pagada parcial",
    "CERRADA": "Cerrada",
    "ANULADA": "Anulada",
    # Estados del lote.
    "GENERADO": "Generado",
    "CARGADO_VALIDADOR": "Cargado en el validador",
    "OBSERVADO_VALIDADOR": "Observado por el validador",
    "VALIDADO": "Validado",
    "REMITIDO_IAFAS": "Remitido a la IAFAS",
    "ACEPTADO": "Aceptado",
    "RECHAZADO": "Rechazado",
    "EXCEDIDO": "Excedido",
}


def nombre_estado(estado: str) -> str:
    """Nombre legible de un estado de cuenta o de lote; un estado desconocido
    se devuelve tal cual."""

    return _NOMBRES_ESTADOS.get(estado, estado)
