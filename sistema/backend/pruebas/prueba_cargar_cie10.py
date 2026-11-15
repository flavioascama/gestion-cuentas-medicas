"""Pruebas del cargador del catalogo CIE-10 (T2 campo 18): lectura del
catalogo oficial real y carga en base de datos con huella y version."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo, Cie10VersionModelo
from herramientas.cargar_cie10 import _cargar, _leer_codigos


def prueba_leer_codigos_solo_incluye_subcategoria() -> None:
    codigos = _leer_codigos()

    assert len(codigos) > 10000
    longitudes = {len(c["codigo"]) for c in codigos}
    assert longitudes == {4, 5}  # nunca 3 (categoria) ni 6 (no cabe en el campo)

    codigos_por_valor = {c["codigo"] for c in codigos}
    assert len(codigos_por_valor) == len(codigos)  # ningun duplicado
    assert "A000" in codigos_por_valor  # ejemplo real citado en la Fase 17
    assert "A00" not in codigos_por_valor  # nivel de categoria, excluido


async def prueba_cargar_crea_version_con_huella_y_codigos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    codigos = _leer_codigos()[:50]  # subconjunto: la prueba no necesita los 12963 reales

    version_id = await _cargar(codigos, fabrica_sesiones)

    async with fabrica_sesiones() as sesion:
        version = await sesion.get(Cie10VersionModelo, version_id)
        assert version is not None
        assert version.conteo == 50
        assert len(version.huella_sha256) == 64  # sha256 en hex

        total = await sesion.scalar(
            sa.select(sa.func.count())
            .select_from(Cie10CodigoModelo)
            .where(Cie10CodigoModelo.cie10_version_id == version_id)
        )
        assert total == 50
