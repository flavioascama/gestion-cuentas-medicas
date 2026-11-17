"""Adaptador de RepositorioValidacionOficial (Seccion 8.3, Fase 16).

Recomputa los nombres de los `.txt` de un lote GENERADO desde su
identidad (mismo patron que nombrado.py usa para el `.S01`: la ruta
nunca se persiste, Seccion 7.6) en vez de leer una columna con la ruta
guardada -- GenerarLote (Fase 7/13) no persiste `rutas_archivos`, solo
las devuelve en memoria a quien lo invoco.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.compartido.rutas import raiz_reportes
from app.dominio.integracion.puertos_validacion import (
    ArchivoLote,
    DatosRegistrarValidacion,
    LoteParaCargarValidador,
    LoteParaEnvioSusalud,
    ObservacionLectura,
    RepositorioValidacionOficial,
    RutaArchivoLote,
)
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    DocumentoFacturadorModelo,
    IpressModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.modelos_plataformas import (
    ObservacionValidadorModelo,
    ValidacionOficialModelo,
)
from app.infraestructura.tedef.carga_tablas_activas import cargar_tablas_activas
from app.infraestructura.tedef.nombrado import (
    PREFIJO_ARCHIVO_POR_TABLA,
    IdentidadTrama,
    nombre_archivo_txt,
)

_ESTADO_OBSERVADO_VALIDADOR = "OBSERVADO_VALIDADOR"
_ESTADO_CARGADO_VALIDADOR = "CARGADO_VALIDADOR"
# Tambien lo usa el control del envio (repositorio_control_susalud_sql).
ESTADOS_ENVIABLES_SUSALUD = ("VALIDADO", "REMITIDO_IAFAS", "ACEPTADO", "RECHAZADO")


class RepositorioValidacionOficialSql(RepositorioValidacionOficial):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_lote_para_carga(self, lote_id: int) -> LoteParaCargarValidador | None:
        lote = await self._sesion.get(
            LoteFacturacionModelo, lote_id, options=[joinedload(LoteFacturacionModelo.iafas)]
        )
        if lote is None:
            return None
        ipress = await self._obtener_ipress_propia()
        identidad = IdentidadTrama(
            ruc=ipress.ruc,
            codigo_ipress=ipress.codigo_ipress,
            codigo_iafas=lote.iafas.codigo,
            numero_lote=lote.numero,
            periodo=lote.periodo,
            fecha=lote.generado_en.date(),
        )
        directorio = raiz_reportes() / "lotes_generados"
        tablas = list(cargar_tablas_activas())
        # T4 es condicional (Seccion 8.1, Fase 17): GenerarLote solo la
        # escribe si el lote tiene productos de farmacia. Se decide por
        # el mismo dato que decidio GenerarLote (hay productos o no), no
        # por si el archivo existe en disco -- eso mantendria esta
        # consulta pura y verificable sin tocar el filesystem.
        if "T4" in tablas and not await self._lote_tiene_productos(lote_id):
            tablas.remove("T4")
        archivos = tuple(
            _ruta_archivo(directorio, PREFIJO_ARCHIVO_POR_TABLA[tabla], identidad)
            for tabla in tablas
        )
        return LoteParaCargarValidador(
            lote_id=lote.id, numero=lote.numero, periodo=lote.periodo, archivos=archivos
        )

    async def _obtener_ipress_propia(self) -> IpressModelo:
        resultado = await self._sesion.execute(sa.select(IpressModelo).limit(1))
        ipress = resultado.scalar_one()
        return ipress

    async def _lote_tiene_productos(self, lote_id: int) -> bool:
        consulta = (
            sa.select(ProductoFacturadoModelo.id)
            .join(
                DocumentoFacturadorModelo,
                DocumentoFacturadorModelo.cuenta_id == ProductoFacturadoModelo.cuenta_medica_id,
            )
            .join(
                LoteDocumentoModelo,
                LoteDocumentoModelo.documento_id == DocumentoFacturadorModelo.id,
            )
            .where(LoteDocumentoModelo.lote_id == lote_id)
            .limit(1)
        )
        resultado = await self._sesion.execute(consulta)
        return resultado.first() is not None

    async def obtener_estado_lote(self, lote_id: int) -> str | None:
        lote = await self._sesion.get(LoteFacturacionModelo, lote_id)
        return lote.estado if lote is not None else None

    async def existe_validacion_conforme(self, lote_id: int, etapa: str) -> bool:
        resultado = await self._sesion.execute(
            sa.select(ValidacionOficialModelo.id).where(
                ValidacionOficialModelo.lote_id == lote_id,
                ValidacionOficialModelo.etapa == etapa,
                ValidacionOficialModelo.resultado == "CONFORME",
            )
        )
        return resultado.first() is not None

    async def registrar_validacion(self, datos: DatosRegistrarValidacion) -> int:
        resultado = datos.resultado
        validacion = ValidacionOficialModelo(
            lote_id=datos.lote_id,
            trabajo_id=datos.trabajo_id,
            etapa=datos.etapa,
            resultado="CONFORME" if resultado.conforme else "OBSERVADO",
            estado_informado_validador=resultado.estado_informado,
            ruta_reporte=datos.ruta_reporte,
            sha256_reporte=datos.sha256_reporte,
            registrado_en=datos.instante,
        )
        self._sesion.add(validacion)
        await self._sesion.flush()
        self._sesion.add_all(_a_modelos_observacion(validacion.id, resultado.observaciones))

        nuevo_estado = _estado_lote_tras_etapa(datos.etapa, resultado.conforme)
        if nuevo_estado is not None:
            await self._sesion.execute(
                sa.update(LoteFacturacionModelo)
                .where(LoteFacturacionModelo.id == datos.lote_id)
                .values(estado=nuevo_estado)
            )

        await self._sesion.commit()
        return validacion.id

    async def registrar_archivo_transmision(
        self, lote_id: int, archivo: ArchivoLote, ruta_s01: str, sha256_s01: str, instante: datetime
    ) -> None:
        await self._sesion.execute(
            sa.update(LoteFacturacionModelo)
            .where(LoteFacturacionModelo.id == lote_id)
            .values(
                estado="VALIDADO",
                nombre_s01=archivo.nombre,
                sha256_s01=sha256_s01,
                ruta_s01=ruta_s01,
                s01_obtenido_en=instante,
            )
        )
        await self._sesion.commit()

    async def obtener_lotes_para_envio_susalud(
        self, periodo: str
    ) -> tuple[LoteParaEnvioSusalud, ...]:
        resultado = await self._sesion.execute(
            sa.select(LoteFacturacionModelo).where(
                LoteFacturacionModelo.periodo == periodo,
                LoteFacturacionModelo.estado.in_(ESTADOS_ENVIABLES_SUSALUD),
                LoteFacturacionModelo.enviado_susalud_en.is_(None),
            )
        )
        lotes = resultado.scalars().all()
        return tuple(
            LoteParaEnvioSusalud(lote_id=lote.id, numero=lote.numero, periodo=lote.periodo)
            for lote in lotes
        )

    async def marcar_enviados_susalud(self, lote_ids: tuple[int, ...], instante: datetime) -> None:
        await self._sesion.execute(
            sa.update(LoteFacturacionModelo)
            .where(LoteFacturacionModelo.id.in_(lote_ids))
            .values(enviado_susalud_en=instante)
        )
        await self._sesion.commit()


def _ruta_archivo(directorio: Path, prefijo: str, identidad: IdentidadTrama) -> RutaArchivoLote:
    nombre = nombre_archivo_txt(prefijo, identidad)
    return RutaArchivoLote(nombre=nombre, ruta=str(directorio / nombre))


def _estado_lote_tras_etapa(etapa: str, conforme: bool) -> str | None:
    if not conforme:
        return _ESTADO_OBSERVADO_VALIDADOR
    if etapa == "FORMA":
        return _ESTADO_CARGADO_VALIDADOR
    return None  # DETALLADA conforme: RegistrarArchivoTransmision pone VALIDADO.


def _a_modelos_observacion(
    validacion_oficial_id: int, observaciones: tuple[ObservacionLectura, ...]
) -> list[ObservacionValidadorModelo]:
    return [
        ObservacionValidadorModelo(
            validacion_oficial_id=validacion_oficial_id,
            tabla=obs.tabla,
            numero_linea=obs.numero_linea,
            campo_clave=obs.campo_clave,
            campo=obs.campo,
            valor_observado=obs.valor_observado,
            codigo_error=obs.codigo_error,
            descripcion=obs.descripcion,
        )
        for obs in observaciones
    ]
