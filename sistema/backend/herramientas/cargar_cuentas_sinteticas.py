"""Carga en la base de datos real las semillas de la Fase 4
(maestro_iafas.csv, maestro_ipress.csv, asegurados.json,
cuentas_medicas.json), dejando las cuentas en estado FACTURADA. Desde la
Fase 17 tambien carga los `productos` de cada cuenta como filas de
`producto_facturado` (fuente de T4).

Puente deliberado: GenerarLote exige cuentas ya en FACTURADA, pero el
camino real (acreditacion por RPA, Fase 11; codificacion CPMS confirmada
por un auditor, Fase 9) todavia no existe. Este script simula ese
resultado final desde las semillas, para demostrar "un lote conforme
generado desde las semillas" (Seccion 13) sin esperar a esas fases.
`procedimiento_facturado.origen_codigo` queda marcado
'bootstrap_fase7_sin_confirmar_por_auditor', trazable como no confirmado.

Requiere los catalogos CPMS, GTIN y CIE-10 ya cargados (`cargar_cpms.py`,
`cargar_catalogo_gtin.py`, `cargar_cie10.py`) y la migracion aplicada.

Uso (desde sistema/backend/):
    uv run python herramientas/cargar_cuentas_sinteticas.py
"""

from __future__ import annotations

import asyncio
import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.rutas import RAIZ_BACKEND, raiz_simuladores_datos_semilla
from app.infraestructura.persistencia import todos_los_modelos  # noqa: F401
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.modelos_catalogo_gtin import CatalogoGtinVersionModelo
from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo, Cie10VersionModelo
from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    MaestroIafasModelo,
    MaestroIpressModelo,
    ProcedimientoFacturadoModelo,
)

RUTA_MAESTRO_IAFAS = RAIZ_BACKEND / "pruebas" / "fixtures" / "maestro_iafas.csv"
RUTA_MAESTRO_IPRESS = RAIZ_BACKEND / "pruebas" / "fixtures" / "maestro_ipress.csv"
RUTA_ASEGURADOS = raiz_simuladores_datos_semilla() / "asegurados.json"
RUTA_CUENTAS = RAIZ_BACKEND / "pruebas" / "fixtures" / "cuentas_medicas.json"

_ORIGEN_CODIGO_BOOTSTRAP = "bootstrap_fase7_sin_confirmar_por_auditor"
# Buzon desde el que el simulador del receptor de la IAFAS envia sus
# comunicaciones (simuladores/receptor_iafas, CORREO_REMITENTE).
REMITENTE_SIMULADOR_IAFAS = "auditoria@iafas.test"


def _leer_csv_con_cabecera(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8") as archivo:
        lineas = [linea for linea in archivo if not linea.startswith("#")]
    return list(csv.DictReader(lineas))


def _leer_json(ruta: Path) -> dict[str, Any]:
    with ruta.open(encoding="utf-8") as archivo:
        contenido: dict[str, Any] = json.load(archivo)
    return contenido


async def _obtener_codigos_cie10(sesion: AsyncSession) -> list[str]:
    version_id = await _ultima_version_o_falla(
        sesion,
        Cie10VersionModelo.id,
        "No hay ninguna version de catalogo CIE-10 cargada. Ejecute primero "
        "herramientas/cargar_cie10.py (Fase 17).",
    )
    resultado = await sesion.execute(
        sa.select(Cie10CodigoModelo.codigo).where(Cie10CodigoModelo.cie10_version_id == version_id)
    )
    return list(resultado.scalars().all())


async def _cargar_maestros(
    sesion: AsyncSession,
) -> tuple[dict[str, int], list[dict[str, str]]]:
    filas_iafas = _leer_csv_con_cabecera(RUTA_MAESTRO_IAFAS)
    filas_ipress = _leer_csv_con_cabecera(RUTA_MAESTRO_IPRESS)

    codigo_a_iafas_id: dict[str, int] = {}
    for fila in filas_iafas:
        sesion.add(
            MaestroIafasModelo(
                codigo=fila["codigo"], razon_social=fila["razon_social"], ficticio=True
            )
        )
        modelo_iafas = IafasModelo(
            codigo=fila["codigo"],
            razon_social=fila["razon_social"],
            periodicidad_remision_dias=int(fila["periodicidad_remision_dias"]),
            ventana_monitoreo_horas=int(fila["ventana_monitoreo_horas"]),
            # El simulador del receptor de la IAFAS envia desde este buzon.
            correo_remitente=REMITENTE_SIMULADOR_IAFAS,
        )
        sesion.add(modelo_iafas)
        await sesion.flush()
        codigo_a_iafas_id[fila["codigo"]] = modelo_iafas.id

    for indice, fila in enumerate(filas_ipress):
        sesion.add(
            MaestroIpressModelo(
                ruc=fila["ruc"],
                codigo_ipress=fila["codigo_ipress"],
                razon_social=fila["razon_social"],
                ficticio=True,
            )
        )
        if indice == 0:  # la primera fila representa la clinica que opera el sistema
            sesion.add(
                IpressModelo(
                    ruc=fila["ruc"],
                    codigo_ipress=fila["codigo_ipress"],
                    razon_social=fila["razon_social"],
                )
            )
    await sesion.flush()
    return codigo_a_iafas_id, filas_ipress


async def _cargar_asegurados(
    sesion: AsyncSession, codigo_a_iafas_id: dict[str, int]
) -> dict[tuple[str, str], AseguradoModelo]:
    datos = _leer_json(RUTA_ASEGURADOS)
    mapa: dict[tuple[str, str], AseguradoModelo] = {}
    for asegurado in datos["asegurados"]:
        documento = asegurado["documento"]
        modelo = AseguradoModelo(
            tipo_documento=documento["tipo"],
            numero_documento=documento["numero"],
            nombres=asegurado["nombres"],
            apellidos=asegurado["apellidos"],
            iafas_id=codigo_a_iafas_id[asegurado["iafas_codigo"]],
            ficticio=True,
        )
        sesion.add(modelo)
        mapa[(documento["tipo"], documento["numero"])] = modelo
    await sesion.flush()
    return mapa


def _acreditacion_desde_escenario(
    cuenta_medica_id: int, asegurado_datos: dict[str, Any], indice: int
) -> AcreditacionModelo:
    copago = asegurado_datos.get("copago", {})
    tipo_copago = copago.get("tipo") if copago.get("tipo") in ("fijo", "coaseguro") else None
    return AcreditacionModelo(
        cuenta_id=cuenta_medica_id,
        condicion_cobertura=asegurado_datos.get("estado_afiliacion", "ACTIVO"),
        codigo_autorizacion=f"AUT{indice:07d}",
        tipo_documento_autorizacion="03",  # Carta de Garantia (dominio T2 campo 12)
        codigo_asegurado=f"AS{indice:08d}",
        tipo_afiliacion="1",  # Regular (simplificacion documentada en docs/DECISIONES.md)
        plan=asegurado_datos.get("plan"),
        vigente_desde=_fecha_opcional(asegurado_datos, "vigente_desde"),
        vigente_hasta=_fecha_opcional(asegurado_datos, "vigente_hasta"),
        tipo_copago=tipo_copago,
        monto_copago_fijo=Decimal(str(copago["monto"])) if tipo_copago == "fijo" else None,
        porcentaje_coaseguro=copago.get("porcentaje") if tipo_copago == "coaseguro" else None,
        preexistencias=asegurado_datos.get("preexistencias_declaradas", []),
        instante=datetime.now(),
        duracion_ms=0,
        componente_ejecutor=_ORIGEN_CODIGO_BOOTSTRAP,
        ruta_evidencia=None,
    )


def _fecha_opcional(datos: dict[str, Any], clave: str) -> date | None:
    valor = datos.get(clave)
    return date.fromisoformat(valor) if valor else None


@dataclass(frozen=True, slots=True)
class _ContextoCarga:
    """Objeto de parametros (Seccion 2.2): datos que `_crear_cuenta`
    necesita por fila, resueltos una sola vez por `_cargar_cuentas`."""

    codigo_a_iafas_id: dict[str, int]
    ipress_id: int
    asegurados: dict[tuple[str, str], AseguradoModelo]
    asegurados_datos: dict[tuple[str, str], dict[str, Any]]
    codigos_cie10: list[str]
    cpms_version_id: int
    catalogo_gtin_version_id: int


def _agregar_procedimientos(
    sesion: AsyncSession,
    cuenta_medica_id: int,
    procedimientos: list[dict[str, Any]],
    fecha_prestacion: date,
    cpms_version_id: int,
) -> None:
    for procedimiento in procedimientos:
        sesion.add(
            ProcedimientoFacturadoModelo(
                cuenta_id=cuenta_medica_id,
                descripcion_registrada=procedimiento["denominacion"],
                tipo_clasificacion="01",
                codigo_asignado=procedimiento["codigo_cpms"],
                cpms_version_id=cpms_version_id,
                origen_codigo=_ORIGEN_CODIGO_BOOTSTRAP,
                usuario_confirmo_id=None,
                cantidad=procedimiento["cantidad"],
                monto_unitario=Decimal(str(procedimiento["monto_unitario"])),
                fecha=fecha_prestacion,
            )
        )


def _agregar_productos(
    sesion: AsyncSession,
    cuenta_medica_id: int,
    productos: list[dict[str, Any]],
    fecha_prestacion: date,
    catalogo_gtin_version_id: int,
) -> None:
    for correlativo, producto in enumerate(productos, start=1):
        cantidad = Decimal(str(producto["cantidad_venta"]))
        monto_unitario = Decimal(str(producto["monto_unitario"]))
        sesion.add(
            ProductoFacturadoModelo(
                cuenta_medica_id=cuenta_medica_id,
                correlativo=correlativo,
                tipo_producto=producto["tipo_producto"],
                catalogo=producto["catalogo"],
                codigo_producto=producto["codigo_producto"],
                catalogo_gtin_version_id=catalogo_gtin_version_id,
                fecha_dispensacion=fecha_prestacion,
                cantidad_venta=cantidad,
                tipo_unidad_dispensacion=producto["tipo_unidad_dispensacion"],
                monto_unitario_sin_impuesto=monto_unitario,
                monto_presentado=(cantidad * monto_unitario).quantize(Decimal("0.01")),
                monto_no_cubierto=Decimal(str(producto["monto_no_cubierto"])),
            )
        )


async def _crear_cuenta_medica(
    sesion: AsyncSession, cuenta: dict[str, Any], indice: int, contexto: _ContextoCarga
) -> tuple[CuentaMedicaModelo, date]:
    doc_asegurado = cuenta["asegurado_documento"]
    asegurado = contexto.asegurados[(doc_asegurado["tipo"], doc_asegurado["numero"])]
    fecha_prestacion = datetime.strptime(cuenta["fecha_prestacion"], "%Y%m%d").date()

    cuenta_medica = CuentaMedicaModelo(
        identificacion_interna=cuenta["id_interno"],
        asegurado_id=asegurado.id,
        iafas_id=contexto.codigo_a_iafas_id[cuenta["iafas_codigo"]],
        ipress_id=contexto.ipress_id,
        fecha_prestacion=fecha_prestacion,
        hora_prestacion=time(8, 0, 0),
        numero_historia_clinica=f"{indice:08d}",
        # Catalogo oficial CIE-10 del MINSA (Fase 17): ver cargar_cie10.py.
        diagnostico_principal_cie10=contexto.codigos_cie10[indice % len(contexto.codigos_cie10)],
        estado="FACTURADA",
    )
    sesion.add(cuenta_medica)
    await sesion.flush()

    sesion.add(
        DocumentoFacturadorModelo(
            cuenta_id=cuenta_medica.id,
            ipress_id=contexto.ipress_id,
            tipo_documento_pago="01",  # Factura
            serie="F001",
            numero=f"{indice:08d}",
            fecha_emision=fecha_prestacion,
            fecha_primer_envio=None,
        )
    )
    return cuenta_medica, fecha_prestacion


async def _crear_cuenta(
    sesion: AsyncSession, cuenta: dict[str, Any], indice: int, contexto: _ContextoCarga
) -> None:
    doc_asegurado = cuenta["asegurado_documento"]
    clave_asegurado = (doc_asegurado["tipo"], doc_asegurado["numero"])
    cuenta_medica, fecha_prestacion = await _crear_cuenta_medica(sesion, cuenta, indice, contexto)

    acreditacion = _acreditacion_desde_escenario(
        cuenta_medica.id, contexto.asegurados_datos[clave_asegurado], indice
    )
    sesion.add(acreditacion)
    _agregar_procedimientos(
        sesion,
        cuenta_medica.id,
        cuenta["procedimientos"],
        fecha_prestacion,
        contexto.cpms_version_id,
    )
    if cuenta.get("productos"):
        _agregar_productos(
            sesion,
            cuenta_medica.id,
            cuenta["productos"],
            fecha_prestacion,
            contexto.catalogo_gtin_version_id,
        )


@dataclass(frozen=True, slots=True)
class _VersionesCatalogo:
    """Agrupa CPMS y GTIN en un parametro, limite de 5 por funcion (Seccion 3)."""

    cpms_version_id: int
    catalogo_gtin_version_id: int


async def _cargar_cuentas(
    sesion: AsyncSession,
    codigo_a_iafas_id: dict[str, int],
    ipress_id: int,
    asegurados: dict[tuple[str, str], AseguradoModelo],
    versiones: _VersionesCatalogo,
) -> int:
    datos = _leer_json(RUTA_CUENTAS)
    todas_las_cuentas = [c for lote in datos["lotes"].values() for c in lote]
    asegurados_datos = {
        (a["documento"]["tipo"], a["documento"]["numero"]): a
        for a in _leer_json(RUTA_ASEGURADOS)["asegurados"]
    }
    contexto = _ContextoCarga(
        codigo_a_iafas_id=codigo_a_iafas_id,
        ipress_id=ipress_id,
        asegurados=asegurados,
        asegurados_datos=asegurados_datos,
        codigos_cie10=await _obtener_codigos_cie10(sesion),
        cpms_version_id=versiones.cpms_version_id,
        catalogo_gtin_version_id=versiones.catalogo_gtin_version_id,
    )

    for indice, cuenta in enumerate(todas_las_cuentas, start=1):
        await _crear_cuenta(sesion, cuenta, indice, contexto)

    await sesion.commit()
    return len(todas_las_cuentas)


async def _ultima_version_o_falla(
    sesion: AsyncSession, columna_id: sa.ColumnElement[int], mensaje_si_falta: str
) -> int:
    version_id = (
        await sesion.execute(sa.select(columna_id).order_by(columna_id.desc()).limit(1))
    ).scalar_one_or_none()
    if version_id is None:
        raise SystemExit(mensaje_si_falta)
    return version_id


async def main() -> None:
    async with FabricaSesiones() as sesion:
        version_cpms = await _ultima_version_o_falla(
            sesion,
            CpmsVersionModelo.id,
            "No hay ninguna version de CPMS cargada. Ejecute primero "
            "herramientas/cargar_cpms.py (Fase 4).",
        )
        version_gtin = await _ultima_version_o_falla(
            sesion,
            CatalogoGtinVersionModelo.id,
            "No hay ninguna version de catalogo GTIN cargada. Ejecute primero "
            "herramientas/cargar_catalogo_gtin.py (Fase 17).",
        )

        codigo_a_iafas_id, filas_ipress = await _cargar_maestros(sesion)
        if not filas_ipress:
            raise SystemExit(f"{RUTA_MAESTRO_IPRESS} no tiene filas.")
        asegurados = await _cargar_asegurados(sesion, codigo_a_iafas_id)

        ipress_id = (await sesion.execute(sa.select(IpressModelo.id).limit(1))).scalar_one()
        creadas = await _cargar_cuentas(
            sesion,
            codigo_a_iafas_id,
            ipress_id,
            asegurados,
            _VersionesCatalogo(version_cpms, version_gtin),
        )

    print(
        f"Cargadas {len(codigo_a_iafas_id)} IAFAS, {len(filas_ipress)} IPRESS "
        f"(maestro) + 1 propia, {len(asegurados)} asegurados y {creadas} cuentas "
        "medicas en estado FACTURADA."
    )


if __name__ == "__main__":
    asyncio.run(main())
