"""Esquemas Pydantic de /atenciones-hospitalarias, /cuentas/importar y
/cuentas/{id}/copago-cobrado y /cuentas/{id}/copago-asegurado (2026-11-19).
La importacion por archivo recibe la atencion con la estructura del sistema
hospitalario (infraestructura/sistema_hospitalario/esquema_atencion.py)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from app.dominio.integracion.atencion_hospitalaria import ResumenAtencionHospitalaria
from app.dominio.integracion.copago_cobrado import CopagoCobrado, DatosCobroCopago


class PacienteAtencionRespuesta(BaseModel):
    tipo_documento: str
    numero_documento: str
    nombres: str
    apellidos: str


class ResumenAtencionRespuesta(BaseModel):
    atencion_id: str
    tipo_atencion: str
    fecha_prestacion: date
    paciente: PacienteAtencionRespuesta
    iafas_codigo: str

    @staticmethod
    def desde_valor(valor: ResumenAtencionHospitalaria) -> ResumenAtencionRespuesta:
        paciente = valor.paciente
        return ResumenAtencionRespuesta(
            atencion_id=valor.atencion_id,
            tipo_atencion=valor.tipo_atencion,
            fecha_prestacion=valor.fecha_prestacion,
            paciente=PacienteAtencionRespuesta(
                tipo_documento=paciente.tipo_documento,
                numero_documento=paciente.numero_documento,
                nombres=paciente.nombres,
                apellidos=paciente.apellidos,
            ),
            iafas_codigo=valor.iafas_codigo,
        )


class CopagoCobradoRespuesta(BaseModel):
    monto: Decimal
    fecha: date
    referencia: str
    origen: str
    registrado_por: str
    registrado_en: datetime | None

    @staticmethod
    def desde_valor(valor: CopagoCobrado) -> CopagoCobradoRespuesta:
        return CopagoCobradoRespuesta(
            monto=valor.monto,
            fecha=valor.fecha,
            referencia=valor.referencia,
            origen=valor.origen,
            registrado_por=valor.registrado_por,
            registrado_en=valor.registrado_en,
        )


class SolicitudCopagoCobrado(BaseModel):
    monto: Decimal
    fecha: date
    referencia: str

    def a_valor(self) -> DatosCobroCopago:
        return DatosCobroCopago(monto=self.monto, fecha=self.fecha, referencia=self.referencia)


class CopagoAseguradoRespuesta(BaseModel):
    """`monto` es null mientras la cuenta no tiene acreditacion."""

    monto: Decimal | None
