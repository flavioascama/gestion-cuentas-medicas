"""Escenario de integracion del ciclo completo de una glosa parcial
(Fase 32, R2.6 "todos los flujos"): observacion parcial (CU-08) ->
liquidacion parcial (T-10) -> conciliacion con diferencia (T-11) ->
intento de cierre bloqueado por la diferencia pendiente (CU-13, Tabla
52: "el sistema verifica que el monto conciliado corresponda al
liquidado"). Las Fases 26 y 28 ya prueban cada paso por separado, con
dobles de prueba o aislado por fase; este escenario es el primero que
encadena los dos modulos de punta a punta por la API HTTP real,
exactamente la via GLOSADA_PARCIAL que `prueba_liquidacion_cierre_
anulacion.py` (Fase 28) no ejercita -- ese usa la via total.

Requiere el stack arriba (postgres, backend) -- no hacen falta los
simuladores -- y corre aparte de la suite rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_ciclo_glosa_parcial.py -q
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


async def _crear_cuenta_en_auditoria(
    sesion: AsyncSession, cliente: AsyncClient, token_analista: str
) -> int:
    iafas_id = (await sesion.execute(sa.select(IafasModelo.id).limit(1))).scalar_one()
    respuesta = await cliente.post(
        "/cuentas",
        json={
            "tipo_documento_asegurado": "1",
            "numero_documento_asegurado": f"{uuid.uuid4().int % 10**8:08d}",
            "nombres_asegurado": "Paciente",
            "apellidos_asegurado": "De Prueba Fase32",
            "iafas_id": iafas_id,
            "fecha_prestacion": "2026-09-10",
            "hora_prestacion": "09:00:00",
        },
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    cuenta_id = int(respuesta.json()["cuenta_id"])
    await fijar_estado_de_prueba(sesion, cuenta_id, "EN_AUDITORIA")
    return cuenta_id


async def prueba_glosa_parcial_liquidada_pagada_con_diferencia_no_se_puede_cerrar(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    token_analista = await _crear_token(sesion, cliente, NombreRol.ANALISTA)
    token_tesoreria = await _crear_token(sesion, cliente, NombreRol.TESORERIA)
    cuenta_id = await _crear_cuenta_en_auditoria(sesion, cliente, token_analista)

    # CU-08 (T-07, fila 12): observacion PARCIAL, la cuenta va a
    # GLOSADA_PARCIAL, no a GLOSADA.
    respuesta_observacion = await cliente.post(
        f"/cuentas/{cuenta_id}/observaciones",
        json={
            "motivo_codigo": "OBS-01",
            "es_parcial": True,
            "detalle_campo_objetado": "Duplicidad parcial de un procedimiento",
        },
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta_observacion.status_code == 201, respuesta_observacion.text
    cuerpo_observacion = respuesta_observacion.json()
    assert cuerpo_observacion["estado_cuenta"] == "GLOSADA_PARCIAL"
    observacion_id = int(cuerpo_observacion["observacion_id"])

    # CU-10: la observacion parcial se responde, pero no mueve la
    # cuenta (Tabla 58/65/66 no define GLOSADA_PARCIAL -> SUBSANADA).
    respuesta_respuesta = await cliente.post(
        f"/observaciones/{observacion_id}/respuesta",
        json={"respuesta_texto": "Se corrige la duplicidad detectada."},
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta_respuesta.status_code == 204, respuesta_respuesta.text

    cuenta_tras_respuesta = await sesion.get(CuentaMedicaModelo, cuenta_id)
    assert cuenta_tras_respuesta is not None
    assert cuenta_tras_respuesta.estado == "GLOSADA_PARCIAL"

    # T-10 (fila 13): liquidacion parcial desde GLOSADA_PARCIAL.
    respuesta_liquidacion = await cliente.post(
        f"/cuentas/{cuenta_id}/liquidacion",
        json={"monto_liquidado": "800.00"},
        headers={"Authorization": f"Bearer {token_tesoreria}"},
    )
    assert respuesta_liquidacion.status_code == 201, respuesta_liquidacion.text
    assert respuesta_liquidacion.json()["estado_cuenta"] == "LIQUIDADA_PARCIAL"

    # T-11 (fila 15): el pago difiere del monto liquidado -- la
    # conciliacion avanza igual (Tabla 51, flujo alternativo), solo
    # queda la diferencia registrada.
    respuesta_pago = await cliente.post(
        f"/cuentas/{cuenta_id}/pago",
        json={"monto_pagado": "750.00"},
        headers={"Authorization": f"Bearer {token_tesoreria}"},
    )
    assert respuesta_pago.status_code == 201, respuesta_pago.text
    cuerpo_pago = respuesta_pago.json()
    assert cuerpo_pago["estado_cuenta"] == "PAGADA_PARCIAL"
    assert cuerpo_pago["diferencia"] == "-50.00"

    # CU-13 (Tabla 52): "el sistema verifica que el monto conciliado
    # corresponda al liquidado" -- con una diferencia pendiente, el
    # cierre se rechaza.
    respuesta_cierre = await cliente.post(
        f"/cuentas/{cuenta_id}/cierre",
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta_cierre.status_code == 409, respuesta_cierre.text
    assert respuesta_cierre.json()["codigo"] == "CIERRE_NO_PROCEDE"

    # `populate_existing`: ya se cargo esta misma fila mas arriba
    # (cuenta_tras_respuesta) -- sin esto, `sesion.get` devolveria esa
    # instancia ya en el mapa de identidad sin volver a consultarla.
    cuenta_final = await sesion.get(CuentaMedicaModelo, cuenta_id, populate_existing=True)
    assert cuenta_final is not None
    assert cuenta_final.estado == "PAGADA_PARCIAL"
