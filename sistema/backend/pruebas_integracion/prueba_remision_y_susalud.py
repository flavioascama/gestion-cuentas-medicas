"""Escenarios 9, 10 y 11 de la Seccion 14.2 del plan v3 (Integracion,
stack completo con los tres simuladores): Remision y respuesta, `.S01`
alterado, Envio a SUSALUD.

Requiere el stack completo levantado -- postgres, backend, trabajador,
tedef-web, receptor-iafas -- y corre aparte de la suite rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_remision_y_susalud.py -q

Reutiliza la sesion asistida de tedef_web (Seccion 8.5) que
`prueba_validacion_lotes.py` deja activa si ya corrio antes en la misma
sesion de Postgres; si no, la crea ella misma (mismo mecanismo
idempotente que `SolicitarSesionPlataforma`).

Cada prueba crea su propia cuenta FACTURADA nueva (`_crear_cuenta_facturada`)
en vez de depender de ids fijos de la carga sintetica: la version anterior
usaba las cuentas 18/23/54/62 de la IAFAS 2 (la unica, en los datos
sinteticos, sin ningun lote generado todavia -- el numerador de lote es
secuencial POR IAFAS y el simulador tedef_web recuerda para siempre, en su
propio almacenamiento persistente, cada numero+IAFAS ya registrado, asi que
una IAFAS "virgen" evitaba choques de numeracion sin tocar el simulador).
El problema: 18 y 62 son cuentas de un solo uso -- en cuanto una corrida
las deja en ENVIADA (Seccion 10.3 del plan: sin motor de transiciones que
las devuelva a FACTURADA), la siguiente corrida contra el mismo Postgres
de desarrollo (reutilizado entre sesiones, a diferencia de un Postgres de
CI que nace vacio en cada corrida) ya no las encuentra en
`obtener_documentos_facturados` y `GenerarLote` deja de ser conforme. Una
cuenta nueva por corrida no tiene ese problema, y tampoco reintroduce el
choque de numeracion: `siguiente_numero_lote` siempre lee el maximo real
en Postgres y avanza hacia adelante, nunca hacia atras, asi que una cuenta
nueva bajo cualquier IAFAS obtiene siempre un numero nuevo."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import httpx
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.rutas import ruta_local_s01
from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IpressModelo,
    ProcedimientoFacturadoModelo,
    TrabajoModelo,
)
from pruebas_integracion.conftest import esperar_hasta
from pruebas_integracion.prueba_sesion_asistida_y_cobertura import _TokenParaRol
from pruebas_integracion.prueba_validacion_lotes import (
    _URL_TEDEF_WEB,
    _asegurar_sesion_tedef_web_activa,
    _cargar_en_validador,
    _estado_lote,
    _generar_lote,
    _iafas_de_cuenta,
)

_TIMEOUT_VALIDACION_SEGUNDOS = 60.0
_TIMEOUT_MONITOREO_SEGUNDOS = 60.0
_TIPO_TRABAJO_MONITOREAR = "MONITOREAR_RESPUESTA_IAFAS"
_PERIODO_ENVIO_SUSALUD = "202512"


async def _crear_cuenta_facturada(sesion: AsyncSession) -> int:
    """Cuenta FACTURADA nueva, sembrada directo (mismo criterio que
    `cargar_cuentas_sinteticas.py`: estos escenarios prueban la
    validacion/remision/envio, no el recorrido de completitud que ya
    cubre `prueba_recorrido_ingesta_completo.py` de punta a punta) --
    con acreditacion, un procedimiento CPMS y un comprobante propios,
    que es lo que `GenerarLote` exige (Seccion 8.1: `documento` y
    `acreditacion` no pueden ser None)."""

    asegurado = (
        await sesion.execute(sa.select(AseguradoModelo).order_by(AseguradoModelo.id).limit(1))
    ).scalar_one()
    ipress = (
        await sesion.execute(sa.select(IpressModelo).order_by(IpressModelo.id).limit(1))
    ).scalar_one()
    identificador_unico = f"{uuid.uuid4().int % 10_000_000:07d}"

    cuenta = CuentaMedicaModelo(
        identificacion_interna=f"INT{identificador_unico}",
        asegurado_id=asegurado.id,
        iafas_id=asegurado.iafas_id,
        ipress_id=ipress.id,
        fecha_prestacion=date.today(),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica=identificador_unico,
        diagnostico_principal_cie10="A072",
        estado="FACTURADA",
    )
    sesion.add(cuenta)
    await sesion.flush()

    # Reutiliza la version CPMS ya vigente en vez de crear una nueva: la
    # "vigente" es la de mayor id, sin ninguna marca explicita (Seccion
    # 8.2, `RepositorioCpmsSql.version_vigente`) -- una version nueva por
    # cuenta de prueba correria ese puntero global compartido y rompería
    # `ConfirmarCodigoCpms` para el resto del sistema (encontrado en vivo:
    # asi fallo `prueba_recorrido_ingesta_completo.py` la primera vez que
    # esta funcion se escribio con una version propia por llamada).
    cpms_version_id = (
        await sesion.execute(
            sa.select(CpmsVersionModelo.id).order_by(CpmsVersionModelo.id.desc()).limit(1)
        )
    ).scalar_one()

    sesion.add(
        AcreditacionModelo(
            cuenta_id=cuenta.id,
            condicion_cobertura="ACREDITABLE",
            codigo_autorizacion=f"AUT{identificador_unico}",
            tipo_documento_autorizacion="03",
            codigo_asegurado=f"AS{identificador_unico}",
            tipo_afiliacion="1",
            instante=datetime.now(UTC),
            duracion_ms=100,
            componente_ejecutor="prueba_integracion",
        )
    )
    sesion.add(
        ProcedimientoFacturadoModelo(
            cuenta_id=cuenta.id,
            descripcion_registrada="Consulta de integracion",
            codigo_asignado="99201",
            cpms_version_id=cpms_version_id,
            origen_codigo="coincidencia_exacta",
            cantidad=1,
            monto_unitario="50.00",
            fecha=date.today(),
        )
    )
    sesion.add(
        DocumentoFacturadorModelo(
            cuenta_id=cuenta.id,
            ipress_id=ipress.id,
            tipo_documento_pago="01",
            serie="R001",
            numero=identificador_unico,
            fecha_emision=date.today(),
        )
    )
    await sesion.commit()
    return cuenta.id


async def _asegurar_modo_falla_limpio() -> None:
    """Defensivo: si una corrida anterior de `prueba_validacion_lotes.py`
    (que sí restaura el modo de falla en su propio `finally`) quedo
    interrumpida antes de llegar a esa linea, el simulador seguiria en
    `forzar_observaciones` y este archivo veria un OBSERVADO que no le
    corresponde a el. Correr esto primero es mas barato que depurar la
    causa cada vez."""

    async with httpx.AsyncClient(base_url=_URL_TEDEF_WEB, timeout=5.0) as cliente:
        respuesta = await cliente.get("/admin/falla")
        if respuesta.text.strip() != "ninguno":
            await cliente.post("/admin/falla", data={"modo": "ninguno"})


async def _generar_y_validar_lote(
    sesion: AsyncSession, cliente: AsyncClient, token: str, cuenta_id: int, periodo: str = "202609"
) -> int:
    await _asegurar_modo_falla_limpio()
    iafas_id = await _iafas_de_cuenta(sesion, cuenta_id)
    resultado = await _generar_lote(cliente, token, iafas_id, cuenta_id, periodo=periodo)
    assert resultado.conforme is True, resultado.cuerpo_completo
    lote_id = resultado.lote_id
    assert lote_id is not None

    await _asegurar_sesion_tedef_web_activa(sesion, cliente, token)
    await _cargar_en_validador(cliente, token, lote_id)

    async def _lote_validado() -> bool:
        estado = await _estado_lote(cliente, token, lote_id)
        assert estado != "OBSERVADO_VALIDADOR", f"El lote {lote_id} quedo observado."
        return bool(estado == "VALIDADO")

    await esperar_hasta(_lote_validado, tiempo_limite_segundos=_TIMEOUT_VALIDACION_SEGUNDOS)
    return lote_id


async def _ruta_s01(sesion: AsyncSession, lote_id: int, cliente: AsyncClient, token: str) -> str:
    detalle = await cliente.get(f"/lotes/{lote_id}", headers={"Authorization": f"Bearer {token}"})
    assert detalle.status_code == 200, detalle.text
    # DetalleLoteRespuesta no expone ruta_s01 (solo nombre/huella, Seccion
    # 11): se lee directo del modelo, con la misma sesion de SQLAlchemy.
    from app.infraestructura.persistencia.modelos_integracion import LoteFacturacionModelo

    lote = await sesion.get(LoteFacturacionModelo, lote_id)
    assert lote is not None and lote.ruta_s01 is not None
    return str(ruta_local_s01(lote.ruta_s01))


async def prueba_9_remision_y_respuesta_el_monitoreo_registra_el_resultado(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "Remision y respuesta": el receptor descifra, acepta o
    rechaza; el monitoreo registra el resultado. Sin forzar nada en el
    simulador receptor IAFAS: el camino por defecto tras un descifrado
    correcto es ACEPTADO (simuladores/receptor_iafas/app/procesador.py)."""

    token = await token_para_rol(NombreRol.ANALISTA)
    cuenta_id = await _crear_cuenta_facturada(sesion)
    lote_id = await _generar_y_validar_lote(sesion, cliente, token, cuenta_id)

    respuesta = await cliente.post(
        f"/lotes/{lote_id}/remision-iafas", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["exitosa"] is True, cuerpo

    # RemitirLote encola el primer chequeo de monitoreo a 15 minutos
    # reales (INTERVALO_INICIAL_MONITOREO, remitir_lote.py): una prueba
    # automatizada no puede ni debe esperar eso de verdad -- se adelanta
    # el `proximo_intento` de ese trabajo recien encolado a "ahora", sin
    # tocar la logica de negocio (mismo criterio que forzar `expira_en`
    # de una sesion de plataforma en vez de esperar su vencimiento real).
    await sesion.execute(
        sa.update(TrabajoModelo)
        .where(
            TrabajoModelo.tipo == _TIPO_TRABAJO_MONITOREAR,
            sa.cast(TrabajoModelo.carga_util["lote_id"].as_string(), sa.Integer) == lote_id,
        )
        .values(proximo_intento=sa.func.now())
    )
    await sesion.commit()

    async def _lote_con_respuesta() -> list[dict[str, Any]] | None:
        acuses = await cliente.get(
            f"/lotes/{lote_id}/acuses", headers={"Authorization": f"Bearer {token}"}
        )
        assert acuses.status_code == 200, acuses.text
        cuerpo_acuses = acuses.json()
        return cuerpo_acuses if cuerpo_acuses and cuerpo_acuses[0]["respuesta_receptor"] else None

    acuses = await esperar_hasta(
        _lote_con_respuesta, tiempo_limite_segundos=_TIMEOUT_MONITOREO_SEGUNDOS
    )
    assert acuses[0]["respuesta_receptor"] == "ACEPTADO", acuses[0]

    estado_final = await _estado_lote(cliente, token, lote_id)
    assert estado_final == "ACEPTADO"


async def prueba_10_s01_alterado_bloquea_la_remision(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario ".S01 alterado": si la huella no coincide, la remision
    se bloquea (Regla 11 del plan v3, `RemitirLote._obtener_lote_verificado`)."""

    token = await token_para_rol(NombreRol.ANALISTA)
    cuenta_id = await _crear_cuenta_facturada(sesion)
    lote_id = await _generar_y_validar_lote(sesion, cliente, token, cuenta_id)
    ruta_texto = await _ruta_s01(sesion, lote_id, cliente, token)

    ruta = Path(ruta_texto)
    contenido_original = ruta.read_bytes()
    try:
        ruta.write_bytes(contenido_original + b"\x00")
        respuesta = await cliente.post(
            f"/lotes/{lote_id}/remision-iafas", headers={"Authorization": f"Bearer {token}"}
        )
        assert respuesta.status_code == 409, respuesta.text
        assert "sha-256" in respuesta.text.lower() or "huella" in respuesta.text.lower()
    finally:
        ruta.write_bytes(contenido_original)

    estado_final = await _estado_lote(cliente, token, lote_id)
    assert estado_final == "VALIDADO", "El lote no debio avanzar tras el bloqueo de remision."


async def prueba_11_envio_a_susalud_informa_la_duplicidad(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "Envio a SUSALUD": los lotes del periodo quedan
    enviados; la duplicidad se informa. A SUSALUD se informan los lotes
    remitidos a la IAFAS (2026-11-19), asi que ambos se remiten antes."""

    token = await token_para_rol(NombreRol.ANALISTA)
    cuenta_id_1 = await _crear_cuenta_facturada(sesion)
    cuenta_id_2 = await _crear_cuenta_facturada(sesion)
    lote_id_1 = await _generar_y_validar_lote(
        sesion, cliente, token, cuenta_id_1, periodo=_PERIODO_ENVIO_SUSALUD
    )
    lote_id_2 = await _generar_y_validar_lote(
        sesion, cliente, token, cuenta_id_2, periodo=_PERIODO_ENVIO_SUSALUD
    )
    for lote_id in (lote_id_1, lote_id_2):
        remision = await cliente.post(
            f"/lotes/{lote_id}/remision-iafas", headers={"Authorization": f"Bearer {token}"}
        )
        assert remision.status_code == 201, remision.text

    primer_envio = await cliente.post(
        "/lotes/envio-susalud",
        json={"periodo": _PERIODO_ENVIO_SUSALUD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert primer_envio.status_code == 202, primer_envio.text
    assert primer_envio.json()["trabajo_id"] is not None

    async def _ambos_enviados() -> bool:
        for lote_id in (lote_id_1, lote_id_2):
            detalle = await cliente.get(
                f"/lotes/{lote_id}", headers={"Authorization": f"Bearer {token}"}
            )
            if detalle.json()["enviado_susalud_en"] is None:
                return False
        return True

    await esperar_hasta(_ambos_enviados, tiempo_limite_segundos=_TIMEOUT_MONITOREO_SEGUNDOS)

    # Duplicidad: un segundo envio del mismo periodo no vuelve a incluir
    # los lotes ya enviados -- no hay ningun lote VALIDADO sin enviar que
    # quede pendiente, asi que no encola trabajo nuevo.
    segundo_envio = await cliente.post(
        "/lotes/envio-susalud",
        json={"periodo": _PERIODO_ENVIO_SUSALUD},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert segundo_envio.status_code == 202, segundo_envio.text
    assert segundo_envio.json()["trabajo_id"] is None, (
        "El segundo envio no debio encolar nada: ambos lotes de este periodo ya estan enviados."
    )
