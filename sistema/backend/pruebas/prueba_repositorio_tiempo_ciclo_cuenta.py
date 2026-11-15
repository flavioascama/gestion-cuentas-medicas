"""Prueba del tiempo de ciclo por cuenta (R3.4, Tabla 5) de
RepositorioTrazabilidadSql.calcular_indicadores: del registro al cierre
para las cuentas cerradas; del registro al instante de la consulta para
las abiertas, con las mas antiguas primero; las anuladas no cuentan.

Los eventos se insertan con instantes fijos (sin pasar por
RegistroEventosSql, que sella la hora actual): lo que se prueba aqui es
la medicion, no la cadena HMAC, que ya tiene sus propias pruebas."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.trazabilidad.valores import FiltroIndicadores
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo, EventoModelo
from app.infraestructura.persistencia.proyeccion_ciclo import reconstruir_proyecciones
from app.infraestructura.persistencia.repositorio_trazabilidad_sql import RepositorioTrazabilidadSql
from pruebas.prueba_repositorio_indicadores_gerenciales import _crear_cuenta, _crear_iafas

_INICIO = datetime(2026, 9, 1, 8, 0, 0, tzinfo=UTC)
_AHORA = datetime(2026, 9, 11, 8, 0, 0, tzinfo=UTC)


async def _historia(
    sesion: AsyncSession, cuenta_id: int, estados: list[tuple[str, timedelta]]
) -> None:
    """Un evento por estado, a `desplazamiento` del inicio comun."""
    for version, (estado, desplazamiento) in enumerate(estados, start=1):
        sesion.add(
            EventoModelo(
                tipo_agregado="CUENTA",
                agregado_id=cuenta_id,
                version=version,
                cuenta_medica_id=cuenta_id,
                tipo_evento=f"PRUEBA_{estado}",
                actor="prueba",
                estado_previo=None,
                estado_nuevo=estado,
                datos={},
                ocurrido_en=_INICIO + desplazamiento,
                hash_evento="0" * 64,
            )
        )
    cuenta = await sesion.get(CuentaMedicaModelo, cuenta_id)
    assert cuenta is not None
    cuenta.estado = estados[-1][0]


async def prueba_tiempo_ciclo_por_cuenta_separa_cerradas_abiertas_y_anuladas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas = await _crear_iafas(sesion, "00001")
        fecha = date(2026, 9, 1)
        cerrada_rapida = await _crear_cuenta(sesion, iafas, fecha)
        cerrada_lenta = await _crear_cuenta(sesion, iafas, fecha)
        abierta_reciente = await _crear_cuenta(sesion, iafas, fecha)
        abierta_antigua = await _crear_cuenta(sesion, iafas, fecha)
        anulada = await _crear_cuenta(sesion, iafas, fecha)

        await _historia(
            sesion,
            cerrada_rapida,
            [("REGISTRADA", timedelta(0)), ("CERRADA", timedelta(hours=24))],
        )
        await _historia(
            sesion,
            cerrada_lenta,
            [
                ("REGISTRADA", timedelta(0)),
                ("FACTURADA", timedelta(hours=10)),
                ("CERRADA", timedelta(hours=72)),
            ],
        )
        await _historia(sesion, abierta_reciente, [("REGISTRADA", timedelta(days=9))])
        await _historia(
            sesion,
            abierta_antigua,
            [("REGISTRADA", timedelta(0)), ("ENVIADA", timedelta(days=2))],
        )
        await _historia(
            sesion, anulada, [("REGISTRADA", timedelta(0)), ("ANULADA", timedelta(hours=1))]
        )
        await sesion.commit()
        await reconstruir_proyecciones(sesion)

        indicadores = await RepositorioTrazabilidadSql(sesion).calcular_indicadores(
            FiltroIndicadores(), _AHORA
        )

    ciclo = indicadores.tiempo_ciclo_cuentas
    assert ciclo.cuentas_cerradas == 2
    assert ciclo.promedio_horas_cerradas == 48.0  # (24 + 72) / 2
    assert ciclo.mediana_horas_cerradas == 48.0
    assert ciclo.cuentas_abiertas == 2
    # Antigua: 10 dias (240 h) desde su registro; reciente: 1 dia (24 h).
    assert ciclo.promedio_horas_abiertas == 132.0
    assert [(c.cuenta_medica_id, c.horas, c.estado) for c in ciclo.mas_antiguas_abiertas] == [
        (abierta_antigua, 240.0, "ENVIADA"),
        (abierta_reciente, 24.0, "REGISTRADA"),
    ]
    assert ciclo.mas_antiguas_abiertas[0].identificacion_interna.startswith("CTA-")


async def prueba_tiempo_ciclo_sin_cuentas_no_tiene_promedios(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        indicadores = await RepositorioTrazabilidadSql(sesion).calcular_indicadores(
            FiltroIndicadores(), _AHORA
        )

    ciclo = indicadores.tiempo_ciclo_cuentas
    assert (ciclo.cuentas_cerradas, ciclo.cuentas_abiertas) == (0, 0)
    assert ciclo.promedio_horas_cerradas is None
    assert ciclo.mediana_horas_cerradas is None
    assert ciclo.promedio_horas_abiertas is None
    assert ciclo.mas_antiguas_abiertas == []


async def prueba_panel_marca_los_registros_en_contingencia_y_su_revision(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """C-18: los registros manuales se ven en el panel, con cuantos
    siguen pendientes de la revision del jefe."""

    async with fabrica_sesiones() as sesion:
        iafas = await _crear_iafas(sesion, "00001")
        cuenta_a = await _crear_cuenta(sesion, iafas, date(2026, 9, 1))
        cuenta_b = await _crear_cuenta(sesion, iafas, date(2026, 9, 1))
        registro_a = EventoModelo(
            tipo_agregado="CUENTA",
            agregado_id=cuenta_a,
            version=1,
            cuenta_medica_id=cuenta_a,
            tipo_evento="CONTINGENCIA_COBERTURA_REGISTRADA",
            actor="ana",
            datos={"sustento": "constancia"},
            ocurrido_en=_INICIO,
            hash_evento="0" * 64,
        )
        sesion.add(registro_a)
        sesion.add(
            EventoModelo(
                tipo_agregado="CUENTA",
                agregado_id=cuenta_b,
                version=1,
                cuenta_medica_id=cuenta_b,
                tipo_evento="CONTINGENCIA_COBERTURA_REGISTRADA",
                actor="ana",
                datos={"sustento": "constancia"},
                ocurrido_en=_INICIO,
                hash_evento="0" * 64,
            )
        )
        await sesion.flush()
        sesion.add(
            EventoModelo(
                tipo_agregado="CUENTA",
                agregado_id=cuenta_a,
                version=2,
                cuenta_medica_id=cuenta_a,
                tipo_evento="CONTINGENCIA_REVISADA",
                actor="jefe",
                datos={"registro_evento_id": str(registro_a.evento_id), "conforme": True},
                ocurrido_en=_INICIO + timedelta(hours=1),
                hash_evento="0" * 64,
            )
        )
        await sesion.commit()

        indicadores = await RepositorioTrazabilidadSql(sesion).calcular_indicadores(
            FiltroIndicadores(), _AHORA
        )

    assert indicadores.registros_contingencia.total == 2
    assert indicadores.registros_contingencia.pendientes_revision == 1
