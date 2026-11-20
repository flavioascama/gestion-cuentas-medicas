"""Puertos del contexto de integracion TEDEF (Seccion 5.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.dominio.integracion.hallazgos import Hallazgo
from app.dominio.integracion.lote import DocumentoLote
from app.dominio.integracion.vigencia_lote import VigenciaLote


class ErrorRepositorioLote(Exception):
    pass


class ErrorLoteNoRemisible(Exception):
    """El lote no existe, no esta conforme o ya fue remitido con exito
    (Seccion 7.8, punto 1: 'Verifica que el lote este conforme y no
    remitido'). Un lote no conforme nunca llega a persistirse (GenerarLote
    solo guarda lotes conformes), asi que en la practica esta excepcion
    cubre "no existe" y "ya remitido"."""


class ErrorLoteNoMonitoreable(Exception):
    """El lote no existe, o no tiene un acuse de transmision exitoso
    todavia sin respuesta del receptor (Seccion 8.3)."""


class RepositorioLoteFacturacion(Protocol):
    """Un solo puerto para leer los documentos facturables y persistir el
    lote generado (Seccion 7.6): ambos los usa exclusivamente el caso de
    uso GenerarLote, separarlos en dos puertos no aporta swappability
    real en esta fase."""

    async def obtener_ipress_propia(self) -> tuple[str, str]:
        """(ruc, codigo_ipress) de la clinica que opera el sistema."""
        ...

    async def obtener_codigo_iafas(self, iafas_id: int) -> str: ...

    async def obtener_documentos_facturados(
        self, iafas_id: int, cuenta_ids: list[int]
    ) -> list[DocumentoLote]:
        """Solo cuentas en estado FACTURADA (Seccion 7.6, punto 1)."""
        ...

    async def siguiente_numero_lote(self, iafas_id: int) -> str:
        """7 digitos, transaccional y unico por IAFAS (Seccion 7.6, punto 2)."""
        ...

    async def guardar_lote_conforme(self, datos: DatosLoteConforme) -> int:
        """Devuelve el id del lote_facturacion creado, en estado GENERADO.
        Sin datos del `.S01` todavia (Regla 11 del plan v3: el backend ya
        no lo produce): eso lo completa RegistrarArchivoTransmision
        (Fase 16) cuando el lote llegue a VALIDADO. En la misma
        transaccion persiste tambien el informe de prevalidacion (Fase
        18, `GET /lotes/{id}/prevalidacion`) -- un lote conforme puede
        tener advertencias, aunque nunca errores."""
        ...


@dataclass(frozen=True, slots=True)
class DatosLoteConforme:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2) para
    `guardar_lote_conforme`: ya eran 5 argumentos antes de la Fase 18;
    agregar los hallazgos de prevalidacion como un sexto habria superado
    el limite de parametros por funcion (Seccion 3)."""

    iafas_id: int
    numero: str
    periodo: str
    generado_en: datetime
    documento_ids: list[int]
    hallazgos: tuple[Hallazgo, ...]


@dataclass(frozen=True, slots=True)
class LoteParaRemitir:
    """Lo que RemitirLote (Seccion 7.8, ajustado en la Fase 13) necesita
    leer de un lote ya validado. `estado` se usa para el punto 1 del caso
    de uso; `documento_ids` para fijar `fecha_primer_envio` en cada uno
    (punto 4). `nombre_s01`/`sha256_s01`/`ruta_s01` son `None` mientras el
    lote no llego a VALIDADO -- RemitirLote los usa recien despues de
    verificar el estado, nunca antes."""

    lote_id: int
    numero: str
    estado: str
    nombre_s01: str | None
    sha256_s01: str | None
    ruta_s01: str | None
    documento_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ResultadoTransmision:
    """Resultado de un intento de transferencia (no confundir con la
    respuesta de negocio del receptor -- ACEPTADO o RECHAZADO -- que llega
    despues, por el robot de monitoreo de la Fase 12)."""

    exitosa: bool
    motivo: str | None = None


class Transmisor(Protocol):
    """Puerto de la Seccion 7.8, punto 2: 'Transfiere el .S01 por FTP
    mediante el adaptador TransmisorFtp, que implementa el puerto
    Transmisor'. Generico a proposito -- el nombre del puerto no dice FTP--
    para que un OE futuro pueda sustituir el mecanismo de transporte."""

    async def transmitir(self, nombre_archivo: str, contenido: bytes) -> ResultadoTransmision: ...


class RepositorioLoteRemision(Protocol):
    """Puerto de la Seccion 7.8: lectura del lote a remitir y persistencia
    del ciclo de remision. Puerto separado de RepositorioLoteFacturacion
    porque lo usa un caso de uso distinto (RemitirLote, no GenerarLote) con
    necesidades de lectura y escritura distintas."""

    async def obtener_lote_para_remision(self, lote_id: int) -> LoteParaRemitir | None:
        """None si el lote_id no existe."""
        ...

    async def vigencia_lote(self, lote_id: int) -> VigenciaLote | None:
        """Lo que hace falta para saber si el lote sigue vigente; None si
        no existe."""
        ...

    async def registrar_remision(
        self,
        lote_id: int,
        documento_ids: tuple[int, ...],
        exitosa: bool,
        motivo: str | None,
        instante: datetime,
    ) -> tuple[int, tuple[int, ...]]:
        """Persiste acuse_transmision (Seccion 6.1) y, solo si `exitosa`:
        fija `fecha_primer_envio` en cada documento que aun no la tenga sin
        sobrescribir el valor existente (punto 4, protegido ademas por el
        disparador de la Fase 7), cambia el lote a REMITIDO y las cuentas
        asociadas a ENVIADA (punto 5, T-03 validada por el motor de
        orquestacion). Devuelve (id de acuse_transmision, cuentas que
        pasaron a ENVIADA -- vacio si la transferencia fallo), para que
        RemitirLote registre el evento propio de cada cuenta (RF-16)."""
        ...


@dataclass(frozen=True, slots=True)
class ContextoLoteMonitoreo:
    """Lo que MonitorearRespuestaIafas (Seccion 8.3) necesita leer de un
    lote ya remitido: el nombre exacto con el que se busca en el portal
    del receptor, y la ventana maxima de espera de su IAFAS (punto 5)."""

    lote_id: int
    numero: str
    nombre_s01: str
    ventana_monitoreo_horas: int


@dataclass(frozen=True, slots=True)
class RespuestaReceptor:
    """Lo que devuelve ConsultorRespuestaReceptor cuando el portal ya
    tiene una decision para el lote (Seccion 9.2: 'ACEPTADO' o
    'RECHAZADO' con motivo textual)."""

    estado: str
    motivo: str | None


class ConsultorRespuestaReceptor(Protocol):
    """Puerto sobre el portal de respuestas del simulador receptor IAFAS
    (Fase 8, Seccion 9.2). A diferencia de AcreditacionWeb (Fase 11), ese
    portal no tiene sesion ni pasos interactivos -- una sola lectura HTTP
    de una pagina ya renderizada -- por eso este puerto no necesita
    Playwright del otro lado; su unica implementacion (Fase 12) hace un
    GET simple y lee el HTML con un parser, no con un navegador."""

    async def consultar(self, nombre_s01: str) -> RespuestaReceptor | None:
        """None si el portal todavia no tiene ese lote (Seccion 8.3,
        punto 3: 'el receptor aun no publico respuesta')."""
        ...


class RepositorioMonitoreoRespuesta(Protocol):
    async def obtener_contexto_lote(self, lote_id: int) -> ContextoLoteMonitoreo | None:
        """None si el lote no existe."""
        ...

    async def aplicar_respuesta(
        self, lote_id: int, estado_receptor: str, motivo: str | None, instante: datetime
    ) -> tuple[int, tuple[int, ...]]:
        """Completa el acuse_transmision mas reciente de ese lote que
        seguia sin respuesta (`respuesta_receptor`, `motivo_receptor`,
        `respondido_en`), cambia `lote_facturacion.estado` a
        `estado_receptor` y, validado contra el motor de orquestacion
        (RF-08), cambia el estado de cada `cuenta_medica` del lote: a
        `RECHAZADA` si fue 'RECHAZADO' (Seccion 8.3, punto 4), o a
        `EN_AUDITORIA` si fue 'ACEPTADO' (T-06, Seccion 5.2.4). Devuelve
        (acuse_id, cuenta_medica_ids afectadas -- en ambos casos desde
        la Fase 25, antes solo con 'RECHAZADO')."""
        ...
