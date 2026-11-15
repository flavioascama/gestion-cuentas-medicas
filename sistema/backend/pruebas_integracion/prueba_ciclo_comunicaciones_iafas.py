"""Ciclo completo con las comunicaciones de la IAFAS automatizadas
(2026-11-13): los datos recorren todas las entidades, simuladas, como si
la persona encargada hiciera cada paso a mano.

Clinica: registrar, verificar cobertura (ACREDITA SALUD), codificar,
emitir el comprobante (PSE), facturar, generar el lote, validarlo (TEDEF
Web), remitirlo (FTP del receptor IAFAS) y recibir la aceptacion.
IAFAS (simulador receptor_iafas): su auditor decide sobre cada
comprobante y comunica el resultado por su portal o por correo
(simulador de correo). Robot de comunicaciones: lee el correo y el
portal y registra la conformidad, la glosa, la liquidacion y el pago.
Persona responsable: responde la glosa en el sistema; el robot entrega
la respuesta en el portal de la IAFAS. Al final, el analista cierra las
cuentas y el lote se envia a SUSALUD.

Tres comprobantes en un lote:
- A: glosa total por correo, que la IAFAS mantiene una vez y despues
  liquida y paga (GLOSADA -> SUBSANADA -> GLOSADA -> SUBSANADA ->
  LIQUIDADA -> PAGADA -> CERRADA).
- B: conformidad por el portal (EN_AUDITORIA -> LIQUIDADA -> PAGADA ->
  CERRADA).
- C: glosa parcial por el portal (GLOSADA_PARCIAL -> LIQUIDADA_PARCIAL ->
  PAGADA_PARCIAL -> CERRADA).

Requiere el stack completo y los simuladores (incluido simuladores/correo):
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_ciclo_comunicaciones_iafas.py -q"""

from __future__ import annotations

import asyncio
import email
import imaplib
import os
from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

import httpx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.entidades import NombreRol
from pruebas_integracion.conftest import esperar_hasta
from pruebas_integracion.prueba_recorrido_ingesta_completo import (
    _codificar_procedimiento,
    _consultar_completitud,
    _emitir_comprobante_de_pago,
    _enviar_a_susalud_y_esperar,
    _registrar_cuenta,
    _remitir_a_iafas_y_esperar_respuesta,
    _verificar_cobertura,
)
from pruebas_integracion.prueba_sesion_asistida_y_cobertura import _TokenParaRol
from pruebas_integracion.prueba_validacion_lotes import (
    _asegurar_sesion_tedef_web_activa,
    _cargar_en_validador,
    _estado_lote,
)

_IAFAS_ID = 4
_PERIODO = "202607"
_URL_RECEPTOR_IAFAS = "http://receptor-iafas:8000"
_TIMEOUT_SEGUNDOS = 90.0


def _cabecera(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _cuenta_facturada(cliente: AsyncClient, analista: str, auditor: str) -> int:
    cuenta_id = await _registrar_cuenta(cliente, analista)
    await _verificar_cobertura(cliente, analista, cuenta_id)
    await _codificar_procedimiento(cliente, auditor, cuenta_id)
    await _emitir_comprobante_de_pago(cliente, analista, cuenta_id)
    completitud = await _consultar_completitud(cliente, analista, cuenta_id)
    assert completitud["estado_cuenta"] == "FACTURADA", completitud
    return cuenta_id


async def _lote_aceptado(
    sesion: AsyncSession, cliente: AsyncClient, analista: str, cuenta_ids: list[int]
) -> int:
    respuesta = await cliente.post(
        "/lotes",
        json={"iafas_id": _IAFAS_ID, "periodo": _PERIODO, "cuenta_ids": cuenta_ids},
        headers=_cabecera(analista),
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["conforme"] is True, respuesta.json()
    lote_id = int(respuesta.json()["lote_id"])

    await _asegurar_sesion_tedef_web_activa(sesion, cliente, analista)
    await _cargar_en_validador(cliente, analista, lote_id)

    async def _validado() -> bool:
        estado = await _estado_lote(cliente, analista, lote_id)
        assert estado != "OBSERVADO_VALIDADOR", f"El lote {lote_id} quedo observado."
        return estado == "VALIDADO"

    await esperar_hasta(_validado, tiempo_limite_segundos=_TIMEOUT_SEGUNDOS)
    await _remitir_a_iafas_y_esperar_respuesta(sesion, cliente, analista, lote_id)
    return lote_id


async def _documento(cliente: AsyncClient, token: str, cuenta_id: int) -> str:
    respuesta = await cliente.get(f"/cuentas/{cuenta_id}/comprobante", headers=_cabecera(token))
    assert respuesta.status_code == 200, respuesta.text
    vigente = respuesta.json()["vigente"]
    return f"{vigente['serie']}{vigente['numero']}"


async def _auditor_iafas_decide(documento: str, formulario: dict[str, str]) -> None:
    """El auditor de la aseguradora registra su decision en el sistema de la
    IAFAS (el simulador), que la comunica por el canal elegido."""
    async with httpx.AsyncClient(base_url=_URL_RECEPTOR_IAFAS, timeout=15.0) as simulador:
        ruta = f"/admin/documentos/{documento}/auditoria"
        respuesta = await simulador.post(ruta, data=formulario)
    assert respuesta.status_code == 303, respuesta.text


async def _estado_cuenta(cliente: AsyncClient, token: str, cuenta_id: int) -> str:
    completitud = await _consultar_completitud(cliente, token, cuenta_id)
    return str(completitud["estado_cuenta"])


async def _comunicaciones(cliente: AsyncClient, token: str, cuenta_id: int) -> list[dict[str, Any]]:
    respuesta = await cliente.get(
        "/comunicaciones-iafas", params={"cuenta_id": cuenta_id}, headers=_cabecera(token)
    )
    assert respuesta.status_code == 200, respuesta.text
    return list(reversed(respuesta.json()))  # en el orden en que llegaron


async def _revisar_hasta(
    cliente: AsyncClient, token: str, condicion: Callable[[], Awaitable[bool]]
) -> None:
    """Como la persona que vuelve a mirar el portal y el correo: pide la
    revision y, si lo esperado aun no llego (una revision ya en curso pudo
    empezar antes de que la IAFAS lo emitiera), la pide otra vez."""
    for _ in range(4):
        respuesta = await cliente.post("/comunicaciones-iafas/revision", headers=_cabecera(token))
        assert respuesta.status_code == 202, respuesta.text
        trabajo_id = respuesta.json()["trabajo_id"]

        async def _terminado(trabajo: int = trabajo_id) -> bool:
            detalle = await cliente.get(f"/trabajos/{trabajo}", headers=_cabecera(token))
            estado = detalle.json()["estado"]
            assert estado != "AGOTADO", detalle.json()
            return bool(estado == "COMPLETADO")

        await esperar_hasta(_terminado, tiempo_limite_segundos=_TIMEOUT_SEGUNDOS)
        if await condicion():
            return
    raise AssertionError("Las comunicaciones esperadas de la IAFAS no llegaron.")


async def _hasta_estado(
    cliente: AsyncClient, token: str, cuenta_id: int, estado: str
) -> list[dict[str, Any]]:
    async def _llego() -> bool:
        return await _estado_cuenta(cliente, token, cuenta_id) == estado

    await _revisar_hasta(cliente, token, _llego)
    return await _comunicaciones(cliente, token, cuenta_id)


async def _responder_ultima_observacion(
    cliente: AsyncClient, token: str, cuenta_id: int, texto: str
) -> dict[str, Any]:
    """La persona responsable responde en el sistema y el robot entrega la
    respuesta en el portal de la IAFAS."""
    respuesta = await cliente.get(f"/cuentas/{cuenta_id}/observaciones", headers=_cabecera(token))
    pendiente = next(o for o in respuesta.json() if o["estado"] != "RESPONDIDA")
    registro = await cliente.post(
        f"/observaciones/{pendiente['id']}/respuesta",
        json={"respuesta_texto": texto, "respuesta_sustento": "Historia clinica foliada."},
        headers=_cabecera(token),
    )
    assert registro.status_code == 204, registro.text

    async def _entregada() -> dict[str, Any] | None:
        for comunicacion in await _comunicaciones(cliente, token, cuenta_id):
            if comunicacion["observacion_id"] == pendiente["id"]:
                return comunicacion if comunicacion["respuesta_remitida_en"] else None
        return None

    return await esperar_hasta(_entregada, tiempo_limite_segundos=_TIMEOUT_SEGUNDOS)


async def _cerrar(cliente: AsyncClient, token: str, cuenta_id: int) -> None:
    respuesta = await cliente.post(f"/cuentas/{cuenta_id}/cierre", headers=_cabecera(token))
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado_cuenta"] == "CERRADA"


def _codigos_no_leidos() -> set[str]:
    """Lo que sigue sin leer en la bandeja de la clinica."""
    cliente = imaplib.IMAP4(os.environ.get("CORREO_IMAP_HOST", "correo"), 3143)
    try:
        cliente.login(os.environ["CORREO_USUARIO"], os.environ["CORREO_CLAVE"])
        cliente.select("INBOX", readonly=True)
        _, datos = cliente.search(None, "UNSEEN")
        codigos = set()
        for numero in datos[0].split():
            _, partes = cliente.fetch(numero, "(BODY.PEEK[HEADER])")
            crudo = next(p[1] for p in partes if isinstance(p, tuple))
            codigos.add(str(email.message_from_bytes(crudo)["X-Comunicacion-Iafas"]))
        return codigos
    finally:
        cliente.logout()


async def _motivo_administrativo(cliente: AsyncClient, token: str) -> str:
    respuesta = await cliente.get("/observaciones/motivos", headers=_cabecera(token))
    assert respuesta.status_code == 200, respuesta.text
    return str(next(m["codigo"] for m in respuesta.json() if m["naturaleza"] == "ADMINISTRATIVA"))


async def _liquidacion(cliente: AsyncClient, token: str, cuenta_id: int) -> dict[str, Any]:
    respuesta = await cliente.get(f"/cuentas/{cuenta_id}/liquidacion", headers=_cabecera(token))
    assert respuesta.status_code == 200, respuesta.text
    return dict(respuesta.json())


async def _ciclo_glosa_total_por_correo(
    cliente: AsyncClient, analista: str, cuenta_id: int, motivo: str
) -> list[str]:
    comunicaciones = await _hasta_estado(cliente, analista, cuenta_id, "GLOSADA")
    assert [(c["tipo"], c["canal"], c["resultado"]) for c in comunicaciones] == [
        ("OBSERVACION", "CORREO", "APLICADA")
    ]
    assert comunicaciones[0]["datos"]["motivo_codigo"] == motivo

    primera = await _responder_ultima_observacion(
        cliente, analista, cuenta_id, "Se adjunta la historia clinica."
    )
    # La IAFAS mantiene la observacion una vez: llega otra por correo.
    comunicaciones = await _hasta_estado(cliente, analista, cuenta_id, "GLOSADA")
    assert [c["tipo"] for c in comunicaciones] == ["OBSERVACION", "OBSERVACION"]

    segunda = await _responder_ultima_observacion(
        cliente, analista, cuenta_id, "Se adjunta el informe del medico tratante."
    )
    comunicaciones = await _hasta_estado(cliente, analista, cuenta_id, "PAGADA")
    assert [(c["tipo"], c["canal"]) for c in comunicaciones] == [
        ("OBSERVACION", "CORREO"),
        ("OBSERVACION", "CORREO"),
        ("LIQUIDACION", "CORREO"),
        ("PAGO", "CORREO"),
    ]
    assert all(c["resultado"] == "APLICADA" for c in comunicaciones)
    return [primera["codigo"], segunda["codigo"]] + [c["codigo"] for c in comunicaciones]


async def prueba_ciclo_completo_con_comunicaciones_de_la_iafas_automatizadas(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    analista = await token_para_rol(NombreRol.ANALISTA)
    auditor = await token_para_rol(NombreRol.AUDITOR)
    jefe = await token_para_rol(NombreRol.JEFE)

    # Clinica: tres cuentas facturadas, un lote, validado, remitido, aceptado.
    cuentas = [await _cuenta_facturada(cliente, analista, auditor) for _ in range(3)]
    lote_id = await _lote_aceptado(sesion, cliente, analista, cuentas)
    a, b, c = cuentas
    for cuenta_id in cuentas:
        assert await _estado_cuenta(cliente, analista, cuenta_id) == "EN_AUDITORIA"

    # IAFAS: su auditor decide sobre cada comprobante.
    motivo = await _motivo_administrativo(cliente, analista)
    glosa_total = {"resultado": "GLOSA", "canal": "CORREO", "motivo_codigo": motivo}
    await _auditor_iafas_decide(
        await _documento(cliente, analista, a),
        {**glosa_total, "detalle": "Falta sustento", "decision_respuesta": "MANTENER"},
    )
    await _auditor_iafas_decide(
        await _documento(cliente, analista, b), {"resultado": "CONFORME", "canal": "PORTAL"}
    )
    await _auditor_iafas_decide(
        await _documento(cliente, analista, c),
        {
            "resultado": "GLOSA_PARCIAL",
            "canal": "PORTAL",
            "motivo_codigo": motivo,
            "monto_glosado": "10.00",
            "detalle": "Cantidad mayor a la autorizada",
        },
    )

    # B: conformidad, liquidacion y pago por el portal.
    comunicaciones_b = await _hasta_estado(cliente, analista, b, "PAGADA")
    assert [(x["tipo"], x["canal"]) for x in comunicaciones_b] == [
        ("AUDITORIA_CONFORME", "PORTAL"),
        ("LIQUIDACION", "PORTAL"),
        ("PAGO", "PORTAL"),
    ]
    liquidacion_b = await _liquidacion(cliente, analista, b)
    assert Decimal(liquidacion_b["diferencia"]) == 0

    # C: glosa parcial por el portal; tras la respuesta, liquidacion parcial.
    await _hasta_estado(cliente, analista, c, "GLOSADA_PARCIAL")
    await _responder_ultima_observacion(cliente, analista, c, "Se adjunta la autorizacion.")
    await _hasta_estado(cliente, analista, c, "PAGADA_PARCIAL")
    liquidacion_c = await _liquidacion(cliente, analista, c)
    assert Decimal(liquidacion_c["monto_liquidado"]) == (
        Decimal(liquidacion_b["monto_liquidado"]) - Decimal("10.00")
    )

    # A: glosa total por correo, mantenida una vez.
    codigos_a = await _ciclo_glosa_total_por_correo(cliente, analista, a, motivo)
    assert not set(codigos_a) & await asyncio.to_thread(_codigos_no_leidos)

    # Cierre de las tres y envio del lote a SUSALUD.
    for cuenta_id in cuentas:
        await _cerrar(cliente, analista, cuenta_id)
    await _enviar_a_susalud_y_esperar(cliente, analista, lote_id)

    historial = await cliente.get(f"/cuentas/{a}/historial", headers=_cabecera(jefe))
    assert historial.status_code == 200, historial.text
    assert historial.json()["cadena_integra"] is True
    tipos = [e["tipo_evento"] for e in historial.json()["eventos"]]
    assert tipos.count("COMUNICACION_IAFAS_RECIBIDA") == 4
    assert tipos.count("RESPUESTA_IAFAS_REMITIDA") == 2
