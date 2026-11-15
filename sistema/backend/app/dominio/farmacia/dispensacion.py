"""RI-17 y CU-06: registro de los productos de farmacia dispensados en una
cuenta, desde la interfaz. Hasta el 2026-11-13 solo los cargaba el
generador sintetico.

Cada producto se toma del catalogo GTIN vigente (T4 campo 8 = '1'; el
catalogo UNSPSC y el SISMED no estan disponibles en el entorno de prueba),
que fija el tipo de producto (T4 campo 7). El resto de campos son los de
la Tabla 4 del Anexo 1: fecha de dispensacion (no anterior a la prestacion,
criterio C2 del campo 10), cantidad, tipo de unidad (1 empaque, 2
fraccion), monto unitario sin impuesto, copago, monto no cubierto,
exoneracion de IGV (A o D), guia y diagnostico asociado opcionales. El
monto presentado es cantidad x monto unitario, la misma regla con la que
el constructor del lote arma la T4.

Se registra y se retira en los mismos estados en que se codifica la cuenta
(antes de facturar, al corregir una rechazada y al refacturar una glosa)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Evento, RegistroEventos

ESTADOS_EDITABLES_FARMACIA = frozenset({"REGISTRADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"})
CATALOGO_GTIN = "1"
TIPOS_UNIDAD_DISPENSACION = frozenset({"1", "2"})
INDICADORES_EXONERACION_IGV = frozenset({"A", "D"})
LONGITUD_GUIA = 12
_DOS_DECIMALES = Decimal("0.01")


class ErrorFarmacia(Exception):
    pass


class ErrorCuentaInexistenteFarmacia(ErrorFarmacia):
    pass


class ErrorCuentaNoEditableFarmacia(ErrorFarmacia):
    pass


class ErrorProductoFueraDeCatalogo(ErrorFarmacia):
    pass


class ErrorProductoInvalido(ErrorFarmacia):
    pass


class ErrorProductoInexistente(ErrorFarmacia):
    pass


@dataclass(frozen=True, slots=True)
class ProductoCatalogo:
    codigo: str
    tipo_producto_tedef: str
    nombre: str
    denominacion_comun: str
    concentracion: str | None
    forma_farmaceutica: str | None
    version_id: int


@dataclass(frozen=True, slots=True)
class DatosProductoDispensado:
    codigo_producto: str
    fecha_dispensacion: date
    cantidad_venta: Decimal
    tipo_unidad_dispensacion: str
    monto_unitario: Decimal
    copago: Decimal
    monto_no_cubierto: Decimal
    exento_igv: str
    guia_farmacia: str | None = None
    diagnostico_asociado_cie10: str | None = None


@dataclass(frozen=True, slots=True)
class ProductoARegistrar:
    """Lo que el repositorio guarda: los datos ya validados, el producto
    del catalogo y el monto presentado calculado."""

    cuenta_medica_id: int
    catalogo: ProductoCatalogo
    datos: DatosProductoDispensado
    monto_presentado: Decimal


class RepositorioDispensacion(Protocol):
    async def fecha_prestacion(self, cuenta_medica_id: int) -> date | None: ...

    async def producto_vigente(self, codigo: str) -> ProductoCatalogo | None:
        """El producto en la version mas reciente del catalogo GTIN."""
        ...

    async def buscar_catalogo(self, texto: str, limite: int) -> list[ProductoCatalogo]: ...

    async def existe_cie10(self, codigo: str) -> bool: ...

    async def guardar(self, producto: ProductoARegistrar) -> tuple[int, int]:
        """Devuelve (id, correlativo); el correlativo es el siguiente de
        la cuenta (T4 campo 6)."""
        ...

    async def quitar(self, cuenta_medica_id: int, producto_id: int) -> str | None:
        """Borra el producto de la cuenta; devuelve su codigo o None si no
        existe en esa cuenta."""
        ...


def _validar(datos: DatosProductoDispensado, fecha_prestacion: date) -> None:
    errores: list[str] = []
    if datos.fecha_dispensacion < fecha_prestacion:
        errores.append("la fecha de dispensacion es anterior a la prestacion")
    if datos.cantidad_venta <= 0:
        errores.append("la cantidad debe ser mayor que cero")
    if min(datos.monto_unitario, datos.copago, datos.monto_no_cubierto) < 0:
        errores.append("los montos no pueden ser negativos")
    if datos.tipo_unidad_dispensacion not in TIPOS_UNIDAD_DISPENSACION:
        errores.append("tipo de unidad de dispensacion fuera del dominio (1 o 2)")
    if datos.exento_igv not in INDICADORES_EXONERACION_IGV:
        errores.append("indicador de exoneracion de IGV fuera del dominio (A o D)")
    if datos.guia_farmacia and len(datos.guia_farmacia) > LONGITUD_GUIA:
        errores.append(f"la guia de farmacia tiene mas de {LONGITUD_GUIA} caracteres")
    if errores:
        raise ErrorProductoInvalido("; ".join(errores).capitalize() + ".")


class RegistrarProductoDispensado:
    def __init__(
        self,
        repositorio: RepositorioDispensacion,
        estado_cuenta: RepositorioEstadoCuenta,
        registro_eventos: RegistroEventos,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos

    async def ejecutar(
        self, cuenta_medica_id: int, datos: DatosProductoDispensado, actor: str
    ) -> int:
        await _exigir_cuenta_editable(self._estado_cuenta, cuenta_medica_id)
        fecha_prestacion = await self._repositorio.fecha_prestacion(cuenta_medica_id)
        assert fecha_prestacion is not None, "una cuenta existente tiene fecha de prestacion"
        _validar(datos, fecha_prestacion)
        catalogo = await self._repositorio.producto_vigente(datos.codigo_producto)
        if catalogo is None:
            raise ErrorProductoFueraDeCatalogo(
                f"El codigo {datos.codigo_producto} no esta en el catalogo GTIN vigente."
            )
        diagnostico = datos.diagnostico_asociado_cie10
        if diagnostico and not await self._repositorio.existe_cie10(diagnostico):
            raise ErrorProductoInvalido(f"El diagnostico {diagnostico} no esta en la CIE-10.")
        monto_presentado = (datos.cantidad_venta * datos.monto_unitario).quantize(_DOS_DECIMALES)
        producto_id, correlativo = await self._repositorio.guardar(
            ProductoARegistrar(cuenta_medica_id, catalogo, datos, monto_presentado)
        )
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="PRODUCTO_FARMACIA_REGISTRADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "producto_id": producto_id,
                    "correlativo": correlativo,
                    "codigo_producto": catalogo.codigo,
                    "catalogo_gtin_version_id": catalogo.version_id,
                    "cantidad_venta": str(datos.cantidad_venta),
                    "monto_presentado": str(monto_presentado),
                },
            )
        )
        return producto_id


class QuitarProductoDispensado:
    def __init__(
        self,
        repositorio: RepositorioDispensacion,
        estado_cuenta: RepositorioEstadoCuenta,
        registro_eventos: RegistroEventos,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos

    async def ejecutar(self, cuenta_medica_id: int, producto_id: int, actor: str) -> None:
        await _exigir_cuenta_editable(self._estado_cuenta, cuenta_medica_id)
        codigo = await self._repositorio.quitar(cuenta_medica_id, producto_id)
        if codigo is None:
            raise ErrorProductoInexistente(
                f"La cuenta {cuenta_medica_id} no tiene el producto {producto_id}."
            )
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_medica_id,
                tipo_evento="PRODUCTO_FARMACIA_RETIRADO",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"producto_id": producto_id, "codigo_producto": codigo},
            )
        )


class BuscarProductoCatalogo:
    def __init__(self, repositorio: RepositorioDispensacion) -> None:
        self._repositorio = repositorio

    async def ejecutar(self, texto: str, limite: int = 20) -> list[ProductoCatalogo]:
        return await self._repositorio.buscar_catalogo(texto.strip(), limite)


async def _exigir_cuenta_editable(
    estado_cuenta: RepositorioEstadoCuenta, cuenta_medica_id: int
) -> None:
    estado = await estado_cuenta.obtener_estado(cuenta_medica_id)
    if estado is None:
        raise ErrorCuentaInexistenteFarmacia(f"No existe la cuenta {cuenta_medica_id}.")
    if estado not in ESTADOS_EDITABLES_FARMACIA:
        raise ErrorCuentaNoEditableFarmacia(
            f"La cuenta {cuenta_medica_id} esta en estado {estado!r}: "
            "no admite cambios de farmacia."
        )
