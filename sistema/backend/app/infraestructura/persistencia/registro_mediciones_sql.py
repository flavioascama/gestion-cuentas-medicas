"""Adaptador del puerto RegistroMediciones (Seccion 6.4)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.puertos_comunes import MedicionPaso, RegistroMediciones
from app.infraestructura.persistencia.modelos_integracion import MedicionPasoModelo


class RegistroMedicionesSql(RegistroMediciones):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def registrar(self, medicion: MedicionPaso) -> None:
        self._sesion.add(
            MedicionPasoModelo(
                cuenta_medica_id=medicion.cuenta_medica_id,
                lote_id=medicion.lote_id,
                paso=medicion.paso,
                inicio=medicion.inicio,
                fin=medicion.fin,
                duracion_ms=medicion.duracion_ms,
                actor=medicion.actor,
                resultado=medicion.resultado,
                datos=medicion.datos,
            )
        )
        await self._sesion.commit()
