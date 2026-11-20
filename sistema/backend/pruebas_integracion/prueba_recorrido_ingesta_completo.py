"""Prueba de integracion pedida por la adenda de ingesta y completitud
(docs/ADENDA_INGESTA_Y_COMPLETITUD_CUENTA.md, Seccion 6: "una cuenta
creada por el nuevo endpoint recorre los pasos ... contra los tres
simuladores", ampliada por la propia adenda del simulador PSE): registrar,
verificar cobertura, codificar, emitir el comprobante de pago (contra el
simulador PSE real -- ya no una siembra directa en la base de datos),
completitud (solo lee: la cuenta se facturo al emitir), generar lote, cargar en el
validador, obtener el .S01, remitir a la IAFAS, enviar a SUSALUD.

Requiere el stack completo levantado -- postgres, backend, trabajador,
acredita-salud, tedef-web, receptor-iafas, pse -- y corre aparte de la
suite rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_recorrido_ingesta_completo.py -q"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo
from pruebas_integracion.conftest import esperar_hasta
from pruebas_integracion.prueba_sesion_asistida_y_cobertura import (
    _responder_captcha,
    _sesion_por_id,
    _solicitar_sesion,
    _texto_captcha_vigente,
    _TokenParaRol,
)
from pruebas_integracion.prueba_validacion_lotes import (
    _asegurar_sesion_tedef_web_activa,
    _cargar_en_validador,
    _estado_lote,
    _generar_lote,
)

_IAFAS_ID = 4
_PERIODO = "202607"
_CODIGO_CPMS_VIGENTE = "59401"
_TIPO_TRABAJO_MONITOREAR = "MONITOREAR_RESPUESTA_IAFAS"
_TIMEOUT_INGRESO_SEGUNDOS = 30.0
_TIMEOUT_TRABAJO_SEGUNDOS = 60.0
_TIMEOUT_VALIDACION_SEGUNDOS = 60.0
_TIMEOUT_MONITOREO_SEGUNDOS = 60.0


async def _asegurar_sesion_acredita_salud_activa(cliente: AsyncClient, token: str) -> None:
    """Mismo patron idempotente que
    `prueba_validacion_lotes._asegurar_sesion_tedef_web_activa`, pero
    para acredita_salud: reutiliza una sesion ACTIVA si ya la dejo una
    corrida anterior de `prueba_sesion_asistida_y_cobertura.py` en el
    mismo Postgres, y si no, resuelve el CAPTCHA ella misma."""

    sesion_id = await _solicitar_sesion(cliente, token)

    async def _sesion_lista() -> str | None:
        fila = await _sesion_por_id(cliente, token, sesion_id)
        estado = str(fila["estado"])
        return estado if estado in ("ESPERANDO_CAPTCHA", "ACTIVA") else None

    estado = await esperar_hasta(_sesion_lista, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)
    if estado == "ACTIVA":
        return

    texto = await _texto_captcha_vigente()
    respuesta = await _responder_captcha(cliente, token, sesion_id, texto)
    assert respuesta.status_code == 204, respuesta.text

    async def _esta_activa() -> bool:
        fila = await _sesion_por_id(cliente, token, sesion_id)
        return bool(fila["estado"] == "ACTIVA")

    await esperar_hasta(_esta_activa, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)


async def _registrar_cuenta(cliente: AsyncClient, token: str) -> int:
    # Reutiliza un asegurado YA sembrado (Nydia Sarmiento Acosta, iafas_id
    # 4): RepositorioIngestaCuentasSql busca por (tipo_documento,
    # numero_documento) y reutiliza la fila existente si coincide (nunca
    # crea un duplicado), y el simulador ACREDITA SALUD solo reconoce a
    # los asegurados de sus propios datos semilla -- un numero de
    # documento inventado aqui mismo no existiria en su roster y
    # CONSULTAR_COBERTURA fallaria con "no encontro al asegurado".
    respuesta = await cliente.post(
        "/cuentas",
        json={
            "tipo_documento_asegurado": "1",
            "numero_documento_asegurado": "53679371",
            "nombres_asegurado": "Nydia",
            "apellidos_asegurado": "Sarmiento Acosta",
            "iafas_id": _IAFAS_ID,
            "fecha_prestacion": date.today().isoformat(),
            "hora_prestacion": "09:00:00",
            "diagnostico_principal_cie10": "A072",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 201, respuesta.text
    return int(respuesta.json()["cuenta_id"])


async def _verificar_cobertura(cliente: AsyncClient, token: str, cuenta_id: int) -> None:
    await _asegurar_sesion_acredita_salud_activa(cliente, token)
    respuesta = await cliente.post(
        f"/cuentas/{cuenta_id}/cobertura", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 202, respuesta.text
    trabajo_id = respuesta.json()["trabajo_id"]

    async def _completado() -> bool:
        detalle = await cliente.get(
            f"/trabajos/{trabajo_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert detalle.status_code == 200, detalle.text
        return bool(detalle.json()["estado"] == "COMPLETADO")

    await esperar_hasta(_completado, tiempo_limite_segundos=_TIMEOUT_TRABAJO_SEGUNDOS)


async def _codificar_procedimiento(cliente: AsyncClient, token: str, cuenta_id: int) -> None:
    respuesta = await cliente.post(
        f"/cuentas/{cuenta_id}/procedimientos",
        json={
            "descripcion_registrada": "Atencion prenatal",
            "codigo_elegido": _CODIGO_CPMS_VIGENTE,
            "posicion_aceptada": None,
            "cantidad": 1,
            "monto_unitario": "50.00",
            "fecha": date.today().isoformat(),
            "inicio_sugerencia": datetime.now(UTC).isoformat(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 201, respuesta.text


async def _emitir_comprobante_de_pago(cliente: AsyncClient, token: str, cuenta_id: int) -> None:
    respuesta = await cliente.post(
        f"/cuentas/{cuenta_id}/comprobante", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 201, respuesta.text


async def _consultar_completitud(
    cliente: AsyncClient, token: str, cuenta_id: int
) -> dict[str, Any]:
    respuesta = await cliente.get(
        f"/cuentas/{cuenta_id}/completitud", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()  # type: ignore[no-any-return]


async def _remitir_a_iafas_y_esperar_respuesta(
    sesion: AsyncSession, cliente: AsyncClient, token: str, lote_id: int
) -> None:
    respuesta = await cliente.post(
        f"/lotes/{lote_id}/remision-iafas", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["exitosa"] is True, respuesta.text

    # RemitirLote encola el primer chequeo de monitoreo a 15 minutos
    # reales (mismo ajuste que prueba_remision_y_susalud.py): se adelanta
    # sin tocar la logica de negocio.
    await sesion.execute(
        sa.update(TrabajoModelo)
        .where(
            TrabajoModelo.tipo == _TIPO_TRABAJO_MONITOREAR,
            sa.cast(TrabajoModelo.carga_util["lote_id"].as_string(), sa.Integer) == lote_id,
        )
        .values(proximo_intento=sa.func.now())
    )
    await sesion.commit()

    async def _con_respuesta() -> bool:
        acuses = await cliente.get(
            f"/lotes/{lote_id}/acuses", headers={"Authorization": f"Bearer {token}"}
        )
        assert acuses.status_code == 200, acuses.text
        cuerpo = acuses.json()
        return bool(cuerpo and cuerpo[0]["respuesta_receptor"])

    await esperar_hasta(_con_respuesta, tiempo_limite_segundos=_TIMEOUT_MONITOREO_SEGUNDOS)
    assert await _estado_lote(cliente, token, lote_id) == "ACEPTADO"


async def _enviar_a_susalud_y_esperar(cliente: AsyncClient, token: str, lote_id: int) -> None:
    respuesta = await cliente.post(
        "/lotes/envio-susalud",
        json={"periodo": _PERIODO},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 202, respuesta.text

    async def _enviado() -> bool:
        detalle = await cliente.get(
            f"/lotes/{lote_id}", headers={"Authorization": f"Bearer {token}"}
        )
        return bool(detalle.json()["enviado_susalud_en"] is not None)

    await esperar_hasta(_enviado, tiempo_limite_segundos=_TIMEOUT_MONITOREO_SEGUNDOS)


async def prueba_recorrido_completo_desde_ingesta_hasta_susalud(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    token_analista = await token_para_rol(NombreRol.ANALISTA)
    token_auditor = await token_para_rol(NombreRol.AUDITOR)

    # 1. Registrar (adenda, punto 1): sin pasar por datos sinteticos.
    cuenta_id = await _registrar_cuenta(cliente, token_analista)
    completitud_inicial = await _consultar_completitud(cliente, token_analista, cuenta_id)
    assert completitud_inicial["estado_cuenta"] == "REGISTRADA"
    assert completitud_inicial["completa"] is False

    # 2. Verificar cobertura en ACREDITA SALUD (sesion asistida real).
    await _verificar_cobertura(cliente, token_analista, cuenta_id)

    # 3. Codificar un procedimiento CPMS (rol auditor).
    await _codificar_procedimiento(cliente, token_auditor, cuenta_id)

    # 4. Comprobante de pago, emitido contra el simulador PSE real.
    await _emitir_comprobante_de_pago(cliente, token_analista, cuenta_id)

    # 5. Completitud: las cuatro piezas (paciente, cobertura, codificacion,
    #    comprobante) ya estan OK; la cuenta quedo FACTURADA al emitir el
    #    comprobante (2026-11-19) y la consulta solo lo lee.
    completitud_final = await _consultar_completitud(cliente, token_analista, cuenta_id)
    assert completitud_final["estado_cuenta"] == "FACTURADA"
    assert completitud_final["completa"] is True
    assert all(p["completa"] for p in completitud_final["piezas"])

    # 6. Generar lote.
    resultado_lote = await _generar_lote(cliente, token_analista, _IAFAS_ID, cuenta_id, _PERIODO)
    assert resultado_lote.conforme is True, resultado_lote.cuerpo_completo
    lote_id = resultado_lote.lote_id
    assert lote_id is not None

    # 7 y 8. Cargar en el validador TEDEF Web y obtener el .S01.
    await _asegurar_sesion_tedef_web_activa(sesion, cliente, token_analista)
    await _cargar_en_validador(cliente, token_analista, lote_id)

    async def _lote_validado() -> bool:
        estado = await _estado_lote(cliente, token_analista, lote_id)
        assert estado != "OBSERVADO_VALIDADOR", f"El lote {lote_id} quedo observado."
        return bool(estado == "VALIDADO")

    await esperar_hasta(_lote_validado, tiempo_limite_segundos=_TIMEOUT_VALIDACION_SEGUNDOS)

    detalle_lote = await cliente.get(
        f"/lotes/{lote_id}", headers={"Authorization": f"Bearer {token_analista}"}
    )
    assert detalle_lote.json()["nombre_s01"] is not None
    assert detalle_lote.json()["sha256_s01"] is not None

    # 9. Remitir a la IAFAS y enviar a SUSALUD.
    await _remitir_a_iafas_y_esperar_respuesta(sesion, cliente, token_analista, lote_id)
    await _enviar_a_susalud_y_esperar(cliente, token_analista, lote_id)
