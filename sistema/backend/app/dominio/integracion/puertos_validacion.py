"""Puertos del flujo de validacion oficial (Seccion 8.3 del plan v3,
Fase 16). Separado de puertos.py para no superar el limite de 400 lineas
por archivo (GUIA_ESTILO_CODIGO.md, Seccion 3) -- mismo motivo que separo
modelos_plataformas.py de modelos_integracion.py en la Fase 13.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.dominio.integracion.vigencia_lote import VigenciaLote


class ErrorLoteNoCargable(Exception):
    """El lote no existe o no esta en estado GENERADO (Seccion 8.3:
    'SolicitarCargaEnValidador verifica que el lote este GENERADO')."""


@dataclass(frozen=True, slots=True)
class ArchivoLote:
    """Un archivo cualquiera que cruza la frontera con el validador TEDEF
    Web: un `.txt` que se sube, un reporte `.xlsx` que se descarga, o el
    `.S01` final -- siempre nombre mas contenido crudo."""

    nombre: str
    contenido: bytes


@dataclass(frozen=True, slots=True)
class ObservacionLectura:
    """Una fila de un reporte de observaciones del validador (Seccion
    9.2: tabla, numero de linea, campo clave, campo, valor observado,
    codigo, descripcion). La revision de forma solo puebla `tabla`,
    `codigo_error` y `descripcion`; el resto queda en None -- ese reporte
    no tiene esas columnas (ver app/reportes.py del simulador)."""

    tabla: str | None
    numero_linea: int | None
    campo_clave: str | None
    campo: str | None
    valor_observado: str | None
    codigo_error: str
    descripcion: str


@dataclass(frozen=True, slots=True)
class ResultadoEtapaValidador:
    """Lo que devuelve el robot tras la revision de forma o la
    validacion detallada (Seccion 7, flujo de extremo a extremo):
    conforme, o observado con su reporte `.xlsx` crudo (para calcular la
    huella y guardarlo) y las observaciones ya leidas de el.
    `estado_informado` es el texto/estado literal que mostro el
    validador (Seccion 10: `estado_informado_validador`), para
    trazabilidad frente a lo que vio un humano."""

    conforme: bool
    estado_informado: str | None
    observaciones: tuple[ObservacionLectura, ...] = ()
    reporte: ArchivoLote | None = None


@dataclass(frozen=True, slots=True)
class ContextoCargaValidador:
    """Objeto de parametros: lo que ValidadorTedefWeb.cargar_lote
    necesita para registrar un lote nuevo en 'Lotes por Validar'."""

    numero: str
    periodo: str
    archivos: tuple[ArchivoLote, ...]


@dataclass(frozen=True, slots=True)
class IdentidadLoteTedef:
    """numero de lote + periodo: lo minimo para que el robot vuelva a
    encontrar la fila de un lote ya registrado en el validador, dado que
    este puerto no conserva el id interno del simulador entre llamadas
    (cada metodo abre y cierra su propio contexto de navegador, Seccion
    8.1: mismo patron que AcreditacionWeb y AsistenteSesionPlataforma)."""

    numero: str
    periodo: str


class ValidadorTedefWeb(Protocol):
    """Puerto de la Seccion 8.3. Unica implementacion:
    AdaptadorValidadorTedefWeb (Playwright), en
    sistema/automatizacion/trabajador/robots/ -- la unica pieza del
    sistema que importa Playwright es el trabajador (AD-02).

    Simplificado frente a la lista de metodos sugerida en la Seccion 8.3
    (`cargar_lote, consultar_revision_forma, validar_lote,
    consultar_validacion, descargar_reporte_observaciones,
    descargar_archivo_transmision, enviar_a_susalud`): aqui
    `cargar_lote` ya incluye la lectura de la revision de forma y
    `validar_lote` ya incluye la espera y lectura de la validacion
    detallada, siguiendo el mismo patron que AsistenteSesionPlataforma
    (Fase 15) -- cada metodo es una operacion completa y autonoma que
    abre y cierra su propio contexto de navegador, en vez de mantener
    estado de pagina entre llamadas. Cubre exactamente los mismos pasos
    del flujo de la Seccion 7, con menos superficie de puerto."""

    async def cargar_lote(self, contexto: ContextoCargaValidador) -> ResultadoEtapaValidador:
        """Sube los `.txt` a 'Lotes por Validar' y lee la revision de
        forma (Seccion 9.2, punto 4)."""
        ...

    async def validar_lote(self, identidad: IdentidadLoteTedef) -> ResultadoEtapaValidador:
        """Marca el lote, ejecuta 'Validar lotes' y espera el resultado
        en segundo plano, refrescando la tabla hasta que resuelva
        (Seccion 9.2, punto 4)."""
        ...

    async def descargar_archivo_transmision(self, identidad: IdentidadLoteTedef) -> ArchivoLote:
        """El `.S01` cifrado, desde 'Lotes por Enviar' (Seccion 9.2,
        punto 5)."""
        ...

    async def enviar_a_susalud(self, lotes: tuple[IdentidadLoteTedef, ...]) -> None:
        """'Enviar Lotes' de 'Lotes por Enviar' (Seccion 9.2, punto 5)."""
        ...


@dataclass(frozen=True, slots=True)
class RutaArchivoLote:
    """Nombre y ruta en disco de un `.txt` ya escrito por GenerarLote,
    sin su contenido -- mismo patron que `LoteParaRemitir.ruta_s01`
    (Seccion 7.8): el repositorio resuelve la ruta, quien la lee de
    disco es el caso de uso de infraestructura que la recibe
    (CargarLoteEnValidador), no el repositorio."""

    nombre: str
    ruta: str


@dataclass(frozen=True, slots=True)
class LoteParaCargarValidador:
    """Lo que CargarLoteEnValidador (infraestructura, por la misma razon
    que GenerarLote/RemitirLote: operacion de filesystem) necesita leer
    de un lote GENERADO: los `.txt` ya escritos en disco, localizados
    recomputando su nombre desde la identidad del lote -- nunca se
    persiste la ruta (mismo patron que nombrado.py usa para verificar el
    nombre del `.S01`, Fase 7/13)."""

    lote_id: int
    numero: str
    periodo: str
    archivos: tuple[RutaArchivoLote, ...]


@dataclass(frozen=True, slots=True)
class LoteParaEnvioSusalud:
    lote_id: int
    numero: str
    periodo: str


@dataclass(frozen=True, slots=True)
class DatosRegistrarValidacion:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo que
    RepositorioValidacionOficial.registrar_validacion necesita para
    persistir el resultado de una etapa. Subconjunto de
    DatosValidacionEtapa (app/dominio/integracion/casos_uso_validacion.py):
    ese objeto tiene ademas `estado_previo`, que solo usa
    RegistrarResultadoValidador para construir el Evento, no el
    repositorio."""

    lote_id: int
    trabajo_id: int | None
    etapa: str
    resultado: ResultadoEtapaValidador
    ruta_reporte: str | None
    sha256_reporte: str | None
    instante: datetime


class RepositorioValidacionOficial(Protocol):
    """Puerto de persistencia del flujo de validacion oficial (Seccion
    8.3 y 10)."""

    async def obtener_lote_para_carga(self, lote_id: int) -> LoteParaCargarValidador | None:
        """None si el lote no existe."""
        ...

    async def obtener_estado_lote(self, lote_id: int) -> str | None:
        """None si el lote no existe."""
        ...

    async def obtener_numero_lote(self, lote_id: int) -> str | None:
        """El numero visible del lote; None si no existe."""
        ...

    async def vigencia_lote(self, lote_id: int) -> VigenciaLote | None:
        """Lo que hace falta para saber si el lote sigue vigente; None si
        no existe."""
        ...

    async def existe_validacion_conforme(self, lote_id: int, etapa: str) -> bool:
        """Seccion 8.1, punto 6: un reintento de CARGAR_LOTE_VALIDADOR no
        debe repetir un paso que ya tuvo exito -- volver a subir un lote
        ya conforme en 'FORMA' hace que el validador lo rechace como
        duplicado (Seccion 9.2: 'lote no registrado antes'). Usado por
        CargarLoteEnValidador para decidir desde donde reanudar."""
        ...

    async def registrar_validacion(self, datos: DatosRegistrarValidacion) -> int:
        """Persiste `validacion_oficial` + `observacion_validador`
        (Seccion 10) y ajusta `lote.estado` (Seccion 8.3):
        CARGADO_VALIDADOR si la revision de forma fue conforme,
        OBSERVADO_VALIDADOR si hubo observaciones en cualquier etapa,
        sin cambio si es la validacion detallada conforme
        (RegistrarArchivoTransmision se encarga de VALIDADO). Devuelve
        el id de `validacion_oficial` creado."""
        ...

    async def registrar_archivo_transmision(
        self, lote_id: int, archivo: ArchivoLote, ruta_s01: str, sha256_s01: str, instante: datetime
    ) -> None:
        """Seccion 8.3: guarda nombre, huella y ruta del `.S01` obtenido
        y cambia el lote a VALIDADO. La escritura del archivo en el
        volumen de artefactos ya ocurrio antes de llamar a este metodo
        (responsabilidad de CargarLoteEnValidador, no de este puerto);
        `ruta_s01` es donde quedo escrito."""
        ...

    async def obtener_lotes_para_envio_susalud(
        self, periodo: str
    ) -> tuple[LoteParaEnvioSusalud, ...]:
        """Lotes del periodo en estado VALIDADO o posterior (Seccion
        8.3: REMITIDO_IAFAS, ACEPTADO, RECHAZADO tambien califican) que
        todavia no tienen `enviado_susalud_en`."""
        ...

    async def marcar_enviados_susalud(self, lote_ids: tuple[int, ...], instante: datetime) -> None:
        """Fija `enviado_susalud_en` (Seccion 10): no cambia
        `lote.estado`, que sigue describiendo el ciclo de remision a la
        IAFAS, no el reporte regulatorio a SUSALUD."""
        ...
