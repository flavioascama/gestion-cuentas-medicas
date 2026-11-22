"""Adaptador de RepositorioParametrosIafas (CU-18)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.plazos.parametros import (
    ParametrosIafas,
    RepositorioAltaBajaIafas,
    RepositorioParametrosIafas,
)
from app.infraestructura.persistencia.modelos_comunicaciones import ComunicacionIafasModelo
from app.infraestructura.persistencia.modelos_correos import CorreoIafasModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    LoteFacturacionModelo,
)


def _a_parametros(fila: IafasModelo) -> ParametrosIafas:
    return ParametrosIafas(
        iafas_id=fila.id,
        codigo=fila.codigo,
        razon_social=fila.razon_social,
        periodicidad_remision_dias=fila.periodicidad_remision_dias,
        ventana_monitoreo_horas=fila.ventana_monitoreo_horas,
        dias_plazo_respuesta_observacion=fila.dias_plazo_respuesta_observacion,
        dias_plazo_comunicacion_auditoria=fila.dias_plazo_comunicacion_auditoria,
        dias_plazo_pago_liquidacion=fila.dias_plazo_pago_liquidacion,
        correo_remitente=fila.correo_remitente,
    )


class RepositorioParametrosIafasSql(RepositorioParametrosIafas, RepositorioAltaBajaIafas):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def listar(self) -> list[ParametrosIafas]:
        filas = await self._sesion.execute(sa.select(IafasModelo).order_by(IafasModelo.codigo))
        return [_a_parametros(fila) for fila in filas.scalars().all()]

    async def obtener(self, iafas_id: int) -> ParametrosIafas | None:
        fila = await self._sesion.get(IafasModelo, iafas_id)
        return _a_parametros(fila) if fila is not None else None

    async def actualizar(self, iafas_id: int, cambios: dict[str, int | str]) -> ParametrosIafas:
        await self._sesion.execute(
            sa.update(IafasModelo).where(IafasModelo.id == iafas_id).values(**cambios)
        )
        fila = await self._sesion.get(IafasModelo, iafas_id, populate_existing=True)
        assert fila is not None
        return _a_parametros(fila)

    async def existe_codigo(self, codigo: str) -> bool:
        consulta = sa.select(IafasModelo.id).where(IafasModelo.codigo == codigo)
        return await self._sesion.scalar(consulta) is not None

    async def crear(
        self, codigo: str, razon_social: str, plazos: dict[str, int]
    ) -> ParametrosIafas:
        fila = IafasModelo(codigo=codigo, razon_social=razon_social, **plazos)
        self._sesion.add(fila)
        await self._sesion.flush()
        return _a_parametros(fila)

    async def tiene_registros(self, iafas_id: int) -> bool:
        fila = await self._sesion.get(IafasModelo, iafas_id)
        assert fila is not None
        # Las tablas que la referencian por llave foranea y las que guardan
        # su codigo (comunicaciones y correos de la aseguradora).
        consultas = [
            sa.select(CuentaMedicaModelo.id).where(CuentaMedicaModelo.iafas_id == iafas_id),
            sa.select(LoteFacturacionModelo.id).where(LoteFacturacionModelo.iafas_id == iafas_id),
            sa.select(AseguradoModelo.id).where(AseguradoModelo.iafas_id == iafas_id),
            sa.select(ComunicacionIafasModelo.id).where(
                ComunicacionIafasModelo.codigo_iafas == fila.codigo
            ),
            sa.select(CorreoIafasModelo.id).where(CorreoIafasModelo.codigo_iafas == fila.codigo),
        ]
        for consulta in consultas:
            if await self._sesion.scalar(consulta.limit(1)) is not None:
                return True
        return False

    async def eliminar(self, iafas_id: int) -> None:
        await self._sesion.execute(sa.delete(IafasModelo).where(IafasModelo.id == iafas_id))

    async def actualizar_remitente(
        self, iafas_id: int, correo_remitente: str | None
    ) -> ParametrosIafas:
        await self._sesion.execute(
            sa.update(IafasModelo)
            .where(IafasModelo.id == iafas_id)
            .values(correo_remitente=correo_remitente)
        )
        fila = await self._sesion.get(IafasModelo, iafas_id, populate_existing=True)
        assert fila is not None
        return _a_parametros(fila)
