"""Casos de uso de solo lectura del contexto de integracion (Fase 18,
Seccion 11): listados y detalle para las pantallas de cuentas y lotes.
Separado de casos_uso.py/casos_uso_validacion.py, que ya cubren cada uno
un caso de uso de escritura distinto (Seccion 3: limite de 400 lineas)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from app.dominio.integracion.puertos_consulta import (
    CuentaDelLote,
    DetalleCuenta,
    DetalleLote,
    InformePrevalidacionLote,
    RepositorioCie10Consulta,
    RepositorioCuentasConsulta,
    RepositorioIafasConsulta,
    RepositorioLotesConsulta,
    ResultadoValidacionOficial,
    ResumenAcuse,
    ResumenCie10,
    ResumenCuenta,
    ResumenIafas,
    ResumenLote,
)
from app.dominio.orquestacion.valores import ESTADOS_POR_ETAPA, EtapaCiclo

# Bajo este largo no se busca: evita una avalancha de resultados poco
# utiles con una o dos letras (mismo criterio que el buscador de CPMS).
_LARGO_MINIMO_BUSQUEDA_CIE10 = 2
_LIMITE_RESULTADOS_CIE10 = 20


class ListarIafas:
    def __init__(self, repositorio: RepositorioIafasConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self) -> list[ResumenIafas]:
        return await self._repositorio.listar()


class BuscarCie10:
    def __init__(self, repositorio: RepositorioCie10Consulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, texto: str) -> list[ResumenCie10]:
        texto = texto.strip()
        if len(texto) < _LARGO_MINIMO_BUSQUEDA_CIE10:
            return []
        return await self._repositorio.buscar(texto, _LIMITE_RESULTADOS_CIE10)


class ListarCuentas:
    def __init__(self, repositorio: RepositorioCuentasConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(
        self,
        estado: str | None,
        iafas_codigo: str | None = None,
        fecha_prestacion: date | None = None,
        etapa: EtapaCiclo | None = None,
    ) -> list[ResumenCuenta]:
        estados = ESTADOS_POR_ETAPA[etapa] if etapa is not None else None
        return await self._repositorio.listar(estado, iafas_codigo, fecha_prestacion, estados)


class ObtenerCuenta:
    def __init__(self, repositorio: RepositorioCuentasConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(
        self, cuenta_medica_id: int, con_datos_clinicos: bool = True
    ) -> DetalleCuenta | None:
        detalle = await self._repositorio.obtener(cuenta_medica_id)
        if detalle is None or con_datos_clinicos:
            return detalle
        return reservar_datos_clinicos(detalle)


def reservar_datos_clinicos(detalle: DetalleCuenta) -> DetalleCuenta:
    """El detalle sin lo que revela el acto medico: diagnosticos,
    historia clinica, medico tratante, procedimientos y productos
    dispensados."""

    return replace(
        detalle,
        numero_historia_clinica=None,
        diagnostico_principal_cie10=None,
        diagnosticos_secundarios_cie10=(),
        descripciones_cie10={},
        nombre_medico=None,
        colegiatura_medico=None,
        procedimientos=(),
        productos=(),
        datos_clinicos_reservados=True,
    )


class ListarLotes:
    def __init__(self, repositorio: RepositorioLotesConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(
        self,
        periodo: str | None,
        estado: str | None = None,
        iafas_id: int | None = None,
    ) -> list[ResumenLote]:
        return await self._repositorio.listar(periodo, estado, iafas_id)


class ObtenerLote:
    def __init__(self, repositorio: RepositorioLotesConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, lote_id: int) -> DetalleLote | None:
        return await self._repositorio.obtener(lote_id)


class ObtenerPrevalidacionLote:
    def __init__(self, repositorio: RepositorioLotesConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, lote_id: int) -> InformePrevalidacionLote | None:
        return await self._repositorio.obtener_prevalidacion(lote_id)


class ObtenerValidacionOficialLote:
    def __init__(self, repositorio: RepositorioLotesConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, lote_id: int) -> list[ResultadoValidacionOficial]:
        return await self._repositorio.obtener_validacion_oficial(lote_id)


class ObtenerAcusesLote:
    def __init__(self, repositorio: RepositorioLotesConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, lote_id: int) -> list[ResumenAcuse]:
        return await self._repositorio.obtener_acuses(lote_id)


class ObtenerCuentasLote:
    def __init__(self, repositorio: RepositorioLotesConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, lote_id: int) -> list[CuentaDelLote]:
        return await self._repositorio.obtener_cuentas(lote_id)


class ObtenerRutaS01Lote:
    def __init__(self, repositorio: RepositorioLotesConsulta) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, lote_id: int) -> str | None:
        return await self._repositorio.obtener_ruta_s01(lote_id)
