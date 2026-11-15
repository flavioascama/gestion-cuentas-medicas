"""Genera reportes/evidencia_r14_lotes.json (Seccion 13 del plan v3, que
amplia el contenido de la Seccion 11 del v2): "por lote: tramas y huellas,
resultado de prevalidacion, resultado de revision de forma y de
validacion detallada del validador, nombre y huella del .S01, transmision,
acuse y envio a SUSALUD" -- indicador: "100% de archivos conformes".

"Tramas y huellas" se reporta como el nombre y la huella SHA-256 del
`.S01` (la trama comprimida y cifrada que empaqueta T1 a T4, Seccion 8.3):
no existe una tabla que persista una huella por archivo .txt individual
(T1/T2/T3/T4) -- esos son escrituras intermedias de `GenerarLote`, sin
huella propia registrada, y el `.S01` es el unico artefacto que de verdad
se transmite y se verifica antes de remitir (Regla 11 del plan v3).

Todo lote en `lote_facturacion` ya tiene prevalidacion conforme, por
construccion (docstring de `modelos_prevalidacion.py`, Fase 18): un lote
no conforme nunca se persiste, asi que el escenario "Prevalidacion con
error" de la Seccion 14.2 no aparece aqui -- se demuestra en la propia
prueba de integracion, sobre la respuesta del caso de uso, no en este
reporte.

Uso (desde sistema/backend/):
    uv run python herramientas/generar_evidencia_r14_lotes.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.compartido.rutas import raiz_reportes
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_integracion import (
    AcuseTransmisionModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.modelos_plataformas import ValidacionOficialModelo
from app.infraestructura.persistencia.modelos_prevalidacion import InformePrevalidacionModelo
from herramientas.soporte_evidencia import construir_cabecera_evidencia

SALIDA = raiz_reportes() / "evidencia_r14_lotes.json"


def _iso(instante: datetime | date | None) -> str | None:
    return instante.isoformat() if instante else None


def _prevalidacion(informe: InformePrevalidacionModelo | None) -> dict[str, Any] | None:
    if informe is None:
        return None
    return {
        "conforme": informe.conforme,
        "generado_en": _iso(informe.generado_en),
        "hallazgos": [
            {
                "severidad": h.severidad,
                "tabla": h.tabla,
                "campo_numero": h.campo_numero,
                "campo_nombre": h.campo_nombre,
                "criterio_id": h.criterio_id,
                "criterio_texto": h.criterio_texto,
                "mensaje": h.mensaje,
            }
            for h in informe.hallazgos
        ],
    }


def _validaciones_oficiales(validaciones: list[ValidacionOficialModelo]) -> list[dict[str, Any]]:
    return [
        {
            "etapa": v.etapa,
            "resultado": v.resultado,
            "estado_informado_validador": v.estado_informado_validador,
            "ruta_reporte": v.ruta_reporte,
            "sha256_reporte": v.sha256_reporte,
            "registrado_en": _iso(v.registrado_en),
            "observaciones": [
                {
                    "tabla": o.tabla,
                    "numero_linea": o.numero_linea,
                    "campo_clave": o.campo_clave,
                    "campo": o.campo,
                    "valor_observado": o.valor_observado,
                    "codigo_error": o.codigo_error,
                    "descripcion": o.descripcion,
                }
                for o in v.observaciones
            ],
        }
        for v in validaciones
    ]


def _transmision(acuses: list[AcuseTransmisionModelo]) -> list[dict[str, Any]]:
    return [
        {
            "resultado_transferencia": a.resultado_transferencia,
            "motivo_transferencia": a.motivo_transferencia,
            "intentado_en": _iso(a.intentado_en),
            "respuesta_receptor": a.respuesta_receptor,
            "motivo_receptor": a.motivo_receptor,
            "respondido_en": _iso(a.respondido_en),
        }
        for a in acuses
    ]


def _lote_a_diccionario(
    lote: LoteFacturacionModelo,
    informes_por_lote: dict[int, InformePrevalidacionModelo],
    validaciones_por_lote: dict[int, list[ValidacionOficialModelo]],
    acuses_por_lote: dict[int, list[AcuseTransmisionModelo]],
) -> dict[str, Any]:
    return {
        "lote_id": lote.id,
        "numero": lote.numero,
        "iafas_id": lote.iafas_id,
        "periodo": lote.periodo,
        "estado": lote.estado,
        "generado_en": _iso(lote.generado_en),
        "prevalidacion": _prevalidacion(informes_por_lote.get(lote.id)),
        "validaciones_oficiales": _validaciones_oficiales(validaciones_por_lote.get(lote.id, [])),
        "archivo_s01": {
            "nombre": lote.nombre_s01,
            "huella_sha256": lote.sha256_s01,
            "obtenido_en": _iso(lote.s01_obtenido_en),
        },
        "transmision": _transmision(acuses_por_lote.get(lote.id, [])),
        "enviado_susalud_en": _iso(lote.enviado_susalud_en),
    }


async def _lotes(sesion: AsyncSession) -> list[LoteFacturacionModelo]:
    resultado = await sesion.execute(
        sa.select(LoteFacturacionModelo).order_by(LoteFacturacionModelo.id)
    )
    return list(resultado.scalars())


async def _informes_prevalidacion_por_lote(
    sesion: AsyncSession,
) -> dict[int, InformePrevalidacionModelo]:
    resultado = await sesion.execute(
        sa.select(InformePrevalidacionModelo).options(
            selectinload(InformePrevalidacionModelo.hallazgos)
        )
    )
    return {informe.lote_id: informe for informe in resultado.scalars()}


async def _validaciones_oficiales_por_lote(
    sesion: AsyncSession,
) -> dict[int, list[ValidacionOficialModelo]]:
    resultado = await sesion.execute(
        sa.select(ValidacionOficialModelo)
        .options(selectinload(ValidacionOficialModelo.observaciones))
        .order_by(ValidacionOficialModelo.registrado_en)
    )
    agrupadas: dict[int, list[ValidacionOficialModelo]] = {}
    for validacion in resultado.scalars():
        agrupadas.setdefault(validacion.lote_id, []).append(validacion)
    return agrupadas


async def _acuses_por_lote(sesion: AsyncSession) -> dict[int, list[AcuseTransmisionModelo]]:
    resultado = await sesion.execute(
        sa.select(AcuseTransmisionModelo).order_by(AcuseTransmisionModelo.intentado_en)
    )
    agrupados: dict[int, list[AcuseTransmisionModelo]] = {}
    for acuse in resultado.scalars():
        agrupados.setdefault(acuse.lote_id, []).append(acuse)
    return agrupados


async def main() -> None:
    cabecera = await construir_cabecera_evidencia()
    async with FabricaSesiones() as sesion:
        lotes = await _lotes(sesion)
        informes_por_lote = await _informes_prevalidacion_por_lote(sesion)
        validaciones_por_lote = await _validaciones_oficiales_por_lote(sesion)
        acuses_por_lote = await _acuses_por_lote(sesion)

    documento = {
        "_cabecera": cabecera.como_diccionario(),
        "lotes": [
            _lote_a_diccionario(lote, informes_por_lote, validaciones_por_lote, acuses_por_lote)
            for lote in lotes
        ],
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(documento, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Reporte generado: {SALIDA} ({len(lotes)} lotes).")


if __name__ == "__main__":
    asyncio.run(main())
