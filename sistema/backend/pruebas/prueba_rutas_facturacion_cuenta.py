"""Por las rutas HTTP, contra SQLite en memoria (2026-11-19): emitir el
comprobante deja la cuenta FACTURADA a nombre de quien lo emite, y la
consulta de completitud ya no cambia el estado."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencias_cuentas import obtener_emisor_pse
from app.api.main import app
from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    EventoModelo,
)
from pruebas.prueba_casos_uso_pse import EmisorPseFalso
from pruebas.prueba_rutas_atenciones_hospitalarias import (
    Token,
    _acreditar,
    _cabeceras,
    _importar,
    _sembrar,
)


@pytest.fixture
async def base(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar(sesion)


async def _codificar_pendiente(
    cliente: AsyncClient, auditor: dict[str, str], cuenta_id: int
) -> None:
    pendiente = (
        await cliente.get(f"/cuentas/{cuenta_id}/procedimientos-por-codificar", headers=auditor)
    ).json()[0]
    respuesta = await cliente.post(
        f"/cuentas/{cuenta_id}/procedimientos",
        json={
            "descripcion_registrada": "Hemograma completo",
            "codigo_elegido": "85025",
            "cantidad": 1,
            "monto_unitario": "35.00",
            "fecha": str(date(2026, 11, 18)),
            "inicio_sugerencia": datetime.now(UTC).isoformat(),
            "procedimiento_por_codificar_id": pendiente["id"],
        },
        headers=auditor,
    )
    assert respuesta.status_code == 201, respuesta.text


async def _eventos(
    fabrica: async_sessionmaker[AsyncSession], cuenta_id: int
) -> list[tuple[str, str]]:
    async with fabrica() as sesion:
        filas = await sesion.execute(
            sa.select(EventoModelo.tipo_evento, EventoModelo.actor)
            .where(EventoModelo.cuenta_medica_id == cuenta_id)
            .order_by(EventoModelo.version)
        )
        return [(fila[0], fila[1]) for fila in filas.all()]


async def prueba_emitir_el_comprobante_factura_y_la_consulta_solo_lo_lee(
    base: None,
    cliente: AsyncClient,
    token_para_rol: Token,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    app.dependency_overrides[obtener_emisor_pse] = lambda: EmisorPseFalso()
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    auditor = await _cabeceras(token_para_rol, NombreRol.AUDITOR)
    jefe = await _cabeceras(token_para_rol, NombreRol.JEFE)
    cuenta_id = (await _importar(cliente, analista)).json()["cuenta_id"]
    await _acreditar(fabrica_sesiones, cuenta_id)
    await _codificar_pendiente(cliente, auditor, cuenta_id)

    antes = (await cliente.get(f"/cuentas/{cuenta_id}/completitud", headers=jefe)).json()
    emision = await cliente.post(f"/cuentas/{cuenta_id}/comprobante", headers=analista)
    despues = (await cliente.get(f"/cuentas/{cuenta_id}/completitud", headers=jefe)).json()

    assert emision.status_code == 201, emision.text
    assert (antes["estado_cuenta"], antes["completa"]) == ("REGISTRADA", False)
    assert (despues["estado_cuenta"], despues["completa"]) == ("FACTURADA", True)
    eventos = await _eventos(fabrica_sesiones, cuenta_id)
    facturada = [actor for tipo, actor in eventos if tipo == "CUENTA_FACTURADA"]
    emitido = [actor for tipo, actor in eventos if tipo == "COMPROBANTE_PAGO_EMITIDO"]
    assert facturada == emitido
    assert len(facturada) == 1 and facturada[0].startswith("analista.")


async def prueba_consultar_una_cuenta_completa_no_la_factura(
    base: None,
    cliente: AsyncClient,
    token_para_rol: Token,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """Una cuenta que quedo completa y REGISTRADA (antes del cambio) sigue
    asi al consultarla; la regulariza herramientas/facturar_cuentas_completas."""
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    auditor = await _cabeceras(token_para_rol, NombreRol.AUDITOR)
    cuenta_id = (await _importar(cliente, analista)).json()["cuenta_id"]
    await _acreditar(fabrica_sesiones, cuenta_id)
    await _codificar_pendiente(cliente, auditor, cuenta_id)
    async with fabrica_sesiones() as sesion:
        cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None
        sesion.add(
            DocumentoFacturadorModelo(
                cuenta_id=cuenta_id,
                ipress_id=cuenta.ipress_id,
                tipo_documento_pago="01",
                serie="F001",
                numero="00000099",
                fecha_emision=date(2026, 11, 18),
            )
        )
        await sesion.commit()

    completitud = (await cliente.get(f"/cuentas/{cuenta_id}/completitud", headers=analista)).json()

    assert (completitud["estado_cuenta"], completitud["completa"]) == ("REGISTRADA", True)
    detalle = (await cliente.get(f"/cuentas/{cuenta_id}", headers=analista)).json()
    assert detalle["estado"] == "REGISTRADA"
    assert "CUENTA_FACTURADA" not in [
        tipo for tipo, _ in await _eventos(fabrica_sesiones, cuenta_id)
    ]
