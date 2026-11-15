"""API del simulador PSE: emision sincrona de un comprobante de pago
(adenda de ingesta y completitud). A diferencia de ACREDITA SALUD y TEDEF
Web, un PSE real es una integracion API-a-API entre sistemas (SUNAT/el
proveedor de facturacion electronica), no un portal que un humano navega
-- por eso este simulador no tiene sesion asistida ni CAPTCHA, solo una
respuesta HTTP directa."""

from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.almacenamiento import AlmacenamientoPse

# Serie distinta de "F001" (la que usa la carga sintetica,
# herramientas/cargar_cuentas_sinteticas.py): ese generador ya sembro
# numeros "00000001".."0000006X" bajo esa serie para la unica IPRESS del
# sistema, y el contador propio de este simulador (almacenamiento.py)
# tambien arranca en 1 -- una serie propia evita chocar contra la
# restriccion unique (ipress_id, tipo_documento_pago, serie, numero) del
# backend sin tener que coordinar rangos entre los dos generadores.
_SERIE = "E001"
_TIPO_DOCUMENTO_PAGO = "01"  # Factura (mismo valor que la carga sintetica).


class SolicitudEmision(BaseModel):
    ruc_ipress: str = Field(min_length=1)
    codigo_ipress: str = Field(min_length=1)


class ComprobanteEmitido(BaseModel):
    tipo_documento_pago: str
    serie: str
    numero: str
    fecha_emision: date


def construir_app(almacenamiento: AlmacenamientoPse) -> FastAPI:
    app = FastAPI(title="Simulador PSE")

    @app.post("/comprobantes", response_model=ComprobanteEmitido, status_code=201)
    def emitir_comprobante(solicitud: SolicitudEmision) -> ComprobanteEmitido:
        return ComprobanteEmitido(
            tipo_documento_pago=_TIPO_DOCUMENTO_PAGO,
            serie=_SERIE,
            numero=almacenamiento.siguiente_numero(),
            fecha_emision=date.today(),
        )

    return app
