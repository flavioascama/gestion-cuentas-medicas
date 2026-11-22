"""RI-17 y CU-06: registro de los productos de farmacia dispensados en una
cuenta, desde la interfaz. Hasta el 2026-11-13 solo los cargaba el
generador sintetico.

Cada producto se toma del catalogo GTIN vigente (T4 campo 8 = '1'; el
catalogo UNSPSC y el SISMED no estan disponibles en el entorno de prueba),
que fija el tipo de producto (T4 campo 7). El resto de campos son los de
la Tabla 4 del Anexo 1: fecha de dispensacion (no anterior a la prestacion,
criterio C2 del campo 10), cantidad, tipo de unidad (1 empaque, 2
fraccion), monto unitario sin impuesto, monto no cubierto, exoneracion de
IGV (A o D), guia y diagnostico asociado opcionales. El monto presentado
es cantidad x monto unitario, la misma regla con la que el constructor del
lote arma la T4. El copago no se pide (2026-11-18): sale de la
acreditacion del asegurado al armar el lote y el comprobante.

Se registra y se retira en los mismos estados en que se codifica la cuenta
(antes de facturar, al corregir una rechazada y al refacturar una glosa),
y en una cuenta facturada cuyo lote observo el validador."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Protocol

from app.compartido.fecha_peru import fecha_peru
from app.compartido.nombres_estados import nombre_estado
from app.dominio.orquestacion.correccion_validador import admite_correccion
from app.dominio.orquestacion.puertos import RepositorioEstadoCuenta
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

ESTADOS_EDITABLES_FARMACIA = frozenset({"REGISTRADA", "RECHAZADA", "GLOSADA"})
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


def validar_dispensacion(
    datos: DatosProductoDispensado, fecha_prestacion: date, hoy: date | None = None
) -> Decimal:
    """Valida el producto dispensado y devuelve su monto presentado. La usan
    el registro manual y la importacion de la atencion."""
    errores: list[str] = []
    if datos.fecha_dispensacion < fecha_prestacion:
        errores.append("la fecha de dispensación es anterior a la prestación")
    if hoy is not None and datos.fecha_dispensacion > hoy:
        errores.append("la fecha de dispensación es posterior a hoy")
    if datos.cantidad_venta <= 0:
        errores.append("la cantidad debe ser mayor que cero")
    if min(datos.monto_unitario, datos.monto_no_cubierto) < 0:
        errores.append("los montos no pueden ser negativos")
    if datos.monto_no_cubierto > datos.cantidad_venta * datos.monto_unitario:
        errores.append("el monto no cubierto supera el monto del producto")
    if datos.tipo_unidad_dispensacion not in TIPOS_UNIDAD_DISPENSACION:
        errores.append("el tipo de unidad de dispensación no es válido")
    if datos.exento_igv not in INDICADORES_EXONERACION_IGV:
        errores.append("el indicador de IGV no es válido")
    if datos.guia_farmacia and len(datos.guia_farmacia) > LONGITUD_GUIA:
        errores.append(f"la guía de farmacia tiene más de {LONGITUD_GUIA} caracteres")
    if errores:
        raise ErrorProductoInvalido("; ".join(errores).capitalize() + ".")
    return (datos.cantidad_venta * datos.monto_unitario).quantize(_DOS_DECIMALES)


class RegistrarProductoDispensado:
    def __init__(
        self,
        repositorio: RepositorioDispensacion,
        estado_cuenta: RepositorioEstadoCuenta,
        registro_eventos: RegistroEventos,
        reloj: Reloj | None = None,
    ) -> None:
        self._repositorio = repositorio
        self._estado_cuenta = estado_cuenta
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(
        self, cuenta_medica_id: int, datos: DatosProductoDispensado, actor: str
    ) -> int:
        await _exigir_cuenta_editable(self._estado_cuenta, cuenta_medica_id)
        fecha_prestacion = await self._repositorio.fecha_prestacion(cuenta_medica_id)
        assert fecha_prestacion is not None, "una cuenta existente tiene fecha de prestacion"
        ahora = self._reloj.ahora() if self._reloj is not None else datetime.now(UTC)
        monto_presentado = validar_dispensacion(datos, fecha_prestacion, fecha_peru(ahora))
        catalogo = await self._repositorio.producto_vigente(datos.codigo_producto)
        if catalogo is None:
            raise ErrorProductoFueraDeCatalogo(
                f"El código {datos.codigo_producto} no está en el catálogo GTIN vigente."
            )
        diagnostico = datos.diagnostico_asociado_cie10
        if diagnostico and not await self._repositorio.existe_cie10(diagnostico):
            raise ErrorProductoInvalido(f"El diagnóstico {diagnostico} no está en la CIE-10.")
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
            raise ErrorProductoInexistente("La cuenta no tiene ese producto.")
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
        raise ErrorCuentaInexistenteFarmacia("No existe la cuenta.")
    if not await admite_correccion(
        estado_cuenta, cuenta_medica_id, estado in ESTADOS_EDITABLES_FARMACIA
    ):
        raise ErrorCuentaNoEditableFarmacia(
            f"La cuenta está en estado {nombre_estado(estado)}: no admite cambios de farmacia."
        )
