"""Arma ProcesarComunicacionIafas sobre una sesion de base de datos (lo
usan el trabajador y las pruebas)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.comunicaciones.casos_uso import CasosUsoComunicaciones, ProcesarComunicacionIafas
from app.dominio.liquidacion.casos_uso import ConciliarPago, RegistrarLiquidacion
from app.dominio.observaciones.casos_uso import RegistrarObservacion
from app.dominio.observaciones.conformidad import RegistrarConformidadAuditoria
from app.dominio.puertos_comunes import Observabilidad
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_comunicaciones_sql import (
    RepositorioComunicacionesSql,
)
from app.infraestructura.persistencia.repositorio_conformidad_auditoria_sql import (
    RepositorioConformidadAuditoriaSql,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)
from app.infraestructura.persistencia.repositorio_liquidaciones_sql import (
    RepositorioLiquidacionesSql,
)
from app.infraestructura.persistencia.repositorio_observaciones_sql import (
    RepositorioCatalogoMotivosSql,
    RepositorioObservacionesSql,
)
from app.infraestructura.reloj import RelojSistema


def construir_procesar_comunicacion(sesion: AsyncSession) -> ProcesarComunicacionIafas:
    eventos = RegistroEventosSql(sesion)
    observabilidad = Observabilidad(eventos=eventos, mediciones=RegistroMedicionesSql(sesion))
    estado = RepositorioEstadoCuentaSql(sesion)
    reloj = RelojSistema()
    liquidaciones = RepositorioLiquidacionesSql(sesion)
    observaciones = RepositorioObservacionesSql(sesion)
    casos = CasosUsoComunicaciones(
        conformidad=RegistrarConformidadAuditoria(
            estado, RepositorioConformidadAuditoriaSql(sesion), eventos
        ),
        observacion=RegistrarObservacion(
            observaciones,
            RepositorioCatalogoMotivosSql(sesion),
            estado,
            observabilidad,
            reloj,
        ),
        liquidacion=RegistrarLiquidacion(
            liquidaciones, estado, observabilidad, reloj, observaciones
        ),
        pago=ConciliarPago(liquidaciones, estado, observabilidad, reloj),
    )
    return ProcesarComunicacionIafas(RepositorioComunicacionesSql(sesion), casos, eventos, reloj)
