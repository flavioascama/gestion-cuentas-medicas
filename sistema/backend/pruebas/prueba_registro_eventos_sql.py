"""Pruebas de RegistroEventosSql contra SQLite en memoria (Fase 24, Seccion
6.2.2): numero de orden (`version`) por agregado y encadenamiento con valor
resumen con clave (`hash_evento`, RNF-18)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.compartido.configuracion import obtener_configuracion
from app.dominio.orquestacion.errores import ErrorContinuidadEstados, ErrorTransicionNoDefinida
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.cadena_eventos import GENESIS, calcular_hash_evento_de_fila
from app.infraestructura.persistencia.modelos_integracion import EventoModelo
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql


async def _eventos_del_agregado(
    sesion: AsyncSession, tipo_agregado: str, agregado_id: int
) -> list[EventoModelo]:
    filas = await sesion.execute(
        select(EventoModelo)
        .where(EventoModelo.tipo_agregado == tipo_agregado, EventoModelo.agregado_id == agregado_id)
        .order_by(EventoModelo.version)
    )
    return list(filas.scalars().all())


async def prueba_primer_evento_de_un_agregado_tiene_version_1_y_encadena_con_genesis(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=5,
                tipo_evento="CUENTA_REGISTRADA",
                actor="analista.prueba",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        eventos = await _eventos_del_agregado(sesion, "CUENTA", 5)
        assert len(eventos) == 1
        assert eventos[0].version == 1

        clave = obtener_configuracion().clave_hmac_eventos.encode("utf-8")
        esperado = calcular_hash_evento_de_fila(
            clave,
            GENESIS,
            {
                "tipo_agregado": eventos[0].tipo_agregado,
                "agregado_id": eventos[0].agregado_id,
                "version": eventos[0].version,
                "tipo_evento": eventos[0].tipo_evento,
                "actor": eventos[0].actor,
                "estado_previo": eventos[0].estado_previo,
                "estado_nuevo": eventos[0].estado_nuevo,
                "ocurrido_en": eventos[0].ocurrido_en,
            },
        )
        assert eventos[0].hash_evento == esperado


async def prueba_segundo_evento_del_mismo_agregado_encadena_con_el_hash_anterior(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=5,
                tipo_evento="CUENTA_REGISTRADA",
                actor="analista.prueba",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        await registro.registrar(
            Evento(
                cuenta_medica_id=5,
                tipo_evento="CUENTA_FACTURADA",
                actor="sistema",
                estado_previo="REGISTRADA",
                estado_nuevo="FACTURADA",
            )
        )
        eventos = await _eventos_del_agregado(sesion, "CUENTA", 5)
        assert [e.version for e in eventos] == [1, 2]
        assert eventos[1].hash_evento != eventos[0].hash_evento

        clave = obtener_configuracion().clave_hmac_eventos.encode("utf-8")
        esperado = calcular_hash_evento_de_fila(
            clave,
            eventos[0].hash_evento,
            {
                "tipo_agregado": eventos[1].tipo_agregado,
                "agregado_id": eventos[1].agregado_id,
                "version": eventos[1].version,
                "tipo_evento": eventos[1].tipo_evento,
                "actor": eventos[1].actor,
                "estado_previo": eventos[1].estado_previo,
                "estado_nuevo": eventos[1].estado_nuevo,
                "ocurrido_en": eventos[1].ocurrido_en,
            },
        )
        assert eventos[1].hash_evento == esperado


async def prueba_agregados_distintos_llevan_secuencias_de_version_independientes(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=1,
                tipo_evento="CUENTA_REGISTRADA",
                actor="analista.prueba",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        await registro.registrar(
            Evento(
                cuenta_medica_id=2,
                tipo_evento="CUENTA_REGISTRADA",
                actor="analista.prueba",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        eventos_1 = await _eventos_del_agregado(sesion, "CUENTA", 1)
        eventos_2 = await _eventos_del_agregado(sesion, "CUENTA", 2)
        assert [e.version for e in eventos_1] == [1]
        assert [e.version for e in eventos_2] == [1]
        assert eventos_1[0].hash_evento != eventos_2[0].hash_evento


async def prueba_continuidad_rechaza_un_estado_previo_que_no_es_el_ultimo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """Tabla 69 ("continuidad"): el estado previo de una transicion es el
    ultimo estado registrado del agregado; un evento sin estado (bitacora,
    aviso) no interrumpe la secuencia."""
    async with fabrica_sesiones() as sesion:
        registro = RegistroEventosSql(sesion)
        for tipo, previo, nuevo in (
            ("CUENTA_REGISTRADA", None, "REGISTRADA"),
            ("HISTORIAL_CONSULTADO", None, None),
            ("CUENTA_FACTURADA", "REGISTRADA", "FACTURADA"),
        ):
            await registro.registrar(
                Evento(
                    cuenta_medica_id=77,
                    tipo_evento=tipo,
                    actor="prueba",
                    estado_previo=previo,
                    estado_nuevo=nuevo,
                )
            )
        with pytest.raises(ErrorContinuidadEstados):
            await registro.registrar(
                Evento(
                    cuenta_medica_id=77,
                    tipo_evento="INICIO_AUDITORIA",
                    actor="prueba",
                    estado_previo="ENVIADA",
                    estado_nuevo="EN_AUDITORIA",
                )
            )
        await sesion.rollback()
        eventos = await _eventos_del_agregado(sesion, "CUENTA", 77)
        assert [e.tipo_evento for e in eventos][-1] == "CUENTA_FACTURADA"


@pytest.mark.parametrize(
    "previo,nuevo",
    [
        ("REGISTRADA", "PAGADA"),  # omite etapas: no es una transicion de la Tabla 58
        ("CERRADA", "REGISTRADA"),  # sale de un estado terminal
        ("REGISTRADA", "EN_REVISION"),  # estado fuera del conjunto definido
    ],
)
async def prueba_registro_rechaza_un_paso_de_cuenta_fuera_de_la_maquina_de_estados(
    fabrica_sesiones: async_sessionmaker[AsyncSession], previo: str, nuevo: str
) -> None:
    """Tabla 69 (consistencia de estados y secuencia de flujo): el almacen solo
    admite estados del conjunto definido y pasos de la Tabla 58, y nada sale
    de CERRADA o ANULADA."""
    async with fabrica_sesiones() as sesion:
        registro = RegistroEventosSql(sesion)
        with pytest.raises(ErrorTransicionNoDefinida):
            await registro.registrar(
                Evento(
                    cuenta_medica_id=78,
                    tipo_evento="PASO_NO_DEFINIDO",
                    actor="prueba",
                    estado_previo=previo,
                    estado_nuevo=nuevo,
                )
            )
        await sesion.rollback()
        assert await _eventos_del_agregado(sesion, "CUENTA", 78) == []


async def prueba_registro_asigna_la_marca_temporal_al_insertar_y_no_es_futura(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """Tabla 69 (integridad de datos): la marca temporal la asigna el registro
    al insertar y no es posterior al instante de insercion."""
    antes = datetime.now(UTC)
    async with fabrica_sesiones() as sesion:
        await RegistroEventosSql(sesion).registrar(
            Evento(
                cuenta_medica_id=79,
                tipo_evento="CUENTA_REGISTRADA",
                actor="prueba",
                estado_previo=None,
                estado_nuevo="REGISTRADA",
            )
        )
        await sesion.commit()
        (evento,) = await _eventos_del_agregado(sesion, "CUENTA", 79)
    despues = datetime.now(UTC)
    ocurrido = evento.ocurrido_en
    if ocurrido.tzinfo is None:
        ocurrido = ocurrido.replace(tzinfo=UTC)
    assert antes <= ocurrido <= despues
