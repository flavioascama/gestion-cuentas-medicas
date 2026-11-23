"""Lo que se le entrega a la aseguradora como sustento de la respuesta a
una glosa: lo escrito por la persona y, si al responder se refacturo, una
linea final con el comprobante vigente y su nota (2026-11-19). Separado de
casos_uso.py por el limite de lineas por archivo."""

from __future__ import annotations

from app.dominio.pse.documentos import DocumentosPagoCuenta
from app.dominio.pse.neto import neto_a_cobrar

# El mismo tope que el esquema de la respuesta y la columna del sustento.
LONGITUD_MAXIMA_SUSTENTO = 500


def linea_comprobante(documentos: DocumentosPagoCuenta | None) -> str | None:
    """El comprobante vigente y su nota, si al responder se refacturo."""
    if documentos is None or (not documentos.reemplazados and documentos.nota is None):
        return None
    vigente = documentos.vigente
    linea = f"Comprobante vigente: {vigente.serie}-{vigente.numero}."
    nota = documentos.nota
    if nota is not None:
        tipo = "crédito" if nota.tipo == "C" else "débito"
        linea += f" Nota de {tipo}: {nota.serie}-{nota.numero} por {nota.monto}."
    return linea


def sustento_con_comprobante(sustento: str | None, linea: str) -> str:
    # Si no cabe todo, se recorta lo escrito por la persona, nunca la linea.
    escrito = (sustento or "").strip()
    disponible = LONGITUD_MAXIMA_SUSTENTO - len(linea) - 1
    if not escrito or disponible <= 0:
        return linea[:LONGITUD_MAXIMA_SUSTENTO]
    return f"{escrito[:disponible].rstrip()}\n{linea}"


def datos_de_respuesta(
    documentos: DocumentosPagoCuenta | None, sustento: str | None
) -> dict[str, str | None]:
    """El sustento a entregar y, si la cuenta se refacturo, el comprobante
    vigente y lo que hoy se cobra por el: la IAFAS liquida sobre ese monto y
    no sobre el del comprobante que recibio en el lote."""
    linea = linea_comprobante(documentos)
    if documentos is None or linea is None:
        return {"sustento": sustento}
    vigente, neto = documentos.vigente, neto_a_cobrar(documentos)
    return {
        "sustento": sustento_con_comprobante(sustento, linea),
        "comprobante_vigente": vigente.serie + vigente.numero,
        "monto_vigente": None if neto is None else str(neto),
    }
