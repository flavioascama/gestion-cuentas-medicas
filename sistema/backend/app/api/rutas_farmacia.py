"""RI-17 y CU-06: productos de farmacia de una cuenta y busqueda en el
catalogo GTIN vigente. Registran y retiran el analista (registra la cuenta,
Tabla 46) y el auditor medico; buscan en el catalogo los roles que trabajan
la cuenta."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import requiere_rol
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.farmacia.dispensacion import (
    BuscarProductoCatalogo,
    DatosProductoDispensado,
    ErrorCuentaInexistenteFarmacia,
    ErrorCuentaNoEditableFarmacia,
    ErrorFarmacia,
    ErrorProductoFueraDeCatalogo,
    ErrorProductoInexistente,
    ErrorProductoInvalido,
    ProductoCatalogo,
    QuitarProductoDispensado,
    RegistrarProductoDispensado,
)
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_dispensacion_sql import (
    RepositorioDispensacionSql,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)

router = APIRouter(tags=["farmacia"])

# 2026-11-19: el auditor medico tambien registra y quita productos.
_REGISTRA_FARMACIA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR)
_CATALOGO = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.ADMINISTRADOR)


class ProductoCatalogoRespuesta(BaseModel):
    codigo: str
    tipo_producto_tedef: str
    nombre: str
    denominacion_comun: str
    concentracion: str | None
    forma_farmaceutica: str | None

    @staticmethod
    def desde_valor(valor: ProductoCatalogo) -> ProductoCatalogoRespuesta:
        return ProductoCatalogoRespuesta(
            codigo=valor.codigo,
            tipo_producto_tedef=valor.tipo_producto_tedef,
            nombre=valor.nombre,
            denominacion_comun=valor.denominacion_comun,
            concentracion=valor.concentracion,
            forma_farmaceutica=valor.forma_farmaceutica,
        )


class SolicitudProductoDispensado(BaseModel):
    codigo_producto: str = Field(min_length=8, max_length=13)
    fecha_dispensacion: date
    cantidad_venta: Decimal = Field(gt=0, max_digits=9, decimal_places=2)
    tipo_unidad_dispensacion: str = Field(min_length=1, max_length=1)
    monto_unitario: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    monto_no_cubierto: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    exento_igv: str = Field(min_length=1, max_length=1)
    guia_farmacia: str | None = Field(default=None, max_length=12)
    diagnostico_asociado_cie10: str | None = Field(default=None, max_length=5)


class ProductoRegistradoRespuesta(BaseModel):
    producto_id: int


def _repositorio(sesion: AsyncSession = Depends(obtener_sesion)) -> RepositorioDispensacionSql:
    return RepositorioDispensacionSql(sesion)


def construir_registrar(
    sesion: AsyncSession = Depends(obtener_sesion),
) -> RegistrarProductoDispensado:
    return RegistrarProductoDispensado(
        RepositorioDispensacionSql(sesion),
        RepositorioEstadoCuentaSql(sesion),
        RegistroEventosSql(sesion),
    )


def construir_quitar(sesion: AsyncSession = Depends(obtener_sesion)) -> QuitarProductoDispensado:
    return QuitarProductoDispensado(
        RepositorioDispensacionSql(sesion),
        RepositorioEstadoCuentaSql(sesion),
        RegistroEventosSql(sesion),
    )


def _error_http(error: ErrorFarmacia) -> ErrorAplicacion:
    if isinstance(error, ErrorCuentaInexistenteFarmacia):
        return ErrorAplicacion("CUENTA_NO_ENCONTRADA", str(error), estado_http=404)
    if isinstance(error, ErrorProductoInexistente):
        return ErrorAplicacion("PRODUCTO_NO_ENCONTRADO", str(error), estado_http=404)
    if isinstance(error, ErrorCuentaNoEditableFarmacia):
        return ErrorAplicacion("CUENTA_NO_EDITABLE", str(error), estado_http=409)
    if isinstance(error, ErrorProductoFueraDeCatalogo):
        return ErrorAplicacion("PRODUCTO_FUERA_DE_CATALOGO", str(error), estado_http=400)
    assert isinstance(error, ErrorProductoInvalido)
    return ErrorAplicacion("PRODUCTO_INVALIDO", str(error), estado_http=400)


@router.get("/catalogo-gtin/productos", response_model=list[ProductoCatalogoRespuesta])
async def buscar_productos_catalogo(
    buscar: str = "",
    repositorio: RepositorioDispensacionSql = Depends(_repositorio),
    _actor: CargaSesion = Depends(_CATALOGO),
) -> list[ProductoCatalogoRespuesta]:
    productos = await BuscarProductoCatalogo(repositorio).ejecutar(buscar)
    return [ProductoCatalogoRespuesta.desde_valor(p) for p in productos]


@router.post(
    "/cuentas/{cuenta_id}/productos",
    response_model=ProductoRegistradoRespuesta,
    status_code=status.HTTP_201_CREATED,
)
async def registrar_producto(
    cuenta_id: int,
    solicitud: SolicitudProductoDispensado,
    caso_uso: RegistrarProductoDispensado = Depends(construir_registrar),
    actor: CargaSesion = Depends(_REGISTRA_FARMACIA),
) -> ProductoRegistradoRespuesta:
    datos = DatosProductoDispensado(**solicitud.model_dump())
    try:
        producto_id = await caso_uso.ejecutar(cuenta_id, datos, actor.nombre_usuario)
    except ErrorFarmacia as error:
        raise _error_http(error) from error
    return ProductoRegistradoRespuesta(producto_id=producto_id)


@router.delete(
    "/cuentas/{cuenta_id}/productos/{producto_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def quitar_producto(
    cuenta_id: int,
    producto_id: int,
    caso_uso: QuitarProductoDispensado = Depends(construir_quitar),
    actor: CargaSesion = Depends(_REGISTRA_FARMACIA),
) -> None:
    try:
        await caso_uso.ejecutar(cuenta_id, producto_id, actor.nombre_usuario)
    except ErrorFarmacia as error:
        raise _error_http(error) from error
