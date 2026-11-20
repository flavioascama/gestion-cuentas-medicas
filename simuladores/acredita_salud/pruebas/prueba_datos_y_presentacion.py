"""Pruebas puras (sin HTTP) de RepositorioDatos y de la traduccion de
escenarios sinteticos a lo que las pantallas muestran (Seccion 9.1)."""

from __future__ import annotations

from app.datos import RepositorioDatos
from app.presentacion import (
    campos_estructurados_cobertura,
    condicion_cobertura,
    datos_afiliado,
    datos_copago,
    detalle_cobertura,
)


async def prueba_busca_por_documento(repositorio: RepositorioDatos) -> None:
    asegurado = repositorio.buscar_por_documento("1", "11111111")
    assert asegurado is not None
    assert asegurado.nombre_completo == "Ana Prueba Vigente"


async def prueba_no_encuentra_documento_ajeno(repositorio: RepositorioDatos) -> None:
    assert repositorio.buscar_por_documento("1", "00000000") is None


async def prueba_nombre_iafas_es_deterministico(repositorio: RepositorioDatos) -> None:
    assert repositorio.nombre_iafas("00001") == repositorio.nombre_iafas("00001")
    assert repositorio.nombre_iafas("00001") != repositorio.nombre_iafas("00002")


async def prueba_detalle_cobertura_vigente(repositorio: RepositorioDatos) -> None:
    asegurado = repositorio.buscar_por_documento("1", "11111111")
    assert asegurado is not None
    detalle = dict(detalle_cobertura(asegurado))
    assert detalle["Plan"] == "PLAN DE PRUEBA"


async def prueba_condicion_cobertura_cancelada_no_es_acreditable(
    repositorio: RepositorioDatos,
) -> None:
    asegurado = repositorio.buscar_por_documento("1", "22222222")
    assert asegurado is not None
    assert "NO ACREDITABLE" in condicion_cobertura(asegurado)


async def prueba_datos_copago_fijo(repositorio: RepositorioDatos) -> None:
    asegurado = repositorio.buscar_por_documento("1", "33333333")
    assert asegurado is not None
    copago = datos_copago(asegurado)
    assert copago.tipo == "fijo"
    assert copago.monto_fijo == 25.5
    assert copago.porcentaje_coaseguro is None


async def prueba_datos_copago_ausente(repositorio: RepositorioDatos) -> None:
    asegurado = repositorio.buscar_por_documento("1", "11111111")
    assert asegurado is not None
    copago = datos_copago(asegurado)
    assert copago.tipo is None


async def prueba_campos_estructurados_cobertura_vigente(repositorio: RepositorioDatos) -> None:
    asegurado = repositorio.buscar_por_documento("1", "11111111")
    assert asegurado is not None
    campos = campos_estructurados_cobertura(asegurado)
    assert campos.plan == "PLAN DE PRUEBA"
    assert campos.vigente_hasta == "2027-01-01"
    assert campos.preexistencias is None


async def prueba_campos_estructurados_cobertura_sin_datos_relevantes(
    repositorio: RepositorioDatos,
) -> None:
    asegurado = repositorio.buscar_por_documento("1", "22222222")  # cancelado
    assert asegurado is not None
    campos = campos_estructurados_cobertura(asegurado)
    assert campos.plan is None
    assert campos.vigente_desde is None
    assert campos.preexistencias is None


async def prueba_datos_afiliado_se_derivan_del_padron(repositorio: RepositorioDatos) -> None:
    asegurado = repositorio.buscar_por_documento("1", "11111111")
    assert asegurado is not None
    afiliado = datos_afiliado(asegurado, repositorio.nombre_iafas(asegurado.iafas_codigo))
    assert afiliado.codigo_asegurado == f"{asegurado.iafas_codigo}-11111111"
    assert afiliado.tipo_afiliacion == "1"
    assert afiliado.nombre_tipo_afiliacion == "Regular"
    assert afiliado.codigo_iafas == asegurado.iafas_codigo
    assert afiliado.nombre_iafas == repositorio.nombre_iafas(asegurado.iafas_codigo)
