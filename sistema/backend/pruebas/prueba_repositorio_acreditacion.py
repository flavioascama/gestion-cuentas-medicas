"""Pruebas de RepositorioAcreditacionSql contra SQLite en memoria (Seccion
8.1)."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acreditacion.valores import ResultadoAcreditacion
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.repositorio_acreditacion_sql import (
    RepositorioAcreditacionSql,
)

_RESULTADO = ResultadoAcreditacion(
    condicion_cobertura="ACREDITABLE",
    codigo_autorizacion="AUT0000001",
    tipo_documento_autorizacion="03",
    codigo_asegurado="AS81953443",
    tipo_afiliacion="1",
    plan="PLAN DE PRUEBA",
    vigente_desde=date(2026, 1, 1),
    vigente_hasta=date(2027, 1, 1),
    tipo_copago="fijo",
    monto_copago_fijo=Decimal("25.50"),
    porcentaje_coaseguro=None,
    preexistencias=["Diabetes"],
    ruta_evidencia="reportes/evidencia_acreditacion/7/",
)


async def _sembrar_cuenta(sesion: AsyncSession) -> int:
    iafas = IafasModelo(
        codigo="00012",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    ipress = IpressModelo(ruc="20123456789", codigo_ipress="12345678", razon_social="Clinica")
    sesion.add_all([iafas, ipress])
    await sesion.flush()

    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento="81953443",
        nombres="Elvira",
        apellidos="Ochoa",
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
        estado="REGISTRADA",
    )
    sesion.add(cuenta)
    await sesion.commit()
    return cuenta.id


async def prueba_obtener_contexto_cuenta_devuelve_documento_del_asegurado(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioAcreditacionSql(sesion)
        contexto = await repositorio.obtener_contexto_cuenta(cuenta_id)
        assert contexto is not None
        assert contexto.tipo_documento_paciente == "1"
        assert contexto.numero_documento_paciente == "81953443"


async def prueba_obtener_contexto_cuenta_devuelve_none_si_no_existe(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioAcreditacionSql(sesion)
        assert await repositorio.obtener_contexto_cuenta(999) is None


async def prueba_existe_acreditacion_antes_y_despues_de_guardar(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioAcreditacionSql(sesion)
        assert await repositorio.existe_acreditacion(cuenta_id) is False

        await repositorio.guardar_acreditacion(
            cuenta_medica_id=cuenta_id,
            resultado=_RESULTADO,
            instante=datetime(2026, 9, 18, 10, 0, 0),
            duracion_ms=1500,
            componente_ejecutor="robot_acreditacion_playwright",
        )
        assert await repositorio.existe_acreditacion(cuenta_id) is True


async def prueba_guardar_acreditacion_persiste_todos_los_campos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta(sesion)
        repositorio = RepositorioAcreditacionSql(sesion)
        acreditacion_id = await repositorio.guardar_acreditacion(
            cuenta_medica_id=cuenta_id,
            resultado=_RESULTADO,
            instante=datetime(2026, 9, 18, 10, 0, 0),
            duracion_ms=1500,
            componente_ejecutor="robot_acreditacion_playwright",
        )
        assert acreditacion_id > 0

    async with fabrica_sesiones() as sesion:
        registro = await sesion.get(AcreditacionModelo, acreditacion_id)
        assert registro is not None
        assert registro.codigo_autorizacion == "AUT0000001"
        assert registro.monto_copago_fijo == Decimal("25.50")
        assert registro.preexistencias == ["Diabetes"]
        assert registro.duracion_ms == 1500
        assert registro.componente_ejecutor == "robot_acreditacion_playwright"
