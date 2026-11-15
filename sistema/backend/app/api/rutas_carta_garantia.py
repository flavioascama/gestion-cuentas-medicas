"""RF-13 y CU-06: /cuentas/{id}/carta-garantia. La registra el analista
(registra la cuenta, CU-06); la consultan los roles que consultan cuentas
(Tabla 46)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_reloj, requiere_rol
from app.api.serializacion import campos
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.acreditacion.carta_garantia import (
    CartaGarantia,
    DatosCartaGarantia,
    ErrorCartaGarantiaInvalida,
    ErrorCartaGarantiaYaRegistrada,
    ErrorCuentaInexistenteCarta,
    ErrorCuentaSinRegistroCarta,
    ObtenerCartaGarantia,
    RegistrarCartaGarantia,
)
from app.dominio.puertos_comunes import Reloj
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_carta_garantia_sql import (
    RepositorioCartaGarantiaSql,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)

router = APIRouter(prefix="/cuentas/{cuenta_id}/carta-garantia", tags=["cuentas"])

_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)


class SolicitudCartaGarantia(BaseModel):
    numero: str = Field(min_length=1, max_length=30)
    vigente_desde: date
    vigente_hasta: date
    monto: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class CartaGarantiaRespuesta(BaseModel):
    cuenta_medica_id: int
    numero: str
    vigente_desde: date
    vigente_hasta: date
    monto: Decimal
    registrado_en: datetime
    registrado_por: str

    @staticmethod
    def desde_valor(valor: CartaGarantia) -> CartaGarantiaRespuesta:
        return CartaGarantiaRespuesta(**campos(valor))


def construir_registrar_carta(
    sesion: AsyncSession = Depends(obtener_sesion),
    reloj: Reloj = Depends(obtener_reloj),
) -> RegistrarCartaGarantia:
    return RegistrarCartaGarantia(
        RepositorioCartaGarantiaSql(sesion),
        RepositorioEstadoCuentaSql(sesion),
        RegistroEventosSql(sesion),
        reloj,
    )


def construir_obtener_carta(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> ObtenerCartaGarantia:
    return ObtenerCartaGarantia(RepositorioCartaGarantiaSql(sesion))


@router.get("", response_model=CartaGarantiaRespuesta | None)
async def obtener_carta_garantia(
    cuenta_id: int,
    caso_uso: ObtenerCartaGarantia = Depends(construir_obtener_carta),
    _actor: CargaSesion = Depends(_LECTURA),
) -> CartaGarantiaRespuesta | None:
    carta = await caso_uso.ejecutar(cuenta_id)
    return CartaGarantiaRespuesta.desde_valor(carta) if carta is not None else None


@router.post("", response_model=CartaGarantiaRespuesta, status_code=status.HTTP_201_CREATED)
async def registrar_carta_garantia(
    cuenta_id: int,
    solicitud: SolicitudCartaGarantia,
    caso_uso: RegistrarCartaGarantia = Depends(construir_registrar_carta),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> CartaGarantiaRespuesta:
    datos = DatosCartaGarantia(
        numero=solicitud.numero,
        vigente_desde=solicitud.vigente_desde,
        vigente_hasta=solicitud.vigente_hasta,
        monto=solicitud.monto,
    )
    try:
        carta = await caso_uso.ejecutar(cuenta_id, datos, actor.nombre_usuario)
    except ErrorCuentaInexistenteCarta as error:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorCuentaSinRegistroCarta as error:
        raise ErrorAplicacion(
            "CUENTA_CERRADA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorCartaGarantiaYaRegistrada as error:
        raise ErrorAplicacion(
            "CARTA_GARANTIA_YA_REGISTRADA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorCartaGarantiaInvalida as error:
        raise ErrorAplicacion(
            "CARTA_GARANTIA_INVALIDA", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    return CartaGarantiaRespuesta.desde_valor(carta)
