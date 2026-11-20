"""Pruebas del registro de productos de farmacia desde la interfaz (RI-17,
CU-06): validaciones del caso de uso con dobles y el adaptador SQL contra
el catalogo GTIN real transcrito."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.farmacia.dispensacion import (
    DatosProductoDispensado,
    ErrorCuentaNoEditableFarmacia,
    ErrorProductoFueraDeCatalogo,
    ErrorProductoInexistente,
    ErrorProductoInvalido,
    ProductoARegistrar,
    ProductoCatalogo,
    QuitarProductoDispensado,
    RegistrarProductoDispensado,
)
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.repositorio_dispensacion_sql import (
    RepositorioDispensacionSql,
)
from herramientas.cargar_catalogo_gtin import _cargar, _leer_productos
from pruebas.prueba_repositorio_plazos import _sembrar_cuenta, _sembrar_iafas

_GODEK = ProductoCatalogo(
    codigo="008400001344",
    tipo_producto_tedef="M",
    nombre="GODEK",
    denominacion_comun="KETOROLACO",
    concentracion="0.5%",
    forma_farmaceutica=None,
    version_id=1,
)
_DATOS = DatosProductoDispensado(
    codigo_producto="008400001344",
    fecha_dispensacion=date(2026, 9, 10),
    cantidad_venta=Decimal("2"),
    tipo_unidad_dispensacion="1",
    monto_unitario=Decimal("12.50"),
    monto_no_cubierto=Decimal("0"),
    exento_igv="A",
)


@dataclass
class _EstadoFijo:
    estado: str | None = "REGISTRADA"
    en_correccion: bool = False

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self.estado

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        raise AssertionError("la farmacia no cambia el estado de la cuenta")

    async def en_correccion_validador(self, cuenta_medica_id: int) -> bool:
        return self.en_correccion


@dataclass
class _RepositorioFalso:
    guardados: list[ProductoARegistrar] = field(default_factory=list)
    quitados: list[int] = field(default_factory=list)

    async def fecha_prestacion(self, cuenta_medica_id: int) -> date | None:
        return date(2026, 9, 10)

    async def producto_vigente(self, codigo: str) -> ProductoCatalogo | None:
        return _GODEK if codigo == _GODEK.codigo else None

    async def buscar_catalogo(self, texto: str, limite: int) -> list[ProductoCatalogo]:
        return [_GODEK]

    async def existe_cie10(self, codigo: str) -> bool:
        return codigo == "A072"

    async def guardar(self, producto: ProductoARegistrar) -> tuple[int, int]:
        self.guardados.append(producto)
        return 40 + len(self.guardados), len(self.guardados)

    async def quitar(self, cuenta_medica_id: int, producto_id: int) -> str | None:
        if producto_id != 41:
            return None
        self.quitados.append(producto_id)
        return _GODEK.codigo


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


async def prueba_registra_el_producto_con_su_tipo_y_monto_presentado() -> None:
    repositorio, registro = _RepositorioFalso(), _RegistroEventosFalso()
    caso_uso = RegistrarProductoDispensado(repositorio, _EstadoFijo(), registro)

    producto_id = await caso_uso.ejecutar(7, _DATOS, actor="ana.analista")

    assert producto_id == 41
    (guardado,) = repositorio.guardados
    assert guardado.catalogo.tipo_producto_tedef == "M"
    assert guardado.monto_presentado == Decimal("25.00")
    (evento,) = registro.eventos
    assert evento.tipo_evento == "PRODUCTO_FARMACIA_REGISTRADO"
    assert evento.datos["codigo_producto"] == "008400001344"
    assert evento.datos["monto_presentado"] == "25.00"


@pytest.mark.parametrize(
    "cambios",
    [
        {"fecha_dispensacion": date(2026, 9, 9)},
        {"cantidad_venta": Decimal("0")},
        {"monto_no_cubierto": Decimal("25.01")},
        {"tipo_unidad_dispensacion": "3"},
        {"exento_igv": "X"},
        {"guia_farmacia": "1234567890123"},
        {"diagnostico_asociado_cie10": "Z999"},
    ],
)
async def prueba_rechaza_datos_fuera_de_la_tabla_4(cambios: dict[str, Any]) -> None:
    caso_uso = RegistrarProductoDispensado(
        _RepositorioFalso(), _EstadoFijo(), _RegistroEventosFalso()
    )
    with pytest.raises(ErrorProductoInvalido):
        await caso_uso.ejecutar(7, replace(_DATOS, **cambios), actor="ana.analista")


async def prueba_rechaza_un_codigo_fuera_del_catalogo_vigente() -> None:
    caso_uso = RegistrarProductoDispensado(
        _RepositorioFalso(), _EstadoFijo(), _RegistroEventosFalso()
    )
    with pytest.raises(ErrorProductoFueraDeCatalogo):
        await caso_uso.ejecutar(
            7, replace(_DATOS, codigo_producto="0000000000000"), actor="ana.analista"
        )


@pytest.mark.parametrize("estado", ["FACTURADA", "ENVIADA", "EN_AUDITORIA", "CERRADA"])
async def prueba_solo_se_edita_la_farmacia_en_estados_editables(estado: str) -> None:
    caso_uso = RegistrarProductoDispensado(
        _RepositorioFalso(), _EstadoFijo(estado), _RegistroEventosFalso()
    )
    with pytest.raises(ErrorCuentaNoEditableFarmacia):
        await caso_uso.ejecutar(7, _DATOS, actor="ana.analista")


async def prueba_quitar_un_producto_deja_su_evento() -> None:
    repositorio, registro = _RepositorioFalso(), _RegistroEventosFalso()
    caso_uso = QuitarProductoDispensado(repositorio, _EstadoFijo("GLOSADA"), registro)

    await caso_uso.ejecutar(7, 41, actor="ana.analista")
    with pytest.raises(ErrorProductoInexistente):
        await caso_uso.ejecutar(7, 99, actor="ana.analista")

    assert repositorio.quitados == [41]
    assert [e.tipo_evento for e in registro.eventos] == ["PRODUCTO_FARMACIA_RETIRADO"]


async def prueba_repositorio_guarda_con_correlativo_y_busca_en_el_catalogo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    await _cargar(_leer_productos(), fabrica_sesiones)
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta_id = await _sembrar_cuenta(sesion, iafas_id, "REGISTRADA")
        repositorio = RepositorioDispensacionSql(sesion)

        encontrados = await repositorio.buscar_catalogo("ketorolaco", 5)
        assert [p.codigo for p in encontrados] == ["008400001344"]
        catalogo = await repositorio.producto_vigente("008400001344")
        assert catalogo is not None and catalogo.tipo_producto_tedef == "M"
        assert await repositorio.fecha_prestacion(cuenta_id) == date(2026, 9, 10)

        primero = await repositorio.guardar(
            ProductoARegistrar(cuenta_id, catalogo, _DATOS, Decimal("25.00"))
        )
        segundo = await repositorio.guardar(
            ProductoARegistrar(cuenta_id, catalogo, _DATOS, Decimal("25.00"))
        )
        assert (primero[1], segundo[1]) == (1, 2)
        assert await repositorio.quitar(cuenta_id, primero[0]) == "008400001344"
        assert await repositorio.quitar(cuenta_id + 1, segundo[0]) is None
