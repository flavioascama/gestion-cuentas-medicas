"""Cableado de FastAPI para /cuentas (Fase 18): consulta (Seccion 11) y
verificacion de cobertura (Seccion 8.1). Separado de dependencias.py, que
ya cubre acceso (Seccion 3: limite de 400 lineas)."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_registro_eventos, obtener_reloj
from app.compartido.configuracion import Configuracion, obtener_configuracion
from app.dominio.acreditacion.casos_uso import ObtenerAcreditacion, SolicitarVerificacionCobertura
from app.dominio.acreditacion.puertos import RepositorioAcreditacion
from app.dominio.integracion.casos_uso_consulta import (
    BuscarCie10,
    ListarCuentas,
    ListarIafas,
    ObtenerCuenta,
)
from app.dominio.integracion.casos_uso_ingesta import (
    ConsultarCompletitudCuenta,
    RegistrarCuentaMedica,
)
from app.dominio.integracion.puertos_consulta import (
    RepositorioCie10Consulta,
    RepositorioCuentasConsulta,
    RepositorioIafasConsulta,
)
from app.dominio.integracion.puertos_ingesta import (
    RepositorioCompletitudCuenta,
    RepositorioIngestaCuentas,
)
from app.dominio.pse.casos_uso import EmitirComprobantePago
from app.dominio.pse.puertos import EmisorPse, RepositorioComprobantePago
from app.dominio.puertos_comunes import RegistroEventos, Reloj, RepositorioTrabajos
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.repositorio_acreditacion_sql import RepositorioAcreditacionSql
from app.infraestructura.persistencia.repositorio_cie10_consulta_sql import (
    RepositorioCie10ConsultaSql,
)
from app.infraestructura.persistencia.repositorio_comprobante_pago_sql import (
    RepositorioComprobantePagoSql,
)
from app.infraestructura.persistencia.repositorio_cuentas_consulta_sql import (
    RepositorioCuentasConsultaSql,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)
from app.infraestructura.persistencia.repositorio_iafas_consulta_sql import (
    RepositorioIafasConsultaSql,
)
from app.infraestructura.persistencia.repositorio_ingesta_cuentas_sql import (
    RepositorioCompletitudCuentaSql,
    RepositorioIngestaCuentasSql,
)
from app.infraestructura.pse.emisor_pse_http import EmisorPseHttp


def obtener_repositorio_cuentas_consulta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioCuentasConsulta:
    return RepositorioCuentasConsultaSql(sesion)


def obtener_repositorio_iafas_consulta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioIafasConsulta:
    return RepositorioIafasConsultaSql(sesion)


def construir_listar_iafas(
    repositorio: RepositorioIafasConsulta = Depends(obtener_repositorio_iafas_consulta),
) -> ListarIafas:
    return ListarIafas(repositorio)


def obtener_repositorio_cie10_consulta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioCie10Consulta:
    return RepositorioCie10ConsultaSql(sesion)


def construir_buscar_cie10(
    repositorio: RepositorioCie10Consulta = Depends(obtener_repositorio_cie10_consulta),
) -> BuscarCie10:
    return BuscarCie10(repositorio)


def obtener_repositorio_acreditacion(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioAcreditacion:
    return RepositorioAcreditacionSql(sesion)


def obtener_repositorio_trabajos(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioTrabajos:
    return RepositorioTrabajosSql(sesion)


def construir_listar_cuentas(
    repositorio: RepositorioCuentasConsulta = Depends(obtener_repositorio_cuentas_consulta),
) -> ListarCuentas:
    return ListarCuentas(repositorio)


def construir_obtener_cuenta(
    repositorio: RepositorioCuentasConsulta = Depends(obtener_repositorio_cuentas_consulta),
) -> ObtenerCuenta:
    return ObtenerCuenta(repositorio)


def construir_obtener_acreditacion(
    repositorio: RepositorioAcreditacion = Depends(obtener_repositorio_acreditacion),
) -> ObtenerAcreditacion:
    return ObtenerAcreditacion(repositorio)


def construir_solicitar_verificacion_cobertura(
    repositorio: RepositorioAcreditacion = Depends(obtener_repositorio_acreditacion),
    repositorio_trabajos: RepositorioTrabajos = Depends(obtener_repositorio_trabajos),
    reloj: Reloj = Depends(obtener_reloj),
) -> SolicitarVerificacionCobertura:
    return SolicitarVerificacionCobertura(repositorio, repositorio_trabajos, reloj)


def obtener_repositorio_ingesta_cuentas(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioIngestaCuentas:
    return RepositorioIngestaCuentasSql(sesion)


def obtener_repositorio_completitud_cuenta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioCompletitudCuenta:
    return RepositorioCompletitudCuentaSql(sesion)


def construir_registrar_cuenta(
    repositorio: RepositorioIngestaCuentas = Depends(obtener_repositorio_ingesta_cuentas),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
) -> RegistrarCuentaMedica:
    return RegistrarCuentaMedica(repositorio, registro_eventos)


def construir_consultar_completitud(
    repositorio: RepositorioCompletitudCuenta = Depends(obtener_repositorio_completitud_cuenta),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
) -> ConsultarCompletitudCuenta:
    return ConsultarCompletitudCuenta(repositorio, registro_eventos)


def obtener_repositorio_comprobante_pago(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RepositorioComprobantePago:
    return RepositorioComprobantePagoSql(sesion)


def obtener_emisor_pse(
    configuracion: Configuracion = Depends(obtener_configuracion),
) -> EmisorPse:
    return EmisorPseHttp(configuracion.pse_url_base)


def construir_emitir_comprobante_pago(
    repositorio: RepositorioComprobantePago = Depends(obtener_repositorio_comprobante_pago),
    emisor: EmisorPse = Depends(obtener_emisor_pse),
    registro_eventos: RegistroEventos = Depends(obtener_registro_eventos),
    sesion: AsyncSession = Depends(obtener_sesion),
) -> EmitirComprobantePago:
    return EmitirComprobantePago(
        repositorio, emisor, registro_eventos, RepositorioEstadoCuentaSql(sesion)
    )
