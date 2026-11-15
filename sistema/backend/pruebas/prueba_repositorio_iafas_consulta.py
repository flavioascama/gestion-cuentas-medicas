"""Pruebas de RepositorioIafasConsultaSql (Fase 19)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.persistencia.modelos_integracion import IafasModelo
from app.infraestructura.persistencia.repositorio_iafas_consulta_sql import (
    RepositorioIafasConsultaSql,
)


async def prueba_listar_ordena_por_codigo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        sesion.add_all(
            [
                IafasModelo(
                    codigo="99553",
                    razon_social="Segunda",
                    periodicidad_remision_dias=7,
                    ventana_monitoreo_horas=48,
                ),
                IafasModelo(
                    codigo="19395",
                    razon_social="Primera",
                    periodicidad_remision_dias=7,
                    ventana_monitoreo_horas=48,
                ),
            ]
        )
        await sesion.commit()

        repositorio = RepositorioIafasConsultaSql(sesion)
        iafas = await repositorio.listar()
        assert [i.codigo for i in iafas] == ["19395", "99553"]
