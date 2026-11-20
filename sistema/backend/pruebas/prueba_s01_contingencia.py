"""El `.S01` adjuntado en contingencia debe ser del lote: no vacio y con
el nombre del Anexo 3 (RUC, IPRESS, IAFAS, numero de lote y periodo)."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.contingencia.errores import ErrorArchivoS01Invalido
from app.dominio.contingencia.valores import IdentidadLoteS01, ResultadoValidacionManual
from app.dominio.integracion.puertos_validacion import ArchivoLote
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo
from app.infraestructura.persistencia.repositorio_contingencia_sql import (
    RepositorioContingenciaSql,
)
from app.infraestructura.tedef.registrar_validacion_contingencia import (
    s01_corresponde_al_lote,
)
from pruebas.prueba_casos_uso_contingencia import (
    S01_DEL_LOTE,
    _Contingencia,
    _Eventos,
    _Validacion,
    _validacion,
)
from pruebas.prueba_lotes_sugeridos import _crear_cuenta
from pruebas.prueba_vigencia_lote_sql import _base, _lote

_IDENTIDAD = IdentidadLoteS01("20690951848", "15995250", "96969", "0000007", "202611")
_SUSTENTO = "Constancia del validador entregada por correo"


@pytest.mark.parametrize(
    "nombre,corresponde",
    [
        (S01_DEL_LOTE, True),
        ("937_20690951848_15995250_96969_0000008_202611_20261112.S01", False),
        ("937_20690951848_15995250_96969_0000007_202610_20261112.S01", False),
        ("937_20111111111_15995250_96969_0000007_202611_20261112.S01", False),
        ("937_20690951848_15995250_19395_0000007_202611_20261112.S01", False),
        ("937_LOTE_0000007.S01", False),
    ],
)
def prueba_el_nombre_debe_ser_el_del_lote(nombre: str, corresponde: bool) -> None:
    assert s01_corresponde_al_lote(nombre, _IDENTIDAD) is corresponde


def prueba_sin_identidad_del_lote_no_corresponde() -> None:
    assert not s01_corresponde_al_lote(S01_DEL_LOTE, None)


@pytest.mark.parametrize(
    "archivo,mensaje",
    [
        (ArchivoLote(nombre=S01_DEL_LOTE, contenido=b""), "vacío"),
        (
            ArchivoLote(
                nombre="937_20690951848_15995250_96969_0000008_202611_20261112.S01",
                contenido=b"x",
            ),
            "no corresponde a este lote",
        ),
    ],
)
async def prueba_un_s01_vacio_o_de_otro_lote_es_rechazado(
    tmp_path: Path, archivo: ArchivoLote, mensaje: str
) -> None:
    validacion, eventos = _Validacion(), _Eventos()
    caso_uso = _validacion(_Contingencia(), validacion, eventos, tmp_path)
    with pytest.raises(ErrorArchivoS01Invalido, match=mensaje):
        await caso_uso.ejecutar(7, ResultadoValidacionManual.VALIDADO, _SUSTENTO, archivo, "ana")
    assert validacion.archivos == [] and eventos.eventos == []
    assert list(tmp_path.iterdir()) == []


async def _lote_agotado(sesion: AsyncSession) -> tuple[int, str]:
    ipress, iafas = await _base(sesion)
    documento = await _crear_cuenta(sesion, ipress, iafas, "1", "FACTURADA")
    lote_id = await _lote(sesion, iafas, [documento], estado="CARGADO_VALIDADOR")
    instante = datetime(2026, 11, 19, 9, 0, 0, tzinfo=UTC)
    sesion.add(
        TrabajoModelo(
            tipo="CARGAR_LOTE_VALIDADOR",
            carga_util={"lote_id": lote_id},
            estado="AGOTADO",
            intentos=5,
            proximo_intento=instante,
            creado_en=instante,
            actualizado_en=instante,
        )
    )
    await sesion.flush()
    return lote_id, f"00000{documento.id:02d}"


async def prueba_la_identidad_del_lote_sale_de_la_base(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, numero = await _lote_agotado(sesion)
        repositorio = RepositorioContingenciaSql(sesion)
        assert await repositorio.identidad_lote_s01(lote_id) == IdentidadLoteS01(
            "20690951848", "15995250", "19395", numero, "202611"
        )
        assert await repositorio.identidad_lote_s01(999) is None


async def prueba_la_ruta_responde_422_con_un_s01_de_otro_lote(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, _numero = await _lote_agotado(sesion)
        await sesion.commit()
    token = await token_para_rol(NombreRol.ANALISTA)
    respuesta = await cliente.post(
        f"/lotes/{lote_id}/validacion/contingencia",
        json={
            "resultado": "VALIDADO",
            "sustento": _SUSTENTO,
            "nombre_s01": "937_20690951848_15995250_19395_0000099_202611_20261112.S01",
            "contenido_s01_base64": base64.b64encode(b"contenido").decode(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 422
    assert "no corresponde a este lote" in respuesta.text
