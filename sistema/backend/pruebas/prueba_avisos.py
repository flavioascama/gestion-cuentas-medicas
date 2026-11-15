"""Pruebas de la bandeja de avisos: el catalogo por rol (cada aviso llega
a quien la tesis dice), el caso de uso, el adaptador SQL sobre eventos
reales y la ruta (cualquier usuario autenticado, filtrado por sus roles)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, time

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.avisos.casos_uso import ListarAvisos, agrupar
from app.dominio.avisos.valores import EventoAviso, tipos_para_roles
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
    LoteFacturacionModelo,
    TrabajoModelo,
)
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_avisos_sql import RepositorioAvisosSql


def prueba_cada_rol_recibe_los_avisos_de_su_etapa() -> None:
    tesoreria = tipos_para_roles(frozenset({NombreRol.TESORERIA}))
    # Tesoreria: el pago y lo que la IAFAS comunico sin poder registrarse.
    assert tesoreria == [
        "COMUNICACION_IAFAS_NO_APLICADA",
        "LIQUIDACION_PAGO_PROXIMO_A_VENCER",
        "LIQUIDACION_PAGO_VENCIDO_ESCALADO",
    ]

    jefe = tipos_para_roles(frozenset({NombreRol.JEFE}))
    # El jefe recibe los escalamientos y la integridad, no los avisos previos.
    assert "OBSERVACION_PLAZO_VENCIDO_ESCALADO" in jefe
    assert "RUPTURA_CADENA_DETECTADA" in jefe
    assert "OBSERVACION_PLAZO_PROXIMO_A_VENCER" not in jefe

    assert tipos_para_roles(frozenset({NombreRol.GERENTE})) == []


class _RepositorioFalso:
    def __init__(self) -> None:
        self.tipos_pedidos: list[str] | None = None

    async def evaluar_atencion(self, avisos: list[EventoAviso]) -> list[EventoAviso]:
        return avisos

    async def listar(self, tipos_evento: list[str], limite: int) -> list[EventoAviso]:
        self.tipos_pedidos = tipos_evento
        return [
            EventoAviso(
                evento_id="e1",
                tipo_evento="AUDITORIA_EXCEDIDA",
                ocurrido_en=datetime(2026, 11, 12, 8, 0, 0),
                datos={"plazo_dias": 30},
                cuenta_medica_id=7,
                identificacion_interna="CTA-000007",
                lote_id=None,
                numero_lote=None,
            )
        ]


async def prueba_listar_avisos_agrega_titulo_y_severidad() -> None:
    repositorio = _RepositorioFalso()
    (aviso,) = await ListarAvisos(repositorio).ejecutar(frozenset({NombreRol.JEFE}), 10)

    assert aviso.titulo == "Resultado de auditoría vencido"
    assert aviso.severidad == "escalamiento"
    assert repositorio.tipos_pedidos == tipos_para_roles(frozenset({NombreRol.JEFE}))


async def prueba_listar_avisos_sin_tipos_no_consulta() -> None:
    repositorio = _RepositorioFalso()
    assert await ListarAvisos(repositorio).ejecutar(frozenset({NombreRol.GERENTE}), 10) == []
    assert repositorio.tipos_pedidos is None


async def _sembrar(sesion: AsyncSession) -> tuple[int, int]:
    iafas = IafasModelo(
        codigo="00012",
        razon_social="IAFAS",
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
        estado="EN_AUDITORIA",
    )
    lote = LoteFacturacionModelo(
        numero="0000009",
        iafas_id=iafas.id,
        periodo="202609",
        generado_en=datetime(2026, 9, 15, 8, 0, 0),
        estado="RECHAZADO",
    )
    sesion.add_all([cuenta, lote])
    await sesion.flush()
    return cuenta.id, lote.id


async def prueba_repositorio_resuelve_la_cuenta_y_el_lote_de_cada_aviso(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id, lote_id = await _sembrar(sesion)
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="AUDITORIA_EXCEDIDA",
                actor="temporizador_sistema",
                estado_previo=None,
                estado_nuevo=None,
                datos={"plazo_dias": 30},
            )
        )
        await registro.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento="LOTE_RECHAZADO",
                actor="trabajador",
                estado_previo="REMITIDO_IAFAS",
                estado_nuevo="RECHAZADO",
                datos={"motivo": "estructura invalida"},
            )
        )
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="HISTORIAL_CONSULTADO",
                actor="jefe",
                estado_previo=None,
                estado_nuevo=None,
            )
        )
        await sesion.commit()

        avisos = await RepositorioAvisosSql(sesion).listar(
            ["AUDITORIA_EXCEDIDA", "LOTE_RECHAZADO"], 10
        )

    por_tipo = {a.tipo_evento: a for a in avisos}
    assert set(por_tipo) == {"AUDITORIA_EXCEDIDA", "LOTE_RECHAZADO"}
    assert por_tipo["AUDITORIA_EXCEDIDA"].identificacion_interna == "CTA0000001"
    assert por_tipo["AUDITORIA_EXCEDIDA"].lote_id is None
    assert (por_tipo["LOTE_RECHAZADO"].lote_id, por_tipo["LOTE_RECHAZADO"].numero_lote) == (
        lote_id,
        "0000009",
    )
    assert por_tipo["LOTE_RECHAZADO"].cuenta_medica_id is None


async def prueba_ruta_de_avisos_exige_sesion(cliente: AsyncClient) -> None:
    assert (await cliente.get("/avisos")).status_code == 401


async def prueba_ruta_de_avisos_responde_a_cualquier_rol(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    for rol in (NombreRol.GERENTE, NombreRol.TESORERIA):
        token = await token_para_rol(rol)
        respuesta = await cliente.get("/avisos", headers={"Authorization": f"Bearer {token}"})
        assert respuesta.status_code == 200
        assert respuesta.json() == []


async def prueba_trabajo_agotado_es_un_aviso_para_analista_jefe_y_administrador(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    """RNF-20: la falla del proceso de automatizacion (un trabajo que agoto
    sus reintentos, RNF-07) llega como aviso, con la cuenta afectada."""

    for rol in (NombreRol.ANALISTA, NombreRol.JEFE, NombreRol.ADMINISTRADOR):
        assert "TRABAJO_AGOTADO" in tipos_para_roles(frozenset({rol}))
    async with fabrica_sesiones() as sesion:
        cuenta_id, _ = await _sembrar(sesion)
        instante = datetime(2026, 11, 12, 9, 0, 0)
        sesion.add(
            TrabajoModelo(
                tipo="CONSULTAR_COBERTURA",
                carga_util={"cuenta_medica_id": cuenta_id, "usuario_origen": "ana"},
                estado="AGOTADO",
                intentos=5,
                proximo_intento=instante,
                error="ACREDITA SALUD no responde",
                creado_en=instante,
                actualizado_en=instante,
            )
        )
        await sesion.commit()
        (aviso,) = await RepositorioAvisosSql(sesion).listar(["TRABAJO_AGOTADO"], 10)

    assert aviso.cuenta_medica_id == cuenta_id
    assert aviso.identificacion_interna == "CTA0000001"
    assert aviso.datos == {
        "tipo_trabajo": "CONSULTAR_COBERTURA",
        "intentos": 5,
        "error": "ACREDITA SALUD no responde",
        "plataforma": None,
    }


def _evento_aviso(
    tipo: str, cuenta: int | None, minuto: int, datos: dict[str, object] | None = None
) -> EventoAviso:
    return EventoAviso(
        evento_id=f"e-{tipo}-{cuenta}-{minuto}",
        tipo_evento=tipo,
        ocurrido_en=datetime(2026, 11, 12, 9, minuto, 0),
        datos=datos or {},
        cuenta_medica_id=cuenta,
        identificacion_interna=None,
        lote_id=None,
        numero_lote=None,
    )


def prueba_agrupar_deja_el_aviso_mas_reciente_de_cada_hito() -> None:
    """El aviso previo y el escalamiento del mismo hito de la misma cuenta
    son una sola fila (la mas reciente), con sus repeticiones."""
    eventos = [
        _evento_aviso("LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO", 7, 30),
        _evento_aviso("LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO", 7, 20),
        _evento_aviso("LOTE_RECHAZADO_PLAZO_PROXIMO_A_VENCER", 7, 10),
        _evento_aviso("LOTE_RECHAZADO_PLAZO_PROXIMO_A_VENCER", 8, 5),
        _evento_aviso("CONTINGENCIA_COBERTURA_REGISTRADA", 7, 4),
        _evento_aviso("CONTINGENCIA_COBERTURA_REGISTRADA", 7, 3),
    ]
    agrupados = agrupar(eventos)
    assert [(e.tipo_evento, e.cuenta_medica_id, n) for e, n in agrupados] == [
        ("LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO", 7, 3),
        ("LOTE_RECHAZADO_PLAZO_PROXIMO_A_VENCER", 8, 1),
        # Cada registro en contingencia se revisa por separado (C-18).
        ("CONTINGENCIA_COBERTURA_REGISTRADA", 7, 1),
        ("CONTINGENCIA_COBERTURA_REGISTRADA", 7, 1),
    ]


def prueba_avisos_de_susalud_se_agrupan_por_periodo() -> None:
    """RI-16: el envio a SUSALUD es por periodo; los lotes del mismo periodo
    son un solo aviso."""
    eventos = [
        _evento_aviso("SUSALUD_ENVIO_VENCIDO_ESCALADO", None, 9, {"periodo": "202609"}),
        _evento_aviso("SUSALUD_ENVIO_VENCIDO_ESCALADO", None, 8, {"periodo": "202609"}),
        _evento_aviso("SUSALUD_ENVIO_PROXIMO_A_VENCER", None, 7, {"periodo": "202609"}),
        _evento_aviso("SUSALUD_ENVIO_PROXIMO_A_VENCER", None, 6, {"periodo": "202610"}),
    ]
    agrupados = agrupar(eventos)
    assert [(e.datos["periodo"], n) for e, n in agrupados] == [("202609", 3), ("202610", 1)]


async def prueba_un_aviso_de_plazo_queda_atendido_si_la_cuenta_cambio_despues(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id, _ = await _sembrar(sesion)
        registro = RegistroEventosSql(sesion)
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="AUDITORIA_EXCEDIDA",
                actor="temporizador_sistema",
                estado_previo=None,
                estado_nuevo=None,
                datos={"plazo_dias": 30},
            )
        )
        repositorio = RepositorioAvisosSql(sesion)
        (antes,) = await repositorio.evaluar_atencion(
            await repositorio.listar(["AUDITORIA_EXCEDIDA"], 10)
        )
        # La IAFAS comunica el resultado: la cuenta pasa a GLOSADA.
        await registro.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="GLOSA",
                actor="ana",
                estado_previo="EN_AUDITORIA",
                estado_nuevo="GLOSADA",
            )
        )
        (despues,) = await repositorio.evaluar_atencion(
            await repositorio.listar(["AUDITORIA_EXCEDIDA"], 10)
        )

    assert antes.atendido is False
    assert despues.atendido is True


def prueba_el_acceso_indebido_es_alerta_para_el_titular_del_banco_de_datos() -> None:
    """C-15: el acceso indebido alerta al jefe y al administrador, no a los
    roles operativos."""
    assert "ACCESO_DENEGADO" in tipos_para_roles(frozenset({NombreRol.ADMINISTRADOR}))
    assert "ACCESO_DENEGADO" in tipos_para_roles(frozenset({NombreRol.JEFE}))
    assert "ACCESO_DENEGADO" not in tipos_para_roles(frozenset({NombreRol.ANALISTA}))
