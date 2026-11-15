"""Pruebas de RepositorioRechazoCuentaSql contra SQLite en memoria, y del
camino de excepcion completo del TO-BE sobre los adaptadores reales:
lote rechazado por la IAFAS -> la cuenta queda RECHAZADA con el motivo
visible -> el analista la corrige (T-05) -> vuelve a ser elegible para
un lote nuevo."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.orquestacion.casos_uso import CorregirCuentaRechazada
from app.dominio.puertos_comunes import Evento, Observabilidad
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)
from app.infraestructura.persistencia.repositorio_monitoreo_respuesta_sql import (
    RepositorioMonitoreoRespuestaSql,
)
from app.infraestructura.persistencia.repositorio_rechazo_cuenta_sql import (
    RepositorioRechazoCuentaSql,
)
from pruebas.prueba_repositorio_monitoreo_respuesta import _sembrar_lote_remitido

_RESPONDIDO_EN = datetime(2026, 9, 18, 10, 0, 0)


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


class _MedicionesFalso:
    async def registrar(self, medicion: object) -> None:
        pass


async def prueba_sin_rechazo_devuelve_none(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        _, cuenta_id = await _sembrar_lote_remitido(sesion)
        assert await RepositorioRechazoCuentaSql(sesion).obtener_ultimo_rechazo(cuenta_id) is None


async def prueba_cuenta_rechazada_se_corrige_y_vuelve_a_ser_elegible(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, cuenta_id = await _sembrar_lote_remitido(sesion)
        await RepositorioMonitoreoRespuestaSql(sesion).aplicar_respuesta(
            lote_id, "RECHAZADO", "estructura invalida", _RESPONDIDO_EN
        )

    async with fabrica_sesiones() as sesion:
        rechazo = await RepositorioRechazoCuentaSql(sesion).obtener_ultimo_rechazo(cuenta_id)
        assert rechazo is not None
        assert (rechazo.lote_id, rechazo.numero_lote) == (lote_id, "0000001")
        assert rechazo.motivo == "estructura invalida"
        assert rechazo.rechazado_en == _RESPONDIDO_EN

        registro = _RegistroEventosFalso()
        caso_uso = CorregirCuentaRechazada(
            estado_cuenta=RepositorioEstadoCuentaSql(sesion),
            rechazos=RepositorioRechazoCuentaSql(sesion),
            observabilidad=Observabilidad(eventos=registro, mediciones=_MedicionesFalso()),
        )
        assert await caso_uso.ejecutar(cuenta_id, "se corrigio el CIE-10", "ana") == "FACTURADA"
        await sesion.commit()
        assert registro.eventos[0].datos["lote_rechazado_id"] == lote_id

    async with fabrica_sesiones() as sesion:
        # El generador de lotes toma las cuentas FACTURADA de la IAFAS
        # (RepositorioLoteFacturacionSql.obtener_documentos_facturados), sin
        # excluir comprobantes que ya estuvieron en otro lote: la cuenta
        # corregida vuelve a estar disponible para un lote nuevo.
        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None and cuenta.estado == "FACTURADA"
