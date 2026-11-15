"""Escenario de integracion de /observaciones (CU-08 a CU-10, Fase 26):
el ciclo completo -- registrar y clasificar, asignar el responsable y
responder -- ejercitado contra la API HTTP real y el Postgres real del
stack, no contra SQLite en memoria. Es la razon por la que la Fase 26 no
se considero cerrada hasta que esta ruta existio: las pruebas de
`pruebas/` ya cubren el caso de uso en si, pero no que este expuesto
correctamente como ruta HTTP con sus guardas de rol.

Requiere el stack arriba (postgres, backend) -- no hacen falta los
simuladores, porque el precondicion de CU-08 (cuenta en EN_AUDITORIA) se
fija de forma directa, igual que hace prueba_validacion_lotes.py con sus
propios estados -- y corre aparte de la suite rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_observaciones_glosas.py -q
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    EventoModelo,
    IafasModelo,
)
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt
from pruebas_integracion.apoyo_estados import fijar_estado_de_prueba

_CLAVE_PRUEBA = "Clave-Valida-123"


async def _crear_usuario_y_token(
    sesion: AsyncSession, cliente: AsyncClient, rol: NombreRol
) -> tuple[int, str]:
    nombre_usuario = f"integracion.{rol.value}.{uuid.uuid4().hex[:12]}"
    registrar = RegistrarUsuario(RepositorioUsuariosSql(sesion), VerificadorClaveBcrypt())
    usuario = await registrar.ejecutar(
        nombre_usuario=nombre_usuario,
        clave=_CLAVE_PRUEBA,
        nombres=nombre_usuario,
        roles=frozenset({rol}),
    )
    await sesion.commit()
    assert usuario.id is not None
    respuesta = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": nombre_usuario, "clave": _CLAVE_PRUEBA}
    )
    assert respuesta.status_code == 200, respuesta.text
    return usuario.id, str(respuesta.json()["token"])


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
            "apellidos_asegurado": "De Prueba Fase26",
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


async def prueba_ciclo_completo_de_observacion_por_la_api_real(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    id_analista, token_analista = await _crear_usuario_y_token(sesion, cliente, NombreRol.ANALISTA)
    _, token_auditor = await _crear_usuario_y_token(sesion, cliente, NombreRol.AUDITOR)
    _, token_jefe = await _crear_usuario_y_token(sesion, cliente, NombreRol.JEFE)

    cuenta_id = await _crear_cuenta_en_auditoria(sesion, cliente, token_analista)

    # CU-08: el analista registra y clasifica -- OBS-01 es ADMINISTRATIVA
    # en el catalogo sembrado por la migracion de la Fase 26.
    respuesta_registro = await cliente.post(
        f"/cuentas/{cuenta_id}/observaciones",
        json={
            "motivo_codigo": "OBS-01",
            "es_parcial": False,
            "detalle_campo_objetado": "Historia clinica incompleta",
        },
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta_registro.status_code == 201, respuesta_registro.text
    cuerpo_registro = respuesta_registro.json()
    observacion_id = int(cuerpo_registro["observacion_id"])
    assert cuerpo_registro["naturaleza"] == "ADMINISTRATIVA"
    assert cuerpo_registro["responsable_rol"] == "analista"
    assert cuerpo_registro["estado_cuenta"] == "GLOSADA"

    respuesta_listado = await cliente.get(
        f"/cuentas/{cuenta_id}/observaciones",
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert respuesta_listado.status_code == 200, respuesta_listado.text
    (observacion,) = (o for o in respuesta_listado.json() if o["id"] == observacion_id)
    assert observacion["estado"] == "ABIERTA"

    respuesta_motivos = await cliente.get(
        "/observaciones/motivos", headers={"Authorization": f"Bearer {token_jefe}"}
    )
    assert respuesta_motivos.status_code == 200, respuesta_motivos.text
    assert any(m["codigo"] == "OBS-01" for m in respuesta_motivos.json())

    # CU-09: el jefe confirma el responsable (no cambia la naturaleza).
    respuesta_asignacion = await cliente.patch(
        f"/observaciones/{observacion_id}/asignacion",
        json={"responsable_usuario_id": id_analista},
        headers={"Authorization": f"Bearer {token_jefe}"},
    )
    assert respuesta_asignacion.status_code == 204, respuesta_asignacion.text

    # CU-10: el responsable (analista, por ser ADMINISTRATIVA) responde.
    # Al no ser parcial, cierra el control de plazo y lleva la cuenta de
    # GLOSADA a SUBSANADA (T-08).
    respuesta_respuesta = await cliente.post(
        f"/observaciones/{observacion_id}/respuesta",
        json={
            "respuesta_texto": "Se adjunta historia clinica completa.",
            "respuesta_sustento": "anexo-01.pdf",
        },
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta_respuesta.status_code == 204, respuesta_respuesta.text

    cuenta_final = await sesion.get(CuentaMedicaModelo, cuenta_id)
    assert cuenta_final is not None
    assert cuenta_final.estado == "SUBSANADA"

    respuesta_listado_final = await cliente.get(
        f"/cuentas/{cuenta_id}/observaciones",
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    (observacion_final,) = (o for o in respuesta_listado_final.json() if o["id"] == observacion_id)
    assert observacion_final["estado"] == "RESPONDIDA"
    assert observacion_final["responsable_usuario_id"] == id_analista
    assert observacion_final["respuesta_texto"] == "Se adjunta historia clinica completa."

    # R3.3/R3.4: cada transicion de la observacion y de la cuenta quedo
    # registrada en el almacen de eventos, sin registro manual. El evento
    # de la respuesta (OBSERVACION_RESPONDIDA) lleva el propio paso de
    # GLOSADA a SUBSANADA en sus campos estado_previo/estado_nuevo -- no
    # hay un evento SUBSANACION aparte (ResponderObservacion.ejecutar).
    filas_evento = (
        await sesion.execute(
            sa.select(
                EventoModelo.tipo_evento, EventoModelo.estado_previo, EventoModelo.estado_nuevo
            )
            .where(EventoModelo.cuenta_medica_id == cuenta_id)
            .order_by(EventoModelo.version)
        )
    ).all()
    tipos_evento = [fila.tipo_evento for fila in filas_evento]
    assert "GLOSA" in tipos_evento
    assert "OBSERVACION_REASIGNADA" in tipos_evento
    (fila_respuesta,) = (f for f in filas_evento if f.tipo_evento == "OBSERVACION_RESPONDIDA")
    assert fila_respuesta.estado_previo == "GLOSADA"
    assert fila_respuesta.estado_nuevo == "SUBSANADA"
