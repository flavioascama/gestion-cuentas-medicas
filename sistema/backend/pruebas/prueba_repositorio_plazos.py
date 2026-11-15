"""Pruebas de RepositorioPlazosSql contra SQLite en memoria (Seccion
5.2.4.3, Tabla 61, Fase 27): verifica las cinco consultas en si --
`RevisarVencimientos` ya se prueba aparte con un doble
(pruebas/prueba_casos_uso_plazos.py). Los eventos de este archivo se
insertan directo (no via RegistroEventosSql) porque necesitan un
`ocurrido_en` en el pasado para simular un hito ya vencido, algo que
RegistroEventosSql no permite (siempre sella `datetime.now()`, Seccion
6.2.2) -- la cadena de valores resumen con clave en si ya se prueba en
pruebas/prueba_registro_eventos_sql.py y en pruebas_integracion/."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    EventoModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.modelos_observaciones import (
    CatalogoMotivoObservacionModelo,
    ObservacionModelo,
)
from app.infraestructura.persistencia.repositorio_plazos_sql import RepositorioPlazosSql

_AHORA = datetime(2026, 11, 8, 10, 0, 0)
_DIAS_PLAZO_REENVIO_LOTE_RECHAZADO = 5


async def _sembrar_iafas(sesion: AsyncSession, **plazos: int) -> int:
    iafas = IafasModelo(
        codigo="00099",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
        **plazos,
    )
    sesion.add(iafas)
    await sesion.flush()
    return iafas.id


async def _sembrar_motivo(sesion: AsyncSession) -> str:
    sesion.add(
        CatalogoMotivoObservacionModelo(
            codigo="OBS-01", descripcion="Datos incompletos", naturaleza="ADMINISTRATIVA"
        )
    )
    await sesion.flush()
    return "OBS-01"


async def _sembrar_cuenta(sesion: AsyncSession, iafas_id: int, estado: str) -> int:
    sufijo = uuid.uuid4().hex[:8]
    ipress = IpressModelo(
        ruc=f"201{sufijo[:8]}", codigo_ipress=sufijo, razon_social="Clinica de prueba"
    )
    sesion.add(ipress)
    await sesion.flush()
    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento=sufijo,
        nombres="Ana",
        apellidos="Perez",
        iafas_id=iafas_id,
        ficticio=True,
    )
    sesion.add(asegurado)
    await sesion.flush()
    cuenta = CuentaMedicaModelo(
        identificacion_interna=f"CTA{asegurado.id:07d}",
        asegurado_id=asegurado.id,
        iafas_id=iafas_id,
        ipress_id=ipress.id,
        fecha_prestacion=date(2026, 9, 10),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica="00000001",
        estado=estado,
    )
    sesion.add(cuenta)
    await sesion.flush()
    return cuenta.id


async def _insertar_evento(
    sesion: AsyncSession,
    cuenta_medica_id: int,
    tipo_evento: str,
    estado_nuevo: str | None,
    ocurrido_en: datetime,
) -> None:
    """Insercion directa (ver docstring del modulo): la version solo
    necesita ser unica y creciente por cuenta dentro de esta prueba."""

    version = (
        1
        + (
            await sesion.execute(
                sa.select(sa.func.count())
                .select_from(EventoModelo)
                .where(
                    EventoModelo.tipo_agregado == "CUENTA",
                    EventoModelo.agregado_id == cuenta_medica_id,
                )
            )
        ).scalar_one()
    )
    sesion.add(
        EventoModelo(
            tipo_agregado="CUENTA",
            agregado_id=cuenta_medica_id,
            version=version,
            cuenta_medica_id=cuenta_medica_id,
            tipo_evento=tipo_evento,
            actor="prueba",
            estado_previo=None,
            estado_nuevo=estado_nuevo,
            datos={},
            ocurrido_en=ocurrido_en,
            hash_evento=f"hash-de-prueba-{cuenta_medica_id}-{version}",
        )
    )
    await sesion.flush()


async def prueba_observaciones_abiertas_trae_plazo_de_la_iafas_y_banderas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta_id = await _sembrar_cuenta(sesion, iafas_id, "GLOSADA")
        motivo_codigo = await _sembrar_motivo(sesion)
        sesion.add(
            ObservacionModelo(
                cuenta_medica_id=cuenta_id,
                motivo_codigo=motivo_codigo,
                naturaleza="ADMINISTRATIVA",
                es_parcial=False,
                responsable_rol="analista",
                estado="ABIERTA",
                registrado_en=_AHORA - timedelta(days=2),
            )
        )
        await sesion.flush()
        await sesion.commit()

        repositorio = RepositorioPlazosSql(sesion, _DIAS_PLAZO_REENVIO_LOTE_RECHAZADO)
        hitos = await repositorio.observaciones_abiertas()

        assert len(hitos) == 1
        assert hitos[0].cuenta_medica_id == cuenta_id
        assert hitos[0].plazo_dias == 7
        assert hitos[0].abierta_desde == _AHORA - timedelta(days=2)
        assert hitos[0].ya_avisada is False
        assert hitos[0].ya_escalada is False


async def prueba_observaciones_abiertas_detecta_aviso_ya_registrado(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta_id = await _sembrar_cuenta(sesion, iafas_id, "GLOSADA")
        motivo_codigo = await _sembrar_motivo(sesion)
        abierta_desde = _AHORA - timedelta(days=6)
        sesion.add(
            ObservacionModelo(
                cuenta_medica_id=cuenta_id,
                motivo_codigo=motivo_codigo,
                naturaleza="ADMINISTRATIVA",
                es_parcial=False,
                responsable_rol="analista",
                estado="ABIERTA",
                registrado_en=abierta_desde,
            )
        )
        await sesion.flush()
        await _insertar_evento(
            sesion,
            cuenta_id,
            "OBSERVACION_PLAZO_PROXIMO_A_VENCER",
            None,
            abierta_desde + timedelta(days=1),
        )
        await sesion.commit()

        repositorio = RepositorioPlazosSql(sesion, _DIAS_PLAZO_REENVIO_LOTE_RECHAZADO)
        (hito,) = await repositorio.observaciones_abiertas()

        assert hito.ya_avisada is True
        assert hito.ya_escalada is False


async def prueba_cuentas_rechazadas_usa_el_plazo_del_sistema_no_el_de_la_iafas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta_id = await _sembrar_cuenta(sesion, iafas_id, "RECHAZADA")
        hito_desde = _AHORA - timedelta(days=1)
        await _insertar_evento(sesion, cuenta_id, "RECHAZO_LOTE", "RECHAZADA", hito_desde)
        await sesion.commit()

        repositorio = RepositorioPlazosSql(sesion, _DIAS_PLAZO_REENVIO_LOTE_RECHAZADO)
        (hito,) = await repositorio.cuentas_rechazadas()

        assert hito.cuenta_medica_id == cuenta_id
        assert hito.plazo_dias == _DIAS_PLAZO_REENVIO_LOTE_RECHAZADO
        assert hito.hito_desde == hito_desde
        assert hito.ya_avisada is False
        assert hito.ya_escalada is False


async def prueba_cuentas_en_auditoria_usa_el_plazo_de_comunicacion_de_la_iafas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=21,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta_id = await _sembrar_cuenta(sesion, iafas_id, "EN_AUDITORIA")
        hito_desde = _AHORA - timedelta(days=22)
        await _insertar_evento(sesion, cuenta_id, "INICIO_AUDITORIA", "EN_AUDITORIA", hito_desde)
        await sesion.commit()

        repositorio = RepositorioPlazosSql(sesion, _DIAS_PLAZO_REENVIO_LOTE_RECHAZADO)
        (hito,) = await repositorio.cuentas_en_auditoria()

        assert hito.plazo_dias == 21
        assert hito.hito_desde == hito_desde


async def prueba_cuentas_liquidadas_incluye_total_y_parcial(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=15,
        )
        cuenta_total_id = await _sembrar_cuenta(sesion, iafas_id, "LIQUIDADA")
        cuenta_parcial_id = await _sembrar_cuenta(sesion, iafas_id, "LIQUIDADA_PARCIAL")
        await _insertar_evento(
            sesion, cuenta_total_id, "LIQUIDACION", "LIQUIDADA", _AHORA - timedelta(days=1)
        )
        await _insertar_evento(
            sesion,
            cuenta_parcial_id,
            "LIQUIDACION_PARCIAL",
            "LIQUIDADA_PARCIAL",
            _AHORA - timedelta(days=1),
        )
        await sesion.commit()

        repositorio = RepositorioPlazosSql(sesion, _DIAS_PLAZO_REENVIO_LOTE_RECHAZADO)
        hitos = await repositorio.cuentas_liquidadas()

        assert {h.cuenta_medica_id for h in hitos} == {cuenta_total_id, cuenta_parcial_id}
        assert all(h.plazo_dias == 15 for h in hitos)


async def prueba_cuentas_con_carta_garantia_por_vencer_solo_antes_de_remitir(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta_registrada_id = await _sembrar_cuenta(sesion, iafas_id, "REGISTRADA")
        cuenta_enviada_id = await _sembrar_cuenta(sesion, iafas_id, "ENVIADA")
        for cuenta_id in (cuenta_registrada_id, cuenta_enviada_id):
            sesion.add(
                AcreditacionModelo(
                    cuenta_id=cuenta_id,
                    condicion_cobertura="VIGENTE",
                    codigo_autorizacion="AUT-0001",
                    tipo_documento_autorizacion="01",
                    codigo_asegurado="ASE-0001",
                    tipo_afiliacion="1",
                    vigente_hasta=_AHORA.date() + timedelta(days=3),
                    instante=_AHORA,
                    componente_ejecutor="robot_acreditacion",
                )
            )
        await sesion.commit()

        repositorio = RepositorioPlazosSql(sesion, _DIAS_PLAZO_REENVIO_LOTE_RECHAZADO)
        hitos = await repositorio.cuentas_con_carta_garantia_por_vencer()

        # La cuenta ya ENVIADA no necesita aviso: la facturacion ya se
        # remitio dentro de la vigencia del documento.
        assert [h.cuenta_medica_id for h in hitos] == [cuenta_registrada_id]
        assert hitos[0].ya_avisada is False
