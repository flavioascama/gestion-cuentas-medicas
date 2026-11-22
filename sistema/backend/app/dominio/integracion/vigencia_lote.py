"""Lote vigente (2026-11-19): un lote solo se carga al validador o se
remite a la IAFAS si sigue diciendo la verdad sobre sus cuentas.

Un lote es vigente cuando todas sus cuentas siguen en FACTURADA y el
comprobante de cada una es el mismo con el que se armo el lote: no se
reemplazo ni se le registro una nota despues de generado el lote, y sus
montos guardados siguen siendo los que hoy factura la cuenta (el lote se
armo con ellos: GenerarLote no admite un comprobante desfasado)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

# Un lote en estos estados todavia no se remitio y sus cuentas siguen
# FACTURADA. El observado por el validador no esta en curso: sus cuentas
# entran en un lote nuevo.
ESTADOS_LOTE_EN_CURSO = ("GENERADO", "CARGADO_VALIDADOR", "VALIDADO")
_ESTADO_CUENTA_EN_LOTE = "FACTURADA"


@dataclass(frozen=True, slots=True)
class DocumentoEnLote:
    """Lo que hoy se sabe del comprobante de una cuenta del lote."""

    cuenta_medica_id: int
    identificacion_interna: str
    estado_cuenta: str
    nota_registrada_en: datetime | None = None
    # Ultimo reemplazo del comprobante (CU-10), si lo hubo.
    reemplazado_en: datetime | None = None
    comprobante_desfasado: bool = False


def _instante(valor: datetime) -> datetime:
    # SQLite devuelve fechas sin zona; se toman como UTC.
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=UTC)


def _posterior(valor: datetime | None, referencia: datetime) -> bool:
    return valor is not None and _instante(valor) > _instante(referencia)


@dataclass(frozen=True, slots=True)
class VigenciaLote:
    lote_id: int
    generado_en: datetime
    documentos: tuple[DocumentoEnLote, ...]
    # Control C-18: la validacion registrada en contingencia fue revisada
    # no conforme por el jefe; el lote deja de estar vigente.
    validacion_no_conforme: bool = False

    def cambio(self, documento: DocumentoEnLote) -> bool:
        return (
            documento.estado_cuenta != _ESTADO_CUENTA_EN_LOTE
            or _posterior(documento.nota_registrada_en, self.generado_en)
            or _posterior(documento.reemplazado_en, self.generado_en)
            or documento.comprobante_desfasado
        )

    @property
    def cuentas_que_cambiaron(self) -> tuple[str, ...]:
        return tuple(d.identificacion_interna for d in self.documentos if self.cambio(d))

    @property
    def vigente(self) -> bool:
        return not self.cuentas_que_cambiaron and not self.validacion_no_conforme


class ErrorLoteDesactualizado(Exception):
    """El lote ya no refleja sus cuentas: no se carga ni se remite."""

    def __init__(self, cuentas: tuple[str, ...], mensaje: str | None = None) -> None:
        super().__init__(
            mensaje
            or f"El lote está desactualizado: cambiaron las cuentas {', '.join(cuentas)}. "
            "Genere un lote nuevo."
        )
        self.cuentas = cuentas


MOTIVO_CUENTAS_CAMBIARON = "Desactualizado: sus cuentas cambiaron después de generarlo."
MOTIVO_VALIDACION_NO_CONFORME = "Desactualizado: la validación en contingencia no fue conforme."

MENSAJE_VALIDACION_NO_CONFORME = (
    "La validación registrada en contingencia no fue conforme. Genere un lote nuevo."
)


def motivo_desactualizado(vigencia: VigenciaLote | None) -> str | None:
    """Lo que ve el usuario (detalle y bandeja); None si sigue vigente."""
    if vigencia is None or vigencia.vigente:
        return None
    if vigencia.validacion_no_conforme:
        return MOTIVO_VALIDACION_NO_CONFORME
    return MOTIVO_CUENTAS_CAMBIARON


def exigir_lote_vigente(vigencia: VigenciaLote | None) -> None:
    """None: el lote no existe; eso lo responde quien llama."""
    if vigencia is None or vigencia.vigente:
        return
    if vigencia.validacion_no_conforme:
        raise ErrorLoteDesactualizado((), MENSAJE_VALIDACION_NO_CONFORME)
    raise ErrorLoteDesactualizado(vigencia.cuentas_que_cambiaron)
