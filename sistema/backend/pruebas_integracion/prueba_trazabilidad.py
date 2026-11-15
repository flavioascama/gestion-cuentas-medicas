"""Escenario de integracion de /cuentas/{id}/historial,
/cuentas/{id}/expediente e /indicadores (CU-14 a CU-16, Fase 29):
ejercitado contra la API HTTP real y el Postgres real del stack,
incluido el encadenamiento de eventos real (RegistroEventosSql).

Requiere el stack arriba (postgres, backend) -- no hacen falta los
simuladores -- y corre aparte de la suite rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_trazabilidad.py -q
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_integracion import EventoModelo, IafasModelo
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt

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
            "apellidos_asegurado": "De Prueba Fase29",
            "iafas_id": iafas_id,
            "fecha_prestacion": "2026-09-10",
            "hora_prestacion": "09:00:00",
        },
        headers={"Authorization": f"Bearer {token_analista}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    return int(respuesta.json()["cuenta_id"])


async def prueba_iniciar_sesion_registra_un_evento_de_sesion_iniciada(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    nombre_usuario = f"integracion.analista.{uuid.uuid4().hex[:12]}"
    registrar = RegistrarUsuario(RepositorioUsuariosSql(sesion), VerificadorClaveBcrypt())
    usuario = await registrar.ejecutar(
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

    # RT-08/control C-08 (Fase 29): la bitacora de accesos se lee del
    # almacen de eventos -- el inicio de sesion exitoso queda registrado
    # con el encadenamiento real (RegistroEventosSql), no un doble.
    tipo_evento = (
        await sesion.execute(
            sa.select(EventoModelo.tipo_evento).where(
                EventoModelo.tipo_agregado == "SESION_USUARIO",
                EventoModelo.agregado_id == usuario.id,
                EventoModelo.tipo_evento == "SESION_INICIADA",
            )
        )
    ).scalar_one()
    assert tipo_evento == "SESION_INICIADA"


async def prueba_historial_se_reconstruye_y_registra_la_consulta_en_la_bitacora(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    token_analista = await _crear_token(sesion, cliente, NombreRol.ANALISTA)
    token_jefe = await _crear_token(sesion, cliente, NombreRol.JEFE)
    cuenta_id = await _crear_cuenta(sesion, cliente, token_analista)

    primera_respuesta = await cliente.get(
        f"/cuentas/{cuenta_id}/historial", headers={"Authorization": f"Bearer {token_jefe}"}
    )
    assert primera_respuesta.status_code == 200, primera_respuesta.text
    primer_cuerpo = primera_respuesta.json()
    assert primer_cuerpo["cadena_integra"] is True
    assert [e["tipo_evento"] for e in primer_cuerpo["eventos"]] == ["CUENTA_REGISTRADA"]

    segunda_respuesta = await cliente.get(
        f"/cuentas/{cuenta_id}/historial", headers={"Authorization": f"Bearer {token_jefe}"}
    )
    assert segunda_respuesta.status_code == 200, segunda_respuesta.text
    # La primera consulta quedo registrada como un evento mas: la
    # segunda corrida ya la ve en su propio historial.
    tipos_segunda = [e["tipo_evento"] for e in segunda_respuesta.json()["eventos"]]
    assert tipos_segunda == ["CUENTA_REGISTRADA", "HISTORIAL_CONSULTADO"]


async def prueba_exportar_expediente_por_la_api_real(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    token_analista = await _crear_token(sesion, cliente, NombreRol.ANALISTA)
    token_jefe = await _crear_token(sesion, cliente, NombreRol.JEFE)
    cuenta_id = await _crear_cuenta(sesion, cliente, token_analista)

    respuesta = await cliente.post(
        f"/cuentas/{cuenta_id}/expediente",
        json={"motivo": "auditoria externa de la aseguradora"},
        headers={"Authorization": f"Bearer {token_jefe}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["cuenta_medica_id"] == cuenta_id
    assert cuerpo["historial"]["cadena_integra"] is True

    historial_tras_exportar = await cliente.get(
        f"/cuentas/{cuenta_id}/historial", headers={"Authorization": f"Bearer {token_jefe}"}
    )
    tipos = [e["tipo_evento"] for e in historial_tras_exportar.json()["eventos"]]
    assert "EXPEDIENTE_EXPORTADO" in tipos


async def prueba_indicadores_del_ciclo_por_la_api_real(
    sesion: AsyncSession, cliente: AsyncClient
) -> None:
    token_analista = await _crear_token(sesion, cliente, NombreRol.ANALISTA)
    token_gerente = await _crear_token(sesion, cliente, NombreRol.GERENTE)
    await _crear_cuenta(sesion, cliente, token_analista)

    respuesta = await cliente.get(
        "/indicadores", headers={"Authorization": f"Bearer {token_gerente}"}
    )
    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["cuentas_evaluadas"] >= 1
    assert any(d["estado"] == "REGISTRADA" for d in cuerpo["distribucion_por_estado"])
