"""Cableado de FastAPI para /lotes (Seccion 7.6, 7.8, 8.3, Fase 18)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj
from app.compartido.configuracion import Configuracion, obtener_configuracion
from app.compartido.rutas import raiz_reportes
from app.dominio.integracion.casos_uso_consulta import (
    ListarLotes,
    ObtenerAcusesLote,
    ObtenerCuentasLote,
    ObtenerLote,
    ObtenerPrevalidacionLote,
    ObtenerRutaS01Lote,
    ObtenerValidacionOficialLote,
)
from app.dominio.integracion.casos_uso_validacion import (
    SolicitarCargaEnValidador,
    SolicitarEnvioSusalud,
)
from app.dominio.integracion.puertos import (
    RepositorioLoteFacturacion,
    RepositorioLoteRemision,
    Transmisor,
)
from app.dominio.integracion.puertos_consulta import RepositorioLotesConsulta
from app.dominio.integracion.puertos_validacion import RepositorioValidacionOficial
from app.dominio.puertos_comunes import (
    Observabilidad,
    Reloj,
    RepositorioTrabajos,
)
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_lote_remision_sql import (
    RepositorioLoteRemisionSql,
)
from app.infraestructura.persistencia.repositorio_lote_sql import RepositorioLoteFacturacionSql
from app.infraestructura.persistencia.repositorio_lotes_consulta_sql import (
    RepositorioLotesConsultaSql,
)
from app.infraestructura.persistencia.repositorio_validacion_oficial_sql import (
    RepositorioValidacionOficialSql,
)
from app.infraestructura.tedef.generar_lote import GenerarLote
from app.infraestructura.tedef.remitir_lote import RemitirLote
from app.infraestructura.transmision.transmisor_ftp import TransmisorFtp


def obtener_repositorio_lote_facturacion(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioLoteFacturacion:
    return RepositorioLoteFacturacionSql(sesion)


def obtener_repositorio_lotes_consulta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioLotesConsulta:
    return RepositorioLotesConsultaSql(sesion)


def obtener_repositorio_validacion_oficial(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioValidacionOficial:
    return RepositorioValidacionOficialSql(sesion)


def obtener_repositorio_lote_remision(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioLoteRemision:
    return RepositorioLoteRemisionSql(sesion)


def obtener_repositorio_trabajos(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioTrabajos:
    return RepositorioTrabajosSql(sesion)


def obtener_transmisor(
    configuracion: Configuracion = Depends(obtener_configuracion),
) -> Transmisor:
    return TransmisorFtp(configuracion)


def obtener_observabilidad(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> Observabilidad:
    return Observabilidad(
        eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
    )


def construir_generar_lote(
    repositorio: RepositorioLoteFacturacion = Depends(obtener_repositorio_lote_facturacion),
    sesion: AsyncSession = Depends(obtener_sesion),
    reloj: Reloj = Depends(obtener_reloj),
) -> GenerarLote:
    return GenerarLote(
        repositorio=repositorio,
        registro_eventos=RegistroEventosSql(sesion),
        registro_mediciones=RegistroMedicionesSql(sesion),
        reloj=reloj,
        directorio_salida=raiz_reportes() / "lotes_generados",
    )


def construir_listar_lotes(
    repositorio: RepositorioLotesConsulta = Depends(obtener_repositorio_lotes_consulta),
) -> ListarLotes:
    return ListarLotes(repositorio)


def construir_obtener_lote(
    repositorio: RepositorioLotesConsulta = Depends(obtener_repositorio_lotes_consulta),
) -> ObtenerLote:
    return ObtenerLote(repositorio)


def construir_obtener_prevalidacion_lote(
    repositorio: RepositorioLotesConsulta = Depends(obtener_repositorio_lotes_consulta),
) -> ObtenerPrevalidacionLote:
    return ObtenerPrevalidacionLote(repositorio)


def construir_obtener_validacion_oficial_lote(
    repositorio: RepositorioLotesConsulta = Depends(obtener_repositorio_lotes_consulta),
) -> ObtenerValidacionOficialLote:
    return ObtenerValidacionOficialLote(repositorio)


def construir_obtener_acuses_lote(
    repositorio: RepositorioLotesConsulta = Depends(obtener_repositorio_lotes_consulta),
) -> ObtenerAcusesLote:
    return ObtenerAcusesLote(repositorio)


def construir_obtener_cuentas_lote(
    repositorio: RepositorioLotesConsulta = Depends(obtener_repositorio_lotes_consulta),
) -> ObtenerCuentasLote:
    return ObtenerCuentasLote(repositorio)


def construir_obtener_ruta_s01_lote(
    repositorio: RepositorioLotesConsulta = Depends(obtener_repositorio_lotes_consulta),
) -> ObtenerRutaS01Lote:
    return ObtenerRutaS01Lote(repositorio)


def construir_solicitar_carga_en_validador(
    repositorio: RepositorioValidacionOficial = Depends(obtener_repositorio_validacion_oficial),
    repositorio_trabajos: RepositorioTrabajos = Depends(obtener_repositorio_trabajos),
    reloj: Reloj = Depends(obtener_reloj),
) -> SolicitarCargaEnValidador:
    return SolicitarCargaEnValidador(repositorio, repositorio_trabajos, reloj)


def construir_remitir_lote(
    repositorio: RepositorioLoteRemision = Depends(obtener_repositorio_lote_remision),
    transmisor: Transmisor = Depends(obtener_transmisor),
    observabilidad: Observabilidad = Depends(obtener_observabilidad),
    repositorio_trabajos: RepositorioTrabajos = Depends(obtener_repositorio_trabajos),
    reloj: Reloj = Depends(obtener_reloj),
) -> RemitirLote:
    return RemitirLote(repositorio, transmisor, observabilidad, repositorio_trabajos, reloj)


def construir_solicitar_envio_susalud(
    repositorio: RepositorioValidacionOficial = Depends(obtener_repositorio_validacion_oficial),
    repositorio_trabajos: RepositorioTrabajos = Depends(obtener_repositorio_trabajos),
    reloj: Reloj = Depends(obtener_reloj),
) -> SolicitarEnvioSusalud:
    return SolicitarEnvioSusalud(repositorio, repositorio_trabajos, reloj)
