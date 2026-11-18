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

Un comprobante con nota no se reemplaza: la nota es de ese comprobante."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.pse.puertos import ComprobantePse, EmisorPse, RepositorioComprobantePago
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

ESTADOS_CON_REEMPLAZO = frozenset({"RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"})
ESTADOS_CON_NOTA = frozenset({"FACTURADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"})
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


class RepositorioDocumentosPago(Protocol):
    async def documentos(self, cuenta_medica_id: int) -> DocumentosPagoCuenta | None:
        """None si la cuenta no tiene comprobante."""
        ...

    async def guardar_nota(self, documento_id: int, nota: NotaDocumento) -> None: ...

    async def reemplazar(
        self, cuenta_medica_id: int, nuevo: ComprobantePse, reemplazo: ComprobanteReemplazado
    ) -> None:
        """Archiva el comprobante vigente con los datos de `reemplazo` y
        deja `nuevo` como vigente en la misma fila."""
        ...


async def _estado_exigido(
    estado_cuenta: RepositorioEstadoCuenta, cuenta_medica_id: int, permitidos: frozenset[str]
) -> str:
    estado = await estado_cuenta.obtener_estado(cuenta_medica_id)
    if estado is None:
        raise ErrorCuentaInexistenteDocumento(f"No existe la cuenta {cuenta_medica_id}.")
    if estado not in permitidos:
        raise ErrorEstadoNoAdmiteDocumento(
            f"La cuenta {cuenta_medica_id} esta en estado {estado!r}."
        )
    return estado


def _validar_nota(datos: DatosNota) -> None:
    errores: list[str] = []
    if datos.tipo not in TIPOS_NOTA:
        errores.append("tipo de nota fuera del dominio (C o D)")
    if datos.motivo not in MOTIVOS_NOTA:
        errores.append("motivo fuera del dominio (R, A o D)")
    if datos.monto <= 0:
        errores.append("el monto debe ser mayor que cero")
    if errores:
        raise ErrorNotaInvalida("; ".join(errores).capitalize() + ".")


class ConsultarDocumentosPago:
    def __init__(self, repositorio: RepositorioDocumentosPago) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, cuenta_medica_id: int) -> DocumentosPagoCuenta | None:
        return await self._repositorio.documentos(cuenta_medica_id)


@dataclass(frozen=True, slots=True)
class EmisionPse:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo que
    hace falta para pedir un comprobante al PSE."""

    comprobantes: RepositorioComprobantePago
    emisor: EmisorPse


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
        await _estado_exigido(self._estado_cuenta, cuenta_medica_id, ESTADOS_CON_NOTA)
        documentos = await self._repositorio.documentos(cuenta_medica_id)
        if documentos is None:
            raise ErrorSinComprobante(f"La cuenta {cuenta_medica_id} no tiene comprobante.")
        if documentos.nota is not None:
            raise ErrorNotaYaRegistrada("El comprobante ya tiene una nota registrada.")
        _validar_nota(datos)
        ruc_ipress, codigo_ipress = await self._comprobantes.obtener_ipress_propia()
        emitida = await self._emisor.emitir_nota(ruc_ipress, codigo_ipress, datos.tipo)
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
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(self, cuenta_medica_id: int, motivo: str, actor: str) -> ComprobanteVigente:
        await _estado_exigido(self._estado_cuenta, cuenta_medica_id, ESTADOS_CON_REEMPLAZO)
        if not motivo.strip():
            raise ErrorNotaInvalida("El motivo del reemplazo es obligatorio.")
        documentos = await self._repositorio.documentos(cuenta_medica_id)
        if documentos is None:
            raise ErrorSinComprobante(f"La cuenta {cuenta_medica_id} no tiene comprobante.")
        if documentos.nota is not None:
            raise ErrorComprobanteConNota(
                "El comprobante tiene una nota registrada: no se reemplaza."
            )
        ruc_ipress, codigo_ipress = await self._comprobantes.obtener_ipress_propia()
        nuevo = await self._emisor.emitir(ruc_ipress, codigo_ipress)
        anterior = documentos.vigente
        await self._repositorio.reemplazar(
            cuenta_medica_id,
            nuevo,
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
                    "motivo": motivo.strip(),
                },
            )
        )
        return ComprobanteVigente(
            documento_id=anterior.documento_id,
            tipo_documento_pago=nuevo.tipo_documento_pago,
            serie=nuevo.serie,
            numero=nuevo.numero,
            fecha_emision=nuevo.fecha_emision,
        )
