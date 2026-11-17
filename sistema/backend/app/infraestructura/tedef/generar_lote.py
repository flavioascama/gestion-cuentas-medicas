"""Caso de uso GenerarLote (Seccion 7.6).

Vive en infraestructura/tedef/, no en dominio/integracion/: orquesta
directamente el escritor de ancho fijo, el constructor y los validadores
de esta misma carpeta, que son logica de formato TEDEF sin alternativa
intercambiable (no tiene sentido un puerto para "otra forma de escribir
ancho fijo"). Lo que si varia por entorno son la persistencia y los
puertos comunes (RegistroEventos, RegistroMediciones, Reloj), inyectados
como de costumbre.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.dominio.integracion.esquema import TablaEsquema
from app.dominio.integracion.hallazgos import Hallazgo
from app.dominio.integracion.lote import ContextoLote, DocumentoLote
from app.dominio.integracion.lotes_sugeridos import periodo_unico
from app.dominio.integracion.puertos import DatosLoteConforme, RepositorioLoteFacturacion
from app.dominio.puertos_comunes import (
    Evento,
    MedicionPaso,
    RegistroEventos,
    RegistroMediciones,
    Reloj,
)
from app.infraestructura.tedef.carga_esquema import cargar_esquema
from app.infraestructura.tedef.carga_tablas_activas import cargar_tablas_activas
from app.infraestructura.tedef.consistencia_tablas import validar_consistencia
from app.infraestructura.tedef.constructor_lote import (
    construir_t1,
    construir_t2,
    construir_t3,
    construir_t4,
)
from app.infraestructura.tedef.escritor_ancho_fijo import ensamblar_archivo, escribir_registro
from app.infraestructura.tedef.nombrado import (
    PREFIJO_ARCHIVO_POR_TABLA,
    IdentidadTrama,
    nombre_archivo_txt,
)
from app.infraestructura.tedef.validador_campo import validar_registro

# Tasa de IGV vigente en el Peru (Ley del IGV, 18%): supuesto documentado
# (docs/DECISIONES.md), no una formula del Anexo 1. Ver mapeo T1 campo 23.
TASA_IGV = Decimal("0.18")


@dataclass(frozen=True, slots=True)
class InformeValidacionLote:
    numero_lote: str
    conforme: bool
    hallazgos: tuple[Hallazgo, ...]

    @property
    def errores(self) -> tuple[Hallazgo, ...]:
        return tuple(h for h in self.hallazgos if h.severidad == "error")

    @property
    def advertencias(self) -> tuple[Hallazgo, ...]:
        return tuple(h for h in self.hallazgos if h.severidad == "advertencia")


Filas = tuple[
    list[dict[int, str]], list[dict[int, str]], list[dict[int, str]], list[dict[int, str]]
]


def _construir_filas(
    esquema: dict[str, TablaEsquema], contexto: ContextoLote, documentos: list[DocumentoLote]
) -> Filas:
    """T1 depende de los valores ya construidos de T2 (Seccion 7.6, campo
    "cantidad de prestaciones"), y T3/T4 dependen de la prestacion de T2 a
    la que pertenece cada procedimiento o producto -- por eso se arman en
    este orden, no tabla por tabla. T4 solo aporta filas para las
    prestaciones que tengan productos registrados (Seccion 8.1)."""

    filas_t1: list[dict[int, str]] = []
    filas_t2: list[dict[int, str]] = []
    filas_t3: list[dict[int, str]] = []
    filas_t4: list[dict[int, str]] = []
    for documento in documentos:
        valores_t2 = construir_t2(
            esquema["T2"], contexto, documento, documento.prestacion.procedimientos
        )
        filas_t2.append(valores_t2)
        filas_t1.append(construir_t1(esquema["T1"], contexto, documento, valores_t2))
        for procedimiento in documento.prestacion.procedimientos:
            filas_t3.append(construir_t3(esquema["T3"], contexto, documento, procedimiento))
        for producto in documento.prestacion.productos:
            filas_t4.append(construir_t4(esquema["T4"], contexto, documento, producto))
    return filas_t1, filas_t2, filas_t3, filas_t4


def _validar_filas(esquema: dict[str, TablaEsquema], filas: Filas) -> list[Hallazgo]:
    filas_t1, filas_t2, filas_t3, filas_t4 = filas
    hallazgos: list[Hallazgo] = []
    for fila in filas_t1:
        hallazgos.extend(validar_registro(esquema["T1"], fila))
    for fila in filas_t2:
        hallazgos.extend(validar_registro(esquema["T2"], fila))
    for fila in filas_t3:
        hallazgos.extend(validar_registro(esquema["T3"], fila))
    for fila in filas_t4:
        hallazgos.extend(validar_registro(esquema["T4"], fila))
    hallazgos.extend(validar_consistencia(filas_t1, filas_t2, filas_t3, filas_t4))
    return hallazgos


@dataclass(frozen=True, slots=True)
class ResultadoGenerarLote:
    conforme: bool
    informe: InformeValidacionLote
    lote_id: int | None
    # Uno por tabla activa (Seccion 8.1 del plan v3): ya no un solo `.S01`
    # comprimido, sino los `.txt` sin comprimir tal como los produce este
    # sistema -- el `.S01` lo arma y cifra el validador TEDEF Web (Fase 16).
    rutas_archivos: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class _LoteGenerado:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): agrupa lo
    que `_persistir_lote_conforme` necesita de un lote ya construido y
    validado. `iafas_id` viaja aparte de `contexto` porque `ContextoLote`
    (dominio/integracion/lote.py) es del constructor de tramas -- solo
    conoce `codigo_iafas` (el dato de negocio), no el id de fila de la
    base de datos."""

    iafas_id: int
    contexto: ContextoLote
    documentos: list[DocumentoLote]
    filas: Filas


class GenerarLote:
    def __init__(
        self,
        repositorio: RepositorioLoteFacturacion,
        registro_eventos: RegistroEventos,
        registro_mediciones: RegistroMediciones,
        reloj: Reloj,
        directorio_salida: Path,
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos
        self._registro_mediciones = registro_mediciones
        self._reloj = reloj
        self._directorio_salida = directorio_salida

    async def ejecutar(
        self, iafas_id: int, periodo: str | None, cuenta_ids: list[int], actor: str
    ) -> ResultadoGenerarLote:
        inicio = self._reloj.ahora()
        esquema = cargar_esquema()
        # Seccion 8.1 del plan v3: valida contra tablas_activas.yaml (T1 a
        # T3 hasta cerrar la Fase 17); si algun dia pide una tabla que este
        # generador todavia no construye, falla al arrancar, no a mitad de
        # lote.
        cargar_tablas_activas()

        documentos = await self._repositorio.obtener_documentos_facturados(iafas_id, cuenta_ids)
        # Sin periodo explicito (asi lo pide la pantalla) es el mes de emision
        # de los comprobantes; si abarcan mas de un mes, el lote no se genera.
        periodo_lote = periodo or periodo_unico(d.fecha_emision for d in documentos)
        contexto = await self._preparar_contexto(iafas_id, periodo_lote, inicio)
        filas = _construir_filas(esquema, contexto, documentos)
        hallazgos = _validar_filas(esquema, filas)
        lote = _LoteGenerado(
            iafas_id=iafas_id, contexto=contexto, documentos=documentos, filas=filas
        )

        conforme = bool(documentos) and not any(h.severidad == "error" for h in hallazgos)
        informe = InformeValidacionLote(
            numero_lote=contexto.numero_lote, conforme=conforme, hallazgos=tuple(hallazgos)
        )
        await self._registrar_medicion_validacion(inicio, actor, documentos, informe)

        if not conforme:
            # Sin lote_id (no se persiste ningun lote cuando no es
            # conforme): no hay agregado al que asociar un Evento (Fase
            # 24), asi que el resultado queda solo en la medicion de
            # arriba, que ya distingue "conforme"/"no_conforme".
            return ResultadoGenerarLote(
                conforme=False, informe=informe, lote_id=None, rutas_archivos=None
            )

        return await self._persistir_lote_conforme(lote, informe, actor)

    async def _preparar_contexto(
        self, iafas_id: int, periodo: str, inicio: datetime
    ) -> ContextoLote:
        ruc_ipress, codigo_ipress = await self._repositorio.obtener_ipress_propia()
        codigo_iafas = await self._repositorio.obtener_codigo_iafas(iafas_id)
        numero_lote = await self._repositorio.siguiente_numero_lote(iafas_id)
        return ContextoLote(
            numero_lote=numero_lote,
            periodo=periodo,
            generado_en=inicio,
            ruc_ipress=ruc_ipress,
            codigo_ipress=codigo_ipress,
            codigo_iafas=codigo_iafas,
            tasa_igv=TASA_IGV,
        )

    async def _persistir_lote_conforme(
        self, lote: _LoteGenerado, informe: InformeValidacionLote, actor: str
    ) -> ResultadoGenerarLote:
        contexto = lote.contexto
        identidad = IdentidadTrama(
            ruc=contexto.ruc_ipress,
            codigo_ipress=contexto.codigo_ipress,
            codigo_iafas=contexto.codigo_iafas,
            numero_lote=contexto.numero_lote,
            periodo=contexto.periodo,
            fecha=contexto.generado_en.date(),
        )
        rutas_archivos = self._escribir_archivos(cargar_esquema(), identidad, lote.filas)

        lote_id = await self._repositorio.guardar_lote_conforme(
            DatosLoteConforme(
                iafas_id=lote.iafas_id,
                numero=contexto.numero_lote,
                periodo=contexto.periodo,
                generado_en=contexto.generado_en,
                documento_ids=[d.documento_id for d in lote.documentos],
                hallazgos=informe.hallazgos,
            )
        )
        await self._registrar_evento_generado(actor, lote_id, contexto.numero_lote, rutas_archivos)

        return ResultadoGenerarLote(
            conforme=True, informe=informe, lote_id=lote_id, rutas_archivos=tuple(rutas_archivos)
        )

    async def _registrar_medicion_validacion(
        self,
        inicio: datetime,
        actor: str,
        documentos: list[DocumentoLote],
        informe: InformeValidacionLote,
    ) -> None:
        await self._registro_mediciones.registrar(
            MedicionPaso(
                paso="generacion_validacion_lote",
                inicio=inicio,
                fin=self._reloj.ahora(),
                actor=actor,
                resultado="conforme" if informe.conforme else "no_conforme",
                datos={
                    "numero_lote": informe.numero_lote,
                    "documentos": len(documentos),
                    "errores": len(informe.errores),
                },
            )
        )

    def _escribir_archivos(
        self, esquema: dict[str, TablaEsquema], identidad: IdentidadTrama, filas: Filas
    ) -> list[str]:
        """Seccion 8.1 del plan v3: escribe los .txt sin comprimir y sin
        producir un .S01 -- eso lo obtiene el validador TEDEF Web (Fase
        16). nombrado.py conserva el calculo del nombre esperado del .S01
        solo para esa fase, que lo usa para verificar coherencia contra lo
        que el validador devuelva."""

        filas_t1, filas_t2, filas_t3, filas_t4 = filas
        archivos = {
            nombre_archivo_txt(PREFIJO_ARCHIVO_POR_TABLA["T1"], identidad): ensamblar_archivo(
                [escribir_registro(esquema["T1"], f) for f in filas_t1]
            ),
            nombre_archivo_txt(PREFIJO_ARCHIVO_POR_TABLA["T2"], identidad): ensamblar_archivo(
                [escribir_registro(esquema["T2"], f) for f in filas_t2]
            ),
            nombre_archivo_txt(PREFIJO_ARCHIVO_POR_TABLA["T3"], identidad): ensamblar_archivo(
                [escribir_registro(esquema["T3"], f) for f in filas_t3]
            ),
        }
        # T4 es condicional (Seccion 8.1): sin productos registrados, no
        # se escribe ningun archivo dfar, a diferencia de T1-T3, que
        # siempre estan presentes.
        if filas_t4:
            archivos[nombre_archivo_txt(PREFIJO_ARCHIVO_POR_TABLA["T4"], identidad)] = (
                ensamblar_archivo([escribir_registro(esquema["T4"], f) for f in filas_t4])
            )

        self._directorio_salida.mkdir(parents=True, exist_ok=True)
        rutas_archivos: list[str] = []
        for nombre, contenido in archivos.items():
            ruta = self._directorio_salida / nombre
            ruta.write_bytes(contenido)
            rutas_archivos.append(str(ruta))
        return rutas_archivos

    async def _registrar_evento_generado(
        self, actor: str, lote_id: int, numero_lote: str, rutas_archivos: list[str]
    ) -> None:
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento="LOTE_GENERADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "lote_id": lote_id,
                    "numero_lote": numero_lote,
                    "archivos": [Path(r).name for r in rutas_archivos],
                },
            )
        )
