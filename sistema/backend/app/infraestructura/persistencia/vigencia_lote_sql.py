"""Lee lo que hace falta para decidir si un lote sigue vigente
(dominio/integracion/vigencia_lote.py): el estado de cada cuenta, la nota
y el ultimo reemplazo de su comprobante, y si el comprobante quedo
desfasado. El lote solo guarda que documentos lleva; lo demas se compara
contra su fecha de generacion."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.vigencia_lote import (
    ESTADOS_LOTE_EN_CURSO,
    DocumentoEnLote,
    VigenciaLote,
)
from app.infraestructura.persistencia.modelos_documentos_pago import (
    ComprobanteReemplazadoModelo,
    NotaDocumentoModelo,
)
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.revision_contingencia_sql import (
    lotes_con_validacion_no_conforme,
)


async def vigencia_de_lote(sesion: AsyncSession, lote_id: int) -> VigenciaLote | None:
    """None si el lote no existe."""
    lote = await sesion.get(LoteFacturacionModelo, lote_id)
    if lote is None:
        return None
    vigencias = await _vigencias(sesion, LoteFacturacionModelo.id == lote_id)
    if lote_id in vigencias:
        return vigencias[lote_id]
    no_conforme = bool(await lotes_con_validacion_no_conforme(sesion, [lote_id]))
    return VigenciaLote(lote_id, lote.generado_en, (), validacion_no_conforme=no_conforme)


async def vigencias_de_lotes(sesion: AsyncSession, lote_ids: list[int]) -> dict[int, VigenciaLote]:
    """Las de varios lotes con una sola lectura de sus documentos (bandeja)."""
    if not lote_ids:
        return {}
    return await _vigencias(sesion, LoteFacturacionModelo.id.in_(lote_ids))


async def cuentas_en_lotes_vigentes(sesion: AsyncSession) -> set[int]:
    """Cuentas que ya estan en un lote en curso y vigente: no entran en
    otro. Las de un lote que dejo de ser vigente quedan libres."""
    vigencias = await _vigencias(sesion, LoteFacturacionModelo.estado.in_(ESTADOS_LOTE_EN_CURSO))
    return {
        documento.cuenta_medica_id
        for vigencia in vigencias.values()
        if vigencia.vigente
        for documento in vigencia.documentos
    }


async def _filas(sesion: AsyncSession, condicion: Any) -> list[Any]:
    """Una fila por documento de cada lote que cumple `condicion`."""
    ultimo_reemplazo = (
        sa.select(sa.func.max(ComprobanteReemplazadoModelo.reemplazado_en))
        .where(ComprobanteReemplazadoModelo.documento_facturador_id == DocumentoFacturadorModelo.id)
        .scalar_subquery()
    )
    filas = (
        await sesion.execute(
            sa.select(
                LoteFacturacionModelo.id,
                LoteFacturacionModelo.generado_en,
                CuentaMedicaModelo.id,
                CuentaMedicaModelo.identificacion_interna,
                CuentaMedicaModelo.estado,
                NotaDocumentoModelo.registrado_en,
                ultimo_reemplazo,
            )
            .join(LoteDocumentoModelo, LoteDocumentoModelo.lote_id == LoteFacturacionModelo.id)
            .join(
                DocumentoFacturadorModelo,
                DocumentoFacturadorModelo.id == LoteDocumentoModelo.documento_id,
            )
            .join(CuentaMedicaModelo, CuentaMedicaModelo.id == DocumentoFacturadorModelo.cuenta_id)
            .outerjoin(
                NotaDocumentoModelo,
                NotaDocumentoModelo.documento_facturador_id == DocumentoFacturadorModelo.id,
            )
            .where(condicion)
            .order_by(LoteFacturacionModelo.id, CuentaMedicaModelo.identificacion_interna)
        )
    ).all()
    return list(filas)


async def _vigencias(sesion: AsyncSession, condicion: Any) -> dict[int, VigenciaLote]:
    # Importado aqui: montos_comprobante_sql importa el repositorio del lote,
    # que a su vez usa este modulo.
    from app.infraestructura.persistencia.montos_comprobante_sql import cotejo_de_cuenta

    filas = await _filas(sesion, condicion)
    generados: dict[int, Any] = {}
    documentos: dict[int, list[DocumentoEnLote]] = {}
    for lote_id, generado_en, cuenta_id, identificacion, estado, nota_en, reemplazo_en in filas:
        generados[lote_id] = generado_en
        # Los montos solo importan si la cuenta sigue facturada.
        desfasado = estado == "FACTURADA" and (await cotejo_de_cuenta(sesion, cuenta_id)).desfasado
        documentos.setdefault(lote_id, []).append(
            DocumentoEnLote(
                cuenta_medica_id=cuenta_id,
                identificacion_interna=identificacion,
                estado_cuenta=estado,
                nota_registrada_en=nota_en,
                reemplazado_en=reemplazo_en,
                comprobante_desfasado=desfasado,
            )
        )
    no_conformes = await lotes_con_validacion_no_conforme(sesion, documentos)
    return {
        lote_id: VigenciaLote(
            lote_id,
            generados[lote_id],
            tuple(docs),
            validacion_no_conforme=lote_id in no_conformes,
        )
        for lote_id, docs in documentos.items()
    }
