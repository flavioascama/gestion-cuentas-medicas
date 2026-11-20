"""Pruebas de CargarLoteEnValidador (Seccion 8.3, Fase 16) con dobles de
prueba -- sin Postgres ni Playwright. Cubren en particular la reanudacion
tras un reintento (Seccion 8.1, punto 6): un CARGAR_LOTE_VALIDADOR que
falla a mitad de camino y se reintenta no debe volver a subir un lote
cuya revision de forma ya fue conforme -- el validador lo rechazaria
como duplicado (bug real encontrado en la verificacion E2E de esta
fase, ver docs/DECISIONES.md)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.dominio.integracion.casos_uso_validacion import (
    RegistrarArchivoTransmision,
    RegistrarResultadoValidador,
)
from app.dominio.integracion.puertos_validacion import (
    ArchivoLote,
    ContextoCargaValidador,
    DatosRegistrarValidacion,
    IdentidadLoteTedef,
    LoteParaCargarValidador,
    ResultadoEtapaValidador,
    RutaArchivoLote,
)
from app.dominio.integracion.vigencia_lote import VigenciaLote
from app.dominio.puertos_comunes import Evento, MedicionPaso, Observabilidad
from app.infraestructura.tedef.cargar_lote_en_validador import (
    CargarLoteEnValidador,
    DependenciasCargaValidador,
)

_INSTANTE = datetime(2026, 9, 26, 9, 0, 0)
_CONFORME = ResultadoEtapaValidador(conforme=True, estado_informado="ok")
_OBSERVADO = ResultadoEtapaValidador(conforme=False, estado_informado="observado")


class _RelojFijo:
    def ahora(self) -> datetime:
        return _INSTANTE


@dataclass
class _RepositorioFalso:
    ruta_archivo_txt: Path
    forma_conforme_previa: bool = False
    detallada_conforme_previa: bool = False
    validaciones: list[str] = field(default_factory=list)
    archivos_transmision: list[str] = field(default_factory=list)
    vigencia: VigenciaLote | None = None

    async def vigencia_lote(self, lote_id: int) -> VigenciaLote | None:
        return self.vigencia

    async def obtener_lote_para_carga(self, lote_id: int) -> LoteParaCargarValidador | None:
        return LoteParaCargarValidador(
            lote_id=lote_id,
            numero="0000005",
            periodo="202612",
            archivos=(RutaArchivoLote(nombre="dfac_....txt", ruta=str(self.ruta_archivo_txt)),),
        )

    async def existe_validacion_conforme(self, lote_id: int, etapa: str) -> bool:
        if etapa == "FORMA":
            return self.forma_conforme_previa
        return self.detallada_conforme_previa

    async def registrar_validacion(self, datos: DatosRegistrarValidacion) -> int:
        self.validaciones.append(datos.etapa)
        return len(self.validaciones)

    async def registrar_archivo_transmision(
        self, lote_id: int, archivo: ArchivoLote, ruta_s01: str, sha256_s01: str, instante: datetime
    ) -> None:
        self.archivos_transmision.append(archivo.nombre)


@dataclass
class _ValidadorFalso:
    resultado_forma: ResultadoEtapaValidador = _CONFORME
    resultado_detallada: ResultadoEtapaValidador = _CONFORME
    llamadas_cargar: int = 0
    llamadas_validar: int = 0
    llamadas_descargar: int = 0

    async def cargar_lote(self, contexto: ContextoCargaValidador) -> ResultadoEtapaValidador:
        self.llamadas_cargar += 1
        return self.resultado_forma

    async def validar_lote(self, identidad: IdentidadLoteTedef) -> ResultadoEtapaValidador:
        self.llamadas_validar += 1
        return self.resultado_detallada

    async def descargar_archivo_transmision(self, identidad: IdentidadLoteTedef) -> ArchivoLote:
        self.llamadas_descargar += 1
        return ArchivoLote(nombre="937_....S01", contenido=b"cifrado")

    async def enviar_a_susalud(self, lotes: tuple[IdentidadLoteTedef, ...]) -> None:
        raise NotImplementedError


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@dataclass
class _RegistroMedicionesFalso:
    mediciones: list[MedicionPaso] = field(default_factory=list)

    async def registrar(self, medicion: MedicionPaso) -> None:
        self.mediciones.append(medicion)


def _repositorio_falso(tmp_path: Path, **kwargs: bool) -> _RepositorioFalso:
    ruta = tmp_path / "dfac_....txt"
    ruta.write_bytes(b"contenido de prueba")
    return _RepositorioFalso(ruta_archivo_txt=ruta, **kwargs)


def _construir(
    repositorio: _RepositorioFalso, validador: _ValidadorFalso, tmp_path: Path
) -> CargarLoteEnValidador:
    observabilidad = Observabilidad(  # type: ignore[arg-type]
        eventos=_RegistroEventosFalso(), mediciones=_RegistroMedicionesFalso()
    )
    dependencias = DependenciasCargaValidador(
        repositorio=repositorio,  # type: ignore[arg-type]
        validador=validador,  # type: ignore[arg-type]
        registrar_resultado=RegistrarResultadoValidador(repositorio, observabilidad),  # type: ignore[arg-type]
        registrar_archivo=RegistrarArchivoTransmision(repositorio, observabilidad),  # type: ignore[arg-type]
        reloj=_RelojFijo(),
        directorio_reportes=tmp_path / "reportes",
        directorio_artefactos=tmp_path / "artefactos",
    )
    return CargarLoteEnValidador(dependencias)


async def prueba_flujo_completo_conforme_llama_los_tres_pasos(tmp_path: Path) -> None:
    repositorio = _repositorio_falso(tmp_path)
    validador = _ValidadorFalso()
    caso_uso = _construir(repositorio, validador, tmp_path)

    await caso_uso.ejecutar(lote_id=9, trabajo_id=1, actor="trabajador")

    assert validador.llamadas_cargar == 1
    assert validador.llamadas_validar == 1
    assert validador.llamadas_descargar == 1
    assert repositorio.validaciones == ["FORMA", "DETALLADA"]
    assert repositorio.archivos_transmision == ["937_....S01"]


async def prueba_forma_observada_no_continua_a_detallada(tmp_path: Path) -> None:
    repositorio = _repositorio_falso(tmp_path)
    validador = _ValidadorFalso(resultado_forma=_OBSERVADO)
    caso_uso = _construir(repositorio, validador, tmp_path)

    await caso_uso.ejecutar(lote_id=9, trabajo_id=1, actor="trabajador")

    assert validador.llamadas_cargar == 1
    assert validador.llamadas_validar == 0
    assert validador.llamadas_descargar == 0
    assert repositorio.validaciones == ["FORMA"]


async def prueba_detallada_observada_no_descarga_el_s01(tmp_path: Path) -> None:
    repositorio = _repositorio_falso(tmp_path)
    validador = _ValidadorFalso(resultado_detallada=_OBSERVADO)
    caso_uso = _construir(repositorio, validador, tmp_path)

    await caso_uso.ejecutar(lote_id=9, trabajo_id=1, actor="trabajador")

    assert validador.llamadas_cargar == 1
    assert validador.llamadas_validar == 1
    assert validador.llamadas_descargar == 0
    assert repositorio.validaciones == ["FORMA", "DETALLADA"]


async def prueba_reintento_tras_forma_conforme_no_vuelve_a_subir(tmp_path: Path) -> None:
    """Bug real: un reintento del trabajo CARGAR_LOTE_VALIDADOR, tras un
    fallo transitorio en el paso de validar, no debe volver a llamar a
    cargar_lote -- el validador ya tiene ese lote registrado y lo
    rechazaria como duplicado."""

    repositorio = _repositorio_falso(tmp_path, forma_conforme_previa=True)
    validador = _ValidadorFalso()
    caso_uso = _construir(repositorio, validador, tmp_path)

    await caso_uso.ejecutar(lote_id=9, trabajo_id=1, actor="trabajador")

    assert validador.llamadas_cargar == 0
    assert validador.llamadas_validar == 1
    assert validador.llamadas_descargar == 1
    assert repositorio.validaciones == ["DETALLADA"]


async def prueba_reintento_tras_detallada_conforme_solo_descarga(tmp_path: Path) -> None:
    repositorio = _repositorio_falso(
        tmp_path, forma_conforme_previa=True, detallada_conforme_previa=True
    )
    validador = _ValidadorFalso()
    caso_uso = _construir(repositorio, validador, tmp_path)

    await caso_uso.ejecutar(lote_id=9, trabajo_id=1, actor="trabajador")

    assert validador.llamadas_cargar == 0
    assert validador.llamadas_validar == 0
    assert validador.llamadas_descargar == 1
    assert repositorio.validaciones == []
    assert repositorio.archivos_transmision == ["937_....S01"]
