"""Escenario de integracion de /cuentas/{id}/liquidacion,
/cuentas/{id}/pago, /cuentas/{id}/cierre y /anulaciones (CU-12 y CU-13,
Fase 28): dos ciclos completos -- liquidar, conciliar y cerrar una
cuenta; solicitar y aprobar la anulacion de otra -- ejercitados contra
la API HTTP real y el Postgres real del stack.

Requiere el stack arriba (postgres, backend) -- no hacen falta los
simuladores, porque las precondiciones de CU-12/CU-13 se fijan de forma
directa, igual que hace prueba_observaciones_glosas.py (Fase 26) -- y
corre aparte de la suite rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_liquidacion_cierre_anulacion.py -q
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_integracion import CuentaMedicaModelo, IafasModelo
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt
from pruebas_integracion.apoyo_estados import fijar_estado_de_prueba

_CLAVE_PRUEBA = "Clave-Valida-123"


async def _crear_token(sesion: AsyncSession, cliente: AsyncClient, rol: NombreRol) -> str:
    nombre_usuario = f"integracion.{rol.value}.{uuid.uuid4().hex[:12]}"
    registrar = RegistrarUsuario(RepositorioUsuariosSql(sesion), VerificadorClaveBcrypt())
    await registrar.ejecutar(
        nombre_usuario=nombre_usuario,
        clave=_CLAVE_PRUEBA,
        nombres=nombre_usuario,
        roles=frozenset({rol}),
    )
    await sesion.commit()
    respuesta = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": nombre_usuario, "clave": _CLAVE_PRUEBA}
    )
    assert respuesta.status_code == 200, respuesta.text
    return str(respuesta.json()["token"])


async def _crear_cuenta(sesion: AsyncSession, cliente: AsyncClient, token_analista: str) -> int:
    iafas_id = (await sesion.execute(sa.select(IafasModelo.id).limit(1))).scalar_one()
    respuesta = await cliente.post(
        "/cuentas",
        json={
            "tipo_documento_asegurado": "1",
            "numero_documento_asegurado": f"{uuid.uuid4().int % 10**8:08d}",
            "nombres_asegurado": "Paciente",
            "apellidos_asegurado": "De Prueba Fase28",
            "iafas_id": iafas_id,
            "fecha_prestacion": "2026-09-10",
            "hora_prestacion": "09:00:00",
        },
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    return int(respuesta.json()["cuenta_id"])


async def _fijar_estado(sesion: AsyncSession, cuenta_id: int, estado: str) -> None:
    await fijar_estado_de_prueba(sesion, cuenta_id, estado)


async def prueba_ciclo_completo_de_liquidacion_pago_y_cierre_por_la_api_real(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    token_analista = await _crear_token(sesion, cliente, NombreRol.ANALISTA)
    token_tesoreria = await _crear_token(sesion, cliente, NombreRol.TESORERIA)

    cuenta_id = await _crear_cuenta(sesion, cliente, token_analista)
    await _fijar_estado(sesion, cuenta_id, "EN_AUDITORIA")

    respuesta_liquidacion = await cliente.post(
        f"/cuentas/{cuenta_id}/liquidacion",
        json={"monto_liquidado": "1500.00"},
        headers={"Authorization": f"Bearer {token_tesoreria}"},
    )
    assert respuesta_liquidacion.status_code == 201, respuesta_liquidacion.text
    assert respuesta_liquidacion.json()["estado_cuenta"] == "LIQUIDADA"

    respuesta_pago = await cliente.post(
        f"/cuentas/{cuenta_id}/pago",
        json={"monto_pagado": "1500.00"},
        headers={"Authorization": f"Bearer {token_tesoreria}"},
    )
    assert respuesta_pago.status_code == 201, respuesta_pago.text
    assert respuesta_pago.json()["estado_cuenta"] == "PAGADA"
    assert respuesta_pago.json()["diferencia"] == "0.00"

    respuesta_lectura = await cliente.get(
        f"/cuentas/{cuenta_id}/liquidacion", headers={"Authorization": f"Bearer {token_tesoreria}"}
    )
    assert respuesta_lectura.status_code == 200, respuesta_lectura.text
    assert respuesta_lectura.json()["monto_pagado"] == "1500.00"

    respuesta_cierre = await cliente.post(
        f"/cuentas/{cuenta_id}/cierre", headers={"Authorization": f"Bearer {token_analista}"}
    )
    assert respuesta_cierre.status_code == 200, respuesta_cierre.text
    assert respuesta_cierre.json()["estado_cuenta"] == "CERRADA"

    cuenta_final = await sesion.get(CuentaMedicaModelo, cuenta_id)
    assert cuenta_final is not None
    assert cuenta_final.estado == "CERRADA"


async def prueba_ciclo_completo_de_solicitud_y_aprobacion_de_anulacion_por_la_api_real(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    token_analista = await _crear_token(sesion, cliente, NombreRol.ANALISTA)
    token_jefe = await _crear_token(sesion, cliente, NombreRol.JEFE)

    cuenta_id = await _crear_cuenta(sesion, cliente, token_analista)

    respuesta_solicitud = await cliente.post(
        f"/cuentas/{cuenta_id}/anulacion/solicitud",
        json={"motivo": "paciente no se presento a la atencion"},
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta_solicitud.status_code == 201, respuesta_solicitud.text
    solicitud_id = int(respuesta_solicitud.json()["solicitud_id"])

    respuesta_pendientes = await cliente.get(
        "/anulaciones/pendientes", headers={"Authorization": f"Bearer {token_jefe}"}
    )
    assert respuesta_pendientes.status_code == 200, respuesta_pendientes.text
    assert any(s["id"] == solicitud_id for s in respuesta_pendientes.json())

    respuesta_resolucion = await cliente.post(
        f"/anulaciones/{solicitud_id}/resolucion",
        json={"aprobada": True},
        headers={"Authorization": f"Bearer {token_jefe}"},
    )
    assert respuesta_resolucion.status_code == 200, respuesta_resolucion.text
    assert respuesta_resolucion.json()["estado_cuenta"] == "ANULADA"

    cuenta_final = await sesion.get(CuentaMedicaModelo, cuenta_id)
    assert cuenta_final is not None
    assert cuenta_final.estado == "ANULADA"

    respuesta_pendientes_tras_resolver = await cliente.get(
        "/anulaciones/pendientes", headers={"Authorization": f"Bearer {token_jefe}"}
    )
    assert not any(s["id"] == solicitud_id for s in respuesta_pendientes_tras_resolver.json())
