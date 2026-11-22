"""Caso de uso CargarLoteEnValidador (Seccion 8.3, flujo completo de la
Seccion 7): orquesta el robot del validador TEDEF Web y compone
RegistrarResultadoValidador con RegistrarArchivoTransmision.

Vive en infraestructura/tedef/, no en dominio/integracion/, por la misma
razon que GenerarLote y RemitirLote: lee los `.txt` ya escritos en disco
por GenerarLote y escribe los reportes y el `.S01` descargados -- son
operaciones de filesystem sin alternativa intercambiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.compartido.huella import huella_sha256
from app.dominio.integracion.casos_uso_validacion import (
    DatosArchivoTransmision,
    DatosValidacionEtapa,
    RegistrarArchivoTransmision,
    RegistrarResultadoValidador,
)
from app.dominio.integracion.puertos_validacion import (
    ArchivoLote,
    ContextoCargaValidador,
    ErrorLoteNoCargable,
    IdentidadLoteTedef,
    LoteParaCargarValidador,
    RepositorioValidacionOficial,
    ResultadoEtapaValidador,
    ValidadorTedefWeb,
)
from app.dominio.integracion.vigencia_lote import exigir_lote_vigente
from app.dominio.puertos_comunes import Reloj

_ESTADO_GENERADO = "GENERADO"
_ESTADO_CARGADO_VALIDADOR = "CARGADO_VALIDADOR"


@dataclass(frozen=True, slots=True)
class DependenciasCargaValidador:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): todo lo
    que CargarLoteEnValidador necesita para orquestar el flujo completo
    de la Seccion 7 (subir, revisar forma, validar, obtener el `.S01`)."""

    repositorio: RepositorioValidacionOficial
    validador: ValidadorTedefWeb
    registrar_resultado: RegistrarResultadoValidador
    registrar_archivo: RegistrarArchivoTransmision
    reloj: Reloj
    directorio_reportes: Path
    directorio_artefactos: Path


@dataclass(frozen=True, slots=True)
class _EtapaCompletada:
    """Objeto de parametros privado: lo que _registrar_etapa necesita de
    una etapa (FORMA o DETALLADA) recien ejecutada por el robot."""

    lote_id: int
    trabajo_id: int
    etapa: str
    estado_previo: str
    resultado: ResultadoEtapaValidador
    inicio: datetime
    fin: datetime
    usuario_origen: str | None = None


class CargarLoteEnValidador:
    """Seccion 8.1, punto 6: 'el trabajo no se pierde, reintenta con
    retroceso exponencial'. Para un flujo de varios pasos como este
    (subir, validar, descargar), un reintento ciego que repite TODO desde
    el principio sube el mismo lote dos veces si el paso de subida ya
    habia tenido exito -- el validador lo rechaza entonces como duplicado
    (Seccion 9.2: 'lote no registrado antes'), destruyendo un resultado
    CONFORME ya registrado. `ejecutar` primero pregunta hasta donde llego
    la vez anterior (si la hubo) y reanuda ahi, en vez de reempezar."""

    def __init__(self, dependencias: DependenciasCargaValidador) -> None:
        self._d = dependencias

    async def ejecutar(
        self, lote_id: int, trabajo_id: int, actor: str, usuario_origen: str | None = None
    ) -> None:
        lote = await self._d.repositorio.obtener_lote_para_carga(lote_id)
        if lote is None:
            raise ErrorLoteNoCargable("No existe el lote.")
        # Justo antes de tocar el validador: el lote pudo cambiar en la cola.
        exigir_lote_vigente(await self._d.repositorio.vigencia_lote(lote_id))
        identidad = IdentidadLoteTedef(numero=lote.numero, periodo=lote.periodo)

        if await self._d.repositorio.existe_validacion_conforme(lote_id, "DETALLADA"):
            await self._obtener_y_registrar_s01(lote_id, identidad, actor, usuario_origen)
            return

        forma_ya_conforme = await self._d.repositorio.existe_validacion_conforme(lote_id, "FORMA")
        if not forma_ya_conforme and not await self._cargar(
            lote, trabajo_id, actor, usuario_origen
        ):
            return  # observado en FORMA: terminado, sin seguir a DETALLADA.

        if not await self._validar(identidad, lote_id, trabajo_id, actor, usuario_origen):
            return  # observado en DETALLADA: terminado, sin seguir al .S01.

        await self._obtener_y_registrar_s01(lote_id, identidad, actor, usuario_origen)

    async def _cargar(
        self,
        lote: LoteParaCargarValidador,
        trabajo_id: int,
        actor: str,
        usuario_origen: str | None,
    ) -> bool:
        """Devuelve True si la revision de forma fue conforme."""
        contexto = ContextoCargaValidador(
            numero=lote.numero,
            periodo=lote.periodo,
            archivos=tuple(
                ArchivoLote(nombre=a.nombre, contenido=Path(a.ruta).read_bytes())
                for a in lote.archivos
            ),
        )
        inicio = self._d.reloj.ahora()
        forma = await self._d.validador.cargar_lote(contexto)
        fin = self._d.reloj.ahora()
        await self._registrar_etapa(
            _EtapaCompletada(
                lote.lote_id,
                trabajo_id,
                "FORMA",
                _ESTADO_GENERADO,
                forma,
                inicio,
                fin,
                usuario_origen,
            ),
            actor,
        )
        return forma.conforme

    async def _validar(
        self,
        identidad: IdentidadLoteTedef,
        lote_id: int,
        trabajo_id: int,
        actor: str,
        usuario_origen: str | None,
    ) -> bool:
        """Devuelve True si la validacion detallada fue conforme."""
        inicio = self._d.reloj.ahora()
        detallada = await self._d.validador.validar_lote(identidad)
        fin = self._d.reloj.ahora()
        await self._registrar_etapa(
            _EtapaCompletada(
                lote_id,
                trabajo_id,
                "DETALLADA",
                _ESTADO_CARGADO_VALIDADOR,
                detallada,
                inicio,
                fin,
                usuario_origen,
            ),
            actor,
        )
        return detallada.conforme

    async def _registrar_etapa(self, etapa: _EtapaCompletada, actor: str) -> None:
        ruta_reporte, sha256_reporte = None, None
        if etapa.resultado.reporte is not None:
            ruta_reporte, sha256_reporte = self._guardar_reporte(etapa)

        await self._d.registrar_resultado.ejecutar(
            DatosValidacionEtapa(
                lote_id=etapa.lote_id,
                trabajo_id=etapa.trabajo_id,
                etapa=etapa.etapa,
                estado_previo=etapa.estado_previo,
                resultado=etapa.resultado,
                ruta_reporte=ruta_reporte,
                sha256_reporte=sha256_reporte,
                inicio=etapa.inicio,
                fin=etapa.fin,
                usuario_origen=etapa.usuario_origen,
            ),
            actor=actor,
        )

    def _guardar_reporte(self, etapa: _EtapaCompletada) -> tuple[str, str]:
        assert etapa.resultado.reporte is not None
        nombre_archivo = f"{etapa.lote_id}_{etapa.etapa.lower()}.xlsx"
        ruta = self._d.directorio_reportes / "validacion_oficial" / nombre_archivo
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(etapa.resultado.reporte.contenido)
        return str(ruta), huella_sha256(etapa.resultado.reporte.contenido)

    async def _obtener_y_registrar_s01(
        self,
        lote_id: int,
        identidad: IdentidadLoteTedef,
        actor: str,
        usuario_origen: str | None = None,
    ) -> None:
        inicio = self._d.reloj.ahora()
        archivo_s01 = await self._d.validador.descargar_archivo_transmision(identidad)
        fin = self._d.reloj.ahora()

        self._d.directorio_artefactos.mkdir(parents=True, exist_ok=True)
        ruta_s01 = self._d.directorio_artefactos / archivo_s01.nombre
        ruta_s01.write_bytes(archivo_s01.contenido)
        sha256_s01 = huella_sha256(archivo_s01.contenido)

        await self._d.registrar_archivo.ejecutar(
            DatosArchivoTransmision(
                lote_id=lote_id,
                archivo_s01=archivo_s01,
                ruta_s01=str(ruta_s01),
                sha256_s01=sha256_s01,
                inicio=inicio,
                fin=fin,
                usuario_origen=usuario_origen,
            ),
            actor=actor,
        )
