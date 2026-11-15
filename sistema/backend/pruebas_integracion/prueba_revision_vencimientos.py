"""Escenario de integracion del control de plazos y escalamiento (CU-11,
Seccion 5.2.4.3, Tabla 61, Fase 27): ejercita RepositorioPlazosSql y
RevisarVencimientos contra el Postgres real del stack, con el
encadenamiento de eventos real (RegistroEventosSql, HMAC-SHA256) de por
medio -- las pruebas de pruebas/ usan SQLite y, para los eventos que
necesitan simular un hito ya vencido, los insertan directo sin pasar por
RegistroEventosSql (que siempre sella `datetime.now()`), asi que nunca
ejercitan ese camino real de escritura.

CU-11 no tiene ruta HTTP (su actor es el "temporizador del sistema", no
una persona -- herramientas/revisar_vencimientos.py es su unica forma
de invocacion, igual que verificar_cadena_eventos.py de la Fase 24), por
eso esta prueba construye RevisarVencimientos directamente en vez de
pasar por el cliente HTTP.

Requiere el stack arriba (postgres, backend) -- no hacen falta los
simuladores -- y corre aparte de la suite rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_revision_vencimientos.py -q
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.dominio.plazos.casos_uso import RevisarVencimientos
from app.dominio.puertos_comunes import Evento, Observabilidad
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    EventoModelo,
    IafasModelo,
)
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.registro_mediciones_sql import RegistroMedicionesSql
from app.infraestructura.persistencia.repositorio_plazos_sql import RepositorioPlazosSql
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.reloj import RelojSistema
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt
from pruebas_integracion.apoyo_estados import fijar_estado_de_prueba

_CLAVE_PRUEBA = "Clave-Valida-123"


async def _crear_token_analista(sesion: AsyncSession, cliente: AsyncClient) -> str:
    nombre_usuario = f"integracion.analista.{uuid.uuid4().hex[:12]}"
    registrar = RegistrarUsuario(RepositorioUsuariosSql(sesion), VerificadorClaveBcrypt())
    await registrar.ejecutar(
        nombre_usuario=nombre_usuario,
        clave=_CLAVE_PRUEBA,
        nombres=nombre_usuario,
        roles=frozenset({NombreRol.ANALISTA}),
    )
    await sesion.commit()
    respuesta = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": nombre_usuario, "clave": _CLAVE_PRUEBA}
    )
    assert respuesta.status_code == 200, respuesta.text
    return str(respuesta.json()["token"])


async def _crear_cuenta_rechazada(
    sesion: AsyncSession, cliente: AsyncClient, token_analista: str
) -> int:
    iafas_id = (await sesion.execute(sa.select(IafasModelo.id).limit(1))).scalar_one()
    respuesta = await cliente.post(
        "/cuentas",
        json={
            "tipo_documento_asegurado": "1",
            "numero_documento_asegurado": f"{uuid.uuid4().int % 10**8:08d}",
            "nombres_asegurado": "Paciente",
            "apellidos_asegurado": "De Prueba Fase27",
            "iafas_id": iafas_id,
            "fecha_prestacion": "2026-09-10",
            "hora_prestacion": "09:00:00",
        },
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    cuenta_id = int(respuesta.json()["cuenta_id"])

    await fijar_estado_de_prueba(sesion, cuenta_id, "ENVIADA")
    await sesion.execute(
        sa.update(CuentaMedicaModelo)
        .where(CuentaMedicaModelo.id == cuenta_id)
        .values(estado="RECHAZADA")
    )
    await RegistroEventosSql(sesion).registrar(
        Evento(
            cuenta_medica_id=cuenta_id,
            tipo_evento="RECHAZO_LOTE",
            actor="integracion_prueba",
            estado_previo="ENVIADA",
            estado_nuevo="RECHAZADA",
            datos={"motivo": "prueba de integracion Fase 27"},
        )
    )
    return cuenta_id


def _caso_uso(sesion: AsyncSession) -> RevisarVencimientos:
    return RevisarVencimientos(
        repositorio=RepositorioPlazosSql(sesion, dias_plazo_reenvio_lote_rechazado=0),
        observabilidad=Observabilidad(
            eventos=RegistroEventosSql(sesion), mediciones=RegistroMedicionesSql(sesion)
        ),
        reloj=RelojSistema(),
        dias_aviso_previo_vencimiento=2,
        dias_aviso_vigencia_carta_garantia=5,
    )


async def prueba_lote_rechazado_vencido_se_escala_una_sola_vez(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    token_analista = await _crear_token_analista(sesion, cliente)
    cuenta_id = await _crear_cuenta_rechazada(sesion, cliente, token_analista)

    # Con plazo 0, el hito ya esta vencido en el instante en que se
    # registro el evento RECHAZO_LOTE (el "ahora" de esta linea es
    # siempre >= ese instante).
    primera_corrida = await _caso_uso(sesion).ejecutar()
    assert primera_corrida.lotes_rechazados.escalados >= 1

    eventos_escalado = (
        await sesion.execute(
            sa.select(sa.func.count())
            .select_from(EventoModelo)
            .where(
                EventoModelo.cuenta_medica_id == cuenta_id,
                EventoModelo.tipo_evento == "LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO",
            )
        )
    ).scalar_one()
    assert eventos_escalado == 1

    # Segunda corrida consecutiva, sin limpieza manual: no debe duplicar
    # el escalamiento de esta misma cuenta (ya quedo registrado).
    await _caso_uso(sesion).ejecutar()
    eventos_escalado_tras_segunda_corrida = (
        await sesion.execute(
            sa.select(sa.func.count())
            .select_from(EventoModelo)
            .where(
                EventoModelo.cuenta_medica_id == cuenta_id,
                EventoModelo.tipo_evento == "LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO",
            )
        )
    ).scalar_one()
    assert eventos_escalado_tras_segunda_corrida == 1
