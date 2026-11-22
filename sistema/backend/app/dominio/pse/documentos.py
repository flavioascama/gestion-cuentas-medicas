"""CU-10 (refacturacion) y RI-11 (notas de credito y debito): el
comprobante vigente de la cuenta, su reemplazo por uno nuevo al refacturar
y la nota que lo ajusta.

- Comprobante de reemplazo: al refacturar una cuenta glosada o rechazada,
  el PSE emite un comprobante nuevo que pasa a ser el vigente; el anterior
  queda en `comprobante_reemplazado` con el motivo, y el lote siguiente
  transmite el nuevo. Se conserva la fecha del primer envio (T-05).
- Nota de credito o debito: la Tabla 1 del Anexo 1 tiene un solo espacio
  de nota por documento (campos 25 a 29: tipo C o D, numero serie+numero,
  monto sin IGV, fecha y motivo R, A o D); por eso se admite una nota por
  comprobante, que el lote siguiente transmite. Sin nota, el lote sigue
  transmitiendo "N" y los campos en blanco. La serie, el numero y la fecha
  de la nota los da el PSE al emitirla, igual que los del comprobante
  (2026-11-18: antes se escribian a mano).

Un comprobante con nota no se reemplaza: la nota es de ese comprobante.

En FACTURADA se reemplaza solo un comprobante desfasado (2026-11-21, calculo
del copago corregido); el estado no cambia y su lote en curso se desactualiza."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.compartido.nombres_estados import nombre_estado
from app.dominio.orquestacion.correccion_validador import admite_correccion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.pse.casos_uso import solicitud_comprobante
from app.dominio.pse.puertos import (
    ComprobanteEmitido,
    ComprobantePse,
    EmisorPse,
    NotaPse,
    RepositorioComprobantePago,
    RepositorioCotejoComprobante,
    SolicitudNota,
)
from app.dominio.pse.reemplazo_necesario import REEMPLAZO_INNECESARIO, estados_con_reemplazo
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

ESTADOS_CON_REEMPLAZO = frozenset({"RECHAZADA", "GLOSADA"})
ESTADOS_CON_NOTA = frozenset({"FACTURADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"})
# Orden en que se nombran los estados permitidos en un rechazo.
_ORDEN_ESTADOS = ("FACTURADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL")
_OPERACION_REEMPLAZO = "el comprobante de reemplazo solo se emite"
_OPERACION_NOTA = "la nota de crédito o débito solo se registra"
_CUANDO_MAS_SE_REEMPLAZA = (
    ", si el validador observó el lote de la cuenta o, en Facturada, si el comprobante ya no "
    "refleja la cuenta"
)
TIPOS_NOTA = frozenset({"C", "D"})
MOTIVOS_NOTA = frozenset({"R", "A", "D"})


class ErrorDocumentoPago(Exception):
    pass


class ErrorCuentaInexistenteDocumento(ErrorDocumentoPago):
    pass


class ErrorSinComprobante(ErrorDocumentoPago):
    pass


class ErrorEstadoNoAdmiteDocumento(ErrorDocumentoPago):
    pass


class ErrorNotaYaRegistrada(ErrorDocumentoPago):
    pass


class ErrorNotaInvalida(ErrorDocumentoPago):
    pass


class ErrorComprobanteConNota(ErrorDocumentoPago):
    pass


@dataclass(frozen=True, slots=True)
class ComprobanteVigente:
    documento_id: int
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date
    # Lo que factura (2026-11-18): valor de venta, IGV y total.
    valor_venta: Decimal | None = None
    igv: Decimal | None = None
    total: Decimal | None = None


@dataclass(frozen=True, slots=True)
class DatosNota:
    """Lo que decide la persona; la serie, el numero y la fecha son del PSE."""

    tipo: str
    monto: Decimal
    motivo: str


@dataclass(frozen=True, slots=True)
class NotaDocumento:
    tipo: str
    serie: str
    numero: str
    monto: Decimal
    fecha: date
    motivo: str
    registrado_en: datetime
    registrado_por: str


@dataclass(frozen=True, slots=True)
class ComprobanteReemplazado:
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date
    reemplazado_en: datetime
    reemplazado_por: str
    motivo: str


@dataclass(frozen=True, slots=True)
class DocumentosPagoCuenta:
    vigente: ComprobanteVigente
    nota: NotaDocumento | None
    reemplazados: list[ComprobanteReemplazado] = field(default_factory=list)
    # El comprobante vigente ya no refleja lo que hoy factura la cuenta.
    desfasado: bool = False


class RepositorioDocumentosPago(Protocol):
    async def documentos(self, cuenta_medica_id: int) -> DocumentosPagoCuenta | None:
        """None si la cuenta no tiene comprobante."""
        ...

    async def guardar_nota(self, documento_id: int, nota: NotaDocumento) -> None: ...

    async def reemplazar(
        self, cuenta_medica_id: int, nuevo: ComprobanteEmitido, reemplazo: ComprobanteReemplazado
    ) -> None:
        """Archiva el comprobante vigente con los datos de `reemplazo` y
        deja `nuevo` (con los montos enviados al PSE) como vigente en la
        misma fila."""
        ...


def _estados_permitidos(permitidos: frozenset[str], con_correccion: bool) -> str:
    nombres = [nombre_estado(estado) for estado in _ORDEN_ESTADOS if estado in permitidos]
    texto = ", ".join(nombres[:-1]) + " o " + nombres[-1]
    return texto + (_CUANDO_MAS_SE_REEMPLAZA if con_correccion else "")


async def _estado_exigido(
    estado_cuenta: RepositorioEstadoCuenta,
    cuenta_medica_id: int,
    permitidos: frozenset[str],
    operacion: str,
    con_correccion: bool = False,
) -> str:
    estado = await estado_cuenta.obtener_estado(cuenta_medica_id)
    if estado is None:
        raise ErrorCuentaInexistenteDocumento("No existe la cuenta.")
    admitido = estado in permitidos
    if con_correccion:
        admitido = await admite_correccion(estado_cuenta, cuenta_medica_id, admitido)
    if not admitido:
        raise ErrorEstadoNoAdmiteDocumento(
            f"La cuenta está en estado {nombre_estado(estado)}: {operacion} en estado "
            f"{_estados_permitidos(permitidos, con_correccion)}."
        )
    return estado


def _validar_nota(datos: DatosNota) -> None:
    errores: list[str] = []
    if datos.tipo not in TIPOS_NOTA:
        errores.append("el tipo de nota no es válido")
    if datos.motivo not in MOTIVOS_NOTA:
        errores.append("el motivo de la nota no es válido")
    if datos.monto <= 0:
        errores.append("el monto debe ser mayor que cero")
    if errores:
        raise ErrorNotaInvalida("; ".join(errores).capitalize() + ".")


def _validar_monto_nota(datos: DatosNota, vigente: ComprobanteVigente) -> None:
    # Solo se compara cuando se conoce el valor de venta del comprobante.
    if vigente.valor_venta is not None and datos.monto > vigente.valor_venta:
        raise ErrorNotaInvalida(
            f"El monto de la nota (S/ {datos.monto:.2f}) supera el valor de venta del "
            f"comprobante (S/ {vigente.valor_venta:.2f})."
        )


class ConsultarDocumentosPago:
    def __init__(
        self,
        repositorio: RepositorioDocumentosPago,
        cotejo: RepositorioCotejoComprobante | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._cotejo = cotejo

    async def ejecutar(self, cuenta_medica_id: int) -> DocumentosPagoCuenta | None:
        documentos = await self._repositorio.documentos(cuenta_medica_id)
        if documentos is None or self._cotejo is None:
            return documentos
        cotejo = await self._cotejo.cotejar(cuenta_medica_id)
        return replace(documentos, desfasado=cotejo.desfasado)


@dataclass(frozen=True, slots=True)
class EmisionPse:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo que
    hace falta para pedir un comprobante al PSE; con `cotejo`, el reemplazo
    sabe si el comprobante vigente quedo desfasado."""

    comprobantes: RepositorioComprobantePago
    emisor: EmisorPse
    cotejo: RepositorioCotejoComprobante | None = None


class RegistrarNotaDocumento:
    def __init__(
        self,
        repositorio: RepositorioDocumentosPago,
        emision: EmisionPse,
        estado_cuenta: RepositorioEstadoCuenta,
        registro_eventos: RegistroEventos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._comprobantes = emision.comprobantes
        self._emisor = emision.emisor
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(self, cuenta_medica_id: int, datos: DatosNota, actor: str) -> NotaDocumento:
        await _estado_exigido(
            self._estado_cuenta, cuenta_medica_id, ESTADOS_CON_NOTA, _OPERACION_NOTA
        )
        documentos = await self._repositorio.documentos(cuenta_medica_id)
        if documentos is None:
            raise ErrorSinComprobante("La cuenta no tiene comprobante.")
        if documentos.nota is not None:
            raise ErrorNotaYaRegistrada("El comprobante ya tiene una nota registrada.")
        _validar_nota(datos)
        _validar_monto_nota(datos, documentos.vigente)
        emitida = await self._emitir_nota(datos, documentos.vigente)
        ahora = self._reloj.ahora()
        nota = NotaDocumento(
            tipo=datos.tipo,
            serie=emitida.serie,
            numero=emitida.numero.zfill(8),
            monto=datos.monto,
            fecha=emitida.fecha_emision,
            motivo=datos.motivo,
            registrado_en=ahora,
            registrado_por=actor,
        )
        await self._repositorio.guardar_nota(documentos.vigente.documento_id, nota)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="NOTA_DOCUMENTO_REGISTRADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "documento_id": documentos.vigente.documento_id,
                    "tipo": nota.tipo,
                    "numero": nota.serie + nota.numero,
                    "monto": str(nota.monto),
                    "motivo": nota.motivo,
                },
            )
        )
        return nota

    async def _emitir_nota(self, datos: DatosNota, vigente: ComprobanteVigente) -> NotaPse:
        # El PSE recibe el monto de la nota y el comprobante al que ajusta.
        ruc_ipress, codigo_ipress = await self._comprobantes.obtener_ipress_propia()
        referido = ComprobantePse(
            tipo_documento_pago=vigente.tipo_documento_pago,
            serie=vigente.serie,
            numero=vigente.numero,
            fecha_emision=vigente.fecha_emision,
        )
        return await self._emisor.emitir_nota(
            SolicitudNota(ruc_ipress, codigo_ipress, datos.tipo, datos.monto, referido)
        )


class ReemplazarComprobantePago:
    def __init__(
        self,
        repositorio: RepositorioDocumentosPago,
        emision: EmisionPse,
        estado_cuenta: RepositorioEstadoCuenta,
        registro_eventos: RegistroEventos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._comprobantes = emision.comprobantes
        self._emisor = emision.emisor
        self._cotejo = emision.cotejo
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(self, cuenta_medica_id: int, motivo: str, actor: str) -> ComprobanteVigente:
        # Tambien si el validador observo su lote: sin reemplazo no entra al lote nuevo.
        permitidos = await estados_con_reemplazo(
            ESTADOS_CON_REEMPLAZO, self._cotejo, self._estado_cuenta, cuenta_medica_id
        )
        if permitidos is None:
            raise ErrorEstadoNoAdmiteDocumento(REEMPLAZO_INNECESARIO)
        await _estado_exigido(
            self._estado_cuenta,
            cuenta_medica_id,
            permitidos,
            _OPERACION_REEMPLAZO,
            con_correccion=True,
        )
        if not motivo.strip():
            raise ErrorNotaInvalida("El motivo del reemplazo es obligatorio.")
        documentos = await self._repositorio.documentos(cuenta_medica_id)
        if documentos is None:
            raise ErrorSinComprobante("La cuenta no tiene comprobante.")
        if documentos.nota is not None:
            raise ErrorComprobanteConNota(
                "El comprobante tiene una nota registrada: no se reemplaza."
            )
        solicitud = await solicitud_comprobante(self._comprobantes, cuenta_medica_id)
        nuevo = await self._emisor.emitir(solicitud)
        anterior = documentos.vigente
        await self._repositorio.reemplazar(
            cuenta_medica_id,
            ComprobanteEmitido(nuevo, solicitud.montos),
            ComprobanteReemplazado(
                tipo_documento_pago=anterior.tipo_documento_pago,
                serie=anterior.serie,
                numero=anterior.numero,
                fecha_emision=anterior.fecha_emision,
                reemplazado_en=self._reloj.ahora(),
                reemplazado_por=actor,
                motivo=motivo.strip(),
            ),
        )
        await self._registrar_evento(cuenta_medica_id, anterior, nuevo, (motivo.strip(), actor))
        return ComprobanteVigente(
            documento_id=anterior.documento_id,
            tipo_documento_pago=nuevo.tipo_documento_pago,
            serie=nuevo.serie,
            numero=nuevo.numero,
            fecha_emision=nuevo.fecha_emision,
            valor_venta=solicitud.montos.valor_venta,
            igv=solicitud.montos.igv,
            total=solicitud.montos.total,
        )

    async def _registrar_evento(
        self,
        cuenta_medica_id: int,
        anterior: ComprobanteVigente,
        nuevo: ComprobantePse,
        motivo_y_actor: tuple[str, str],
    ) -> None:
        motivo, actor = motivo_y_actor
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="COMPROBANTE_PAGO_REEMPLAZADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "documento_id": anterior.documento_id,
                    "anterior": f"{anterior.serie}-{anterior.numero}",
                    "nuevo": f"{nuevo.serie}-{nuevo.numero}",
                    "motivo": motivo,
                },
            )
        )
