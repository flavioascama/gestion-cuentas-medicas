"""API del simulador PSE: emision sincrona de un comprobante de pago
(adenda de ingesta y completitud) y, desde el 2026-11-18, de su nota de
credito o de debito. A diferencia de ACREDITA SALUD y TEDEF
Web, un PSE real es una integracion API-a-API entre sistemas (SUNAT/el
proveedor de facturacion electronica), no un portal que un humano navega
-- por eso este simulador no tiene sesion asistida ni CAPTCHA, solo una
respuesta HTTP directa."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field, model_validator

from app.almacenamiento import AlmacenamientoPse

# El dia de Lima (UTC-5, sin horario de verano): el contenedor corre en UTC
# y date.today() daria el dia siguiente pasadas las 19:00 de Lima.
_ZONA_PERU = timezone(timedelta(hours=-5))


def hoy_peru() -> date:
    return datetime.now(UTC).astimezone(_ZONA_PERU).date()


# Serie distinta de "F001" (la que usa la carga sintetica,
# herramientas/cargar_cuentas_sinteticas.py): ese generador ya sembro
# numeros "00000001".."0000006X" bajo esa serie para la unica IPRESS del
# sistema, y el contador propio de este simulador (almacenamiento.py)
# tambien arranca en 1 -- una serie propia evita chocar contra la
# restriccion unique (ipress_id, tipo_documento_pago, serie, numero) del
# backend sin tener que coordinar rangos entre los dos generadores.
_SERIE = "E001"
_TIPO_DOCUMENTO_PAGO = "01"  # Factura (mismo valor que la carga sintetica).
# Una serie por tipo de nota (C credito, D debito), con su propio correlativo.
_SERIE_NOTA = {"C": "EC01", "D": "ED01"}


class SolicitudEmision(BaseModel):
    """El cliente y los montos son opcionales (2026-11-18) para no romper
    llamadas antiguas; si llegan montos, deben cuadrar."""

    ruc_ipress: str = Field(min_length=1)
    codigo_ipress: str = Field(min_length=1)
    tipo_comprobante: str | None = Field(default=None, min_length=2, max_length=2)
    codigo_cliente: str | None = None
    razon_social_cliente: str | None = None
    valor_venta: Decimal | None = Field(default=None, ge=0)
    igv: Decimal | None = Field(default=None, ge=0)
    total: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _total_cuadra(self) -> SolicitudEmision:
        valor_venta, igv, total = self.valor_venta, self.igv, self.total
        if valor_venta is None and igv is None and total is None:
            return self
        if valor_venta is None or igv is None or total is None:
            raise ValueError("valor_venta, igv y total van juntos")
        if total != valor_venta + igv:
            raise ValueError("el total debe ser el valor de venta mas el IGV")
        return self


class ComprobanteEmitido(BaseModel):
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date


class ComprobanteReferido(BaseModel):
    tipo_comprobante: str = Field(min_length=2, max_length=2)
    serie: str = Field(min_length=1)
    numero: str = Field(min_length=1)


class SolicitudNota(BaseModel):
    ruc_ipress: str = Field(min_length=1)
    codigo_ipress: str = Field(min_length=1)
    tipo: Literal["C", "D"]
    # Opcionales para no romper llamadas antiguas.
    monto: Decimal | None = Field(default=None, ge=0)
    comprobante_referido: ComprobanteReferido | None = None


class NotaEmitida(BaseModel):
    serie: str
    numero: str
    fecha_emision: date


def construir_app(almacenamiento: AlmacenamientoPse) -> FastAPI:
    app = FastAPI(title="Simulador PSE")

    @app.post("/comprobantes", response_model=ComprobanteEmitido, status_code=201)
    def emitir_comprobante(solicitud: SolicitudEmision) -> ComprobanteEmitido:
        return ComprobanteEmitido(
            tipo_documento_pago=solicitud.tipo_comprobante or _TIPO_DOCUMENTO_PAGO,
            serie=_SERIE,
            numero=almacenamiento.siguiente_numero(),
            fecha_emision=hoy_peru(),
        )

    @app.post("/notas", response_model=NotaEmitida, status_code=201)
    def emitir_nota(solicitud: SolicitudNota) -> NotaEmitida:
        serie = _SERIE_NOTA[solicitud.tipo]
        return NotaEmitida(
            serie=serie,
            numero=almacenamiento.siguiente_numero_nota(serie),
            fecha_emision=hoy_peru(),
        )

    return app
