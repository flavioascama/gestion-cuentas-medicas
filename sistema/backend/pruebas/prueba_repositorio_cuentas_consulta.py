"""Pruebas de RepositorioCuentasConsultaSql contra SQLite en memoria
(Fase 18, Seccion 11).

Mismo bug que en `prueba_repositorio_lotes_consulta.py`: `listar()` solo
se habia probado con la base de datos vacia, nunca ejecutaba
`cuenta.iafas.codigo`. Contra Postgres real (Fase 19) fallaba con
`sqlalchemy.exc.MissingGreenlet` por la misma razon (el `.join(IafasModelo)`
no dejaba la relacion cargada). Fijado con `contains_eager`."""

from __future__ import annotations

from datetime import date, time

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.orquestacion.valores import ESTADOS_POR_ETAPA, EtapaCiclo
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.repositorio_cuentas_consulta_sql import (
    RepositorioCuentasConsultaSql,
)


async def _sembrar_cuenta(sesion: AsyncSession) -> int:
    iafas = IafasModelo(
        codigo="19395",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    ipress = IpressModelo(ruc="20123456789", codigo_ipress="12345678", razon_social="Clinica")
    sesion.add_all([iafas, ipress])
    await sesion.flush()

    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento="12345678",
        nombres="Ana",
        apellidos="Perez",
        iafas_id=iafas.id,
        ficticio=True,
    )
    sesion.add(asegurado)
    await sesion.flush()

    cuenta = CuentaMedicaModelo(
        identificacion_interna="CTA0000001",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=date(2026, 9, 10),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica="00000001",
        estado="FACTURADA",
    )
    sesion.add(cuenta)
    await sesion.commit()
    return cuenta.id


async def prueba_listar_incluye_el_codigo_de_la_iafas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_cuenta(sesion)
        repositorio = RepositorioCuentasConsultaSql(sesion)
        cuentas = await repositorio.listar(None)
        assert len(cuentas) == 1
        assert cuentas[0].iafas_codigo == "19395"
        assert cuentas[0].nombres_asegurado == "Ana"


async def prueba_listar_filtra_por_estado(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar_cuenta(sesion)
        repositorio = RepositorioCuentasConsultaSql(sesion)
        assert await repositorio.listar("FACTURADA") != []
        assert await repositorio.listar("REGISTRADA") == []


async def prueba_listar_por_etapa_filtra_los_estados_de_esa_etapa(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """2026-11-12: la bandeja filtra por las cuatro etapas de la tesis; la
    cuenta FACTURADA sembrada pertenece a la etapa de facturacion."""
    async with fabrica_sesiones() as sesion:
        await _sembrar_cuenta(sesion)
        repositorio = RepositorioCuentasConsultaSql(sesion)
        facturacion = ESTADOS_POR_ETAPA[EtapaCiclo.FACTURACION]
        auditoria = ESTADOS_POR_ETAPA[EtapaCiclo.AUDITORIA]
        assert await repositorio.listar(None, estados=facturacion) != []
        assert await repositorio.listar(None, estados=auditoria) == []
