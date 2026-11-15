"""Escenarios 1, 2, 3 y 4 de la Seccion 14.2 del plan v3 (Integracion,
stack completo con los tres simuladores): Ingreso asistido, CAPTCHA
erroneo, Sesion vencida, Consulta de cobertura.

Requiere el stack completo levantado -- postgres, backend, trabajador,
acredita-salud (con SIMULADOR_MODO_PRUEBA=true) -- y corre aparte de la
suite rapida:
    docker compose exec backend uv run pytest \\
        pruebas_integracion/prueba_sesion_asistida_y_cobertura.py -q

Las cuatro funciones de prueba dependen del estado que deja la anterior
(mismo estilo que la verificacion manual de las Fases 15/16 documentada
en docs/DECISIONES.md) y por eso deben correr en el orden en que estan
escritas -- pytest, por defecto, ejecuta un modulo en orden de
definicion. Cada una limpia explicitamente el estado de
`sesion_plataforma` que necesita, en vez de asumirlo, para poder
reejecutar la suite completa mas de una vez sobre el mismo Postgres."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, time, timedelta

import httpx
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IpressModelo,
    TrabajoModelo,
)
from app.infraestructura.persistencia.modelos_plataformas import SesionPlataformaModelo
from pruebas_integracion.conftest import esperar_hasta

_PLATAFORMA = "acredita_salud"
_URL_ACREDITA_SALUD = "http://acredita-salud:8000"
_TokenParaRol = Callable[[NombreRol], Awaitable[str]]
_TIMEOUT_INGRESO_SEGUNDOS = 30.0
_TIMEOUT_COBERTURA_SEGUNDOS = 60.0
_TIPO_TRABAJO_INICIAR_SESION = "INICIAR_SESION_PLATAFORMA"


async def _limpiar_sesiones_previas(sesion: AsyncSession) -> None:
    """`sesion_plataforma` no es inmutable (a diferencia de `evento`):
    partir de cero en cada corrida de la suite es mas simple y mas fiel
    a "solo puede haber una sesion en curso por plataforma" que tratar
    de adivinar en que estado la dejo una corrida anterior.

    Si una corrida previa de esta misma suite quedo interrumpida a mitad
    del intercambio de CAPTCHA, el trabajador puede seguir con un ciclo
    Playwright en curso para una `sesion_id` que esta a punto de
    borrarse -- `_esperar_respuesta_humana` (robot_sesion_plataforma.py)
    simplemente no la encuentra y agota su propio tiempo limite antes de
    continuar (`ErrorSesionFallida`, que ya no se reintenta sola gracias
    al fix de `manejadores.py::manejar_error` de esta misma fase, pero
    ese ciclo Playwright en curso no se puede cancelar desde aqui). Esta
    limpieza marca ese trabajo como AGOTADO para que la BD no quede con
    un EN_PROCESO fantasma."""

    await sesion.execute(
        sa.update(TrabajoModelo)
        .where(
            TrabajoModelo.tipo == _TIPO_TRABAJO_INICIAR_SESION,
            TrabajoModelo.estado.in_(("PENDIENTE", "EN_PROCESO")),
            sa.cast(TrabajoModelo.carga_util["plataforma"].as_string(), sa.String) == _PLATAFORMA,
        )
        .values(estado="AGOTADO", error="Descartado por limpieza de pruebas_integracion (Fase 20).")
    )
    await sesion.execute(
        sa.delete(SesionPlataformaModelo).where(SesionPlataformaModelo.plataforma == _PLATAFORMA)
    )
    await sesion.commit()


async def _texto_captcha_vigente() -> str:
    async with httpx.AsyncClient(base_url=_URL_ACREDITA_SALUD, timeout=5.0) as cliente:
        respuesta = await cliente.get("/admin/captcha")
        assert respuesta.status_code == 200, respuesta.text
        return respuesta.text


async def _texto_captcha_garantizadamente_incorrecto() -> str:
    """El alfabeto del simulador (Pillow, Seccion 9.1) es aleatorio de
    verdad (`secrets.choice`): un texto fijo como "ZZZZZ" *puede*
    coincidir por azar con el desafio real (1 en ~33 millones, pero ya
    se observo en la practica en dos corridas de esta misma suite -- la
    generacion de datos sinteticos de este proyecto usa semillas fijas
    en otros lugares, pero el CAPTCHA no; el riesgo es real, no teorico,
    y una prueba de "CAPTCHA erroneo" que a veces tiene exito por
    casualidad no demuestra nada). Se lee el texto vigente y se responde
    con cualquier otro candidato conocido, nunca ese mismo."""

    real = await _texto_captcha_vigente()
    return "ZZZZZ" if real != "ZZZZZ" else "AAAAA"


async def _sesion_por_id(cliente: AsyncClient, token: str, sesion_id: int) -> dict[str, object]:
    respuesta = await cliente.get(
        "/plataformas/sesiones",
        params={"plataforma": _PLATAFORMA},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert respuesta.status_code == 200, respuesta.text
    (fila,) = (f for f in respuesta.json() if f["id"] == sesion_id)
    return fila  # type: ignore[no-any-return]


async def _solicitar_sesion(cliente: AsyncClient, token: str) -> int:
    respuesta = await cliente.post(
        f"/plataformas/{_PLATAFORMA}/sesion", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 202, respuesta.text
    return int(respuesta.json()["sesion_id"])


async def _responder_captcha(
    cliente: AsyncClient, token: str, sesion_id: int, respuesta_texto: str
) -> httpx.Response:
    return await cliente.post(
        f"/plataformas/sesiones/{sesion_id}/captcha",
        json={"respuesta": respuesta_texto},
        headers={"Authorization": f"Bearer {token}"},
    )


async def _crear_cuenta_registrada_sin_acreditar(sesion: AsyncSession) -> int:
    """Mismo patron que herramientas/solicitar_verificacion_cobertura_ejemplo.py:
    reutiliza un asegurado/IPRESS ya cargados, pero crea una cuenta NUEVA
    en REGISTRADA para que VerificarCobertura tenga algo real que encolar."""

    asegurado = (
        await sesion.execute(sa.select(AseguradoModelo).order_by(AseguradoModelo.id).limit(1))
    ).scalar_one()
    ipress = (
        await sesion.execute(sa.select(IpressModelo).order_by(IpressModelo.id).limit(1))
    ).scalar_one()
    # identificacion_interna es VARCHAR(10) y numero_historia_clinica es
    # VARCHAR(8) (Seccion 6.1): un identificador de 7 digitos cabe en
    # ambos con el prefijo "INT" (10 caracteres exactos).
    identificador_unico = f"{uuid.uuid4().int % 10_000_000:07d}"
    cuenta = CuentaMedicaModelo(
        identificacion_interna=f"INT{identificador_unico}",
        asegurado_id=asegurado.id,
        iafas_id=asegurado.iafas_id,
        ipress_id=ipress.id,
        fecha_prestacion=date.today(),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica=identificador_unico,
        estado="REGISTRADA",
    )
    sesion.add(cuenta)
    await sesion.commit()
    return cuenta.id


async def prueba_1_ingreso_asistido_deja_la_sesion_activa(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    await _limpiar_sesiones_previas(sesion)
    token = await token_para_rol(NombreRol.ANALISTA)

    sesion_id = await _solicitar_sesion(cliente, token)

    async def _esta_esperando_captcha() -> bool:
        fila = await _sesion_por_id(cliente, token, sesion_id)
        return bool(fila["estado"] == "ESPERANDO_CAPTCHA")

    await esperar_hasta(_esta_esperando_captcha, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)

    texto = await _texto_captcha_vigente()
    respuesta = await _responder_captcha(cliente, token, sesion_id, texto)
    assert respuesta.status_code == 204, respuesta.text

    async def _esta_activa() -> dict[str, object] | None:
        fila = await _sesion_por_id(cliente, token, sesion_id)
        return fila if fila["estado"] == "ACTIVA" else None

    fila_activa = await esperar_hasta(
        _esta_activa, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS
    )
    assert fila_activa["activa_desde"] is not None
    assert fila_activa["expira_en"] is not None


async def prueba_2_consulta_de_cobertura_reutiliza_la_sesion_activa(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "Consulta de cobertura": menos de 60 segundos con sesion
    vigente, y el robot la reutiliza sin iniciar sesion por su cuenta
    (Seccion 8.5) -- depende de que la prueba anterior haya dejado la
    sesion ACTIVA."""

    token = await token_para_rol(NombreRol.ANALISTA)
    cuenta_id = await _crear_cuenta_registrada_sin_acreditar(sesion)

    inicio = datetime.now(UTC)
    respuesta = await cliente.post(
        f"/cuentas/{cuenta_id}/cobertura", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 202, respuesta.text
    trabajo_id = respuesta.json()["trabajo_id"]

    async def _trabajo_completado() -> bool:
        detalle = await cliente.get(
            f"/trabajos/{trabajo_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert detalle.status_code == 200, detalle.text
        estado = detalle.json()["estado"]
        assert estado != "REQUIERE_SESION", (
            "El trabajo quedo esperando sesion pese a que la prueba anterior dejo una activa."
        )
        return bool(estado == "COMPLETADO")

    await esperar_hasta(_trabajo_completado, tiempo_limite_segundos=_TIMEOUT_COBERTURA_SEGUNDOS)
    duracion = datetime.now(UTC) - inicio
    assert duracion < timedelta(seconds=60), f"La consulta tardo {duracion}, se exige menos de 60s."


async def prueba_3_captcha_erroneo_tres_veces_deja_la_sesion_fallida(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "CAPTCHA erroneo": se refresca y reintenta; al tercer
    fallo la sesion queda FALLIDA. Cierra primero la sesion ACTIVA que
    dejaron las pruebas anteriores -- SolicitarSesionPlataforma es
    idempotente mientras haya una ACTIVA vigente (Seccion 8.4)."""

    await sesion.execute(
        sa.update(SesionPlataformaModelo)
        .where(
            SesionPlataformaModelo.plataforma == _PLATAFORMA,
            SesionPlataformaModelo.estado == "ACTIVA",
        )
        .values(estado="CERRADA")
    )
    await sesion.commit()

    token = await token_para_rol(NombreRol.ANALISTA)
    sesion_id = await _solicitar_sesion(cliente, token)

    # Responder "en el mismo ciclo de polling" en el que se detecta un
    # `intentos` nuevo con ESPERANDO_CAPTCHA -- no en dos pasos separados
    # (esperar primero, responder despues): entre esos dos pasos el robot
    # puede llegar a generar otro desafio mas (el boton "Refrescar
    # Imagen" del simulador recarga /ingreso completo, Seccion 9.1, no
    # solo la imagen), y una respuesta calculada para el desafio leido en
    # el paso de espera ya no correspondería al que el robot esta
    # verificando en el paso de responder.
    intentos_ya_respondidos: set[int] = set()

    async def _avanzar_un_paso() -> dict[str, object] | None:
        fila = await _sesion_por_id(cliente, token, sesion_id)
        if fila["estado"] in ("ACTIVA", "FALLIDA"):
            return fila
        if (
            fila["estado"] == "ESPERANDO_CAPTCHA"
            and fila["intentos"] not in intentos_ya_respondidos
        ):
            intentos_ya_respondidos.add(fila["intentos"])  # type: ignore[arg-type]
            respuesta_incorrecta = await _texto_captcha_garantizadamente_incorrecto()
            respuesta = await _responder_captcha(cliente, token, sesion_id, respuesta_incorrecta)
            assert respuesta.status_code == 204, respuesta.text
        return None

    fila_final = await esperar_hasta(
        _avanzar_un_paso, tiempo_limite_segundos=3 * _TIMEOUT_INGRESO_SEGUNDOS
    )
    assert fila_final["estado"] == "FALLIDA", (
        f"Se esperaban 3 fallos de CAPTCHA consecutivos; la sesion quedo {fila_final!r}."
    )
    assert fila_final["motivo"] is not None
    assert len(intentos_ya_respondidos) == 3, intentos_ya_respondidos


async def prueba_4_sesion_vencida_reanuda_el_trabajo_al_activar_una_nueva(
    sesion: AsyncSession, cliente: AsyncClient, token_para_rol: _TokenParaRol
) -> None:
    """Escenario "Sesion vencida": los trabajos pasan a REQUIERE_SESION y
    se reanudan al activar una sesion nueva.

    El robot de acreditacion (Seccion 8.5) no consulta
    `sesion_plataforma.expira_en` en absoluto: usa el `storage_state`
    (cookies) guardado y solo se entera de que ya no sirve si el propio
    simulador lo rechaza al navegar a /menu (`_verificar_sesion_vigente`,
    robot_acreditacion.py). Forzar `expira_en` al pasado en la BD del
    backend no alcanza para reproducir esto -- las cookies reales del
    simulador siguen viviendo sus propios
    `SESION_EXPIRACION_MINUTOS` (30 por defecto), sin relacion con esa
    columna. El modo de falla `expiracion_sesion` del simulador (Seccion
    9.1, ya usado por `simuladores/acredita_salud/pruebas/prueba_falla_inducida.py`)
    fuerza el rechazo de cualquier cookie sin esperar ese tiempo real."""

    token = await token_para_rol(NombreRol.ANALISTA)
    sesion_id_inicial = await _solicitar_sesion(cliente, token)

    async def _esta_esperando_captcha() -> bool:
        fila = await _sesion_por_id(cliente, token, sesion_id_inicial)
        return bool(fila["estado"] == "ESPERANDO_CAPTCHA")

    await esperar_hasta(_esta_esperando_captcha, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)
    texto = await _texto_captcha_vigente()
    await _responder_captcha(cliente, token, sesion_id_inicial, texto)

    async def _esta_activa() -> bool:
        fila = await _sesion_por_id(cliente, token, sesion_id_inicial)
        return bool(fila["estado"] == "ACTIVA")

    await esperar_hasta(_esta_activa, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)

    # 1. La sesion real (cookies) queda invalida de inmediato en el
    #    simulador, sin esperar su vencimiento real.
    async with httpx.AsyncClient(base_url=_URL_ACREDITA_SALUD, timeout=5.0) as cliente_simulador:
        activar_falla = await cliente_simulador.post(
            "/admin/falla", data={"modo": "expiracion_sesion"}
        )
        assert activar_falla.status_code == 200, activar_falla.text

    # 2. La fila de sesion_plataforma tambien deja de ser ACTIVA para el
    #    backend, para que SolicitarSesionPlataforma (mas abajo) no la
    #    reutilice por idempotencia y cree una solicitud nueva de verdad.
    await sesion.execute(
        sa.update(SesionPlataformaModelo)
        .where(SesionPlataformaModelo.id == sesion_id_inicial)
        .values(estado="EXPIRADA")
    )
    await sesion.commit()

    cuenta_id = await _crear_cuenta_registrada_sin_acreditar(sesion)
    respuesta = await cliente.post(
        f"/cuentas/{cuenta_id}/cobertura", headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 202, respuesta.text
    trabajo_id = respuesta.json()["trabajo_id"]

    async def _trabajo_requiere_sesion() -> bool:
        detalle = await cliente.get(
            f"/trabajos/{trabajo_id}", headers={"Authorization": f"Bearer {token}"}
        )
        return bool(detalle.json()["estado"] == "REQUIERE_SESION")

    await esperar_hasta(_trabajo_requiere_sesion, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)

    # 3. Se restablece el simulador antes del segundo ingreso: con el
    #    modo de falla todavia activo, ni siquiera un login nuevo entraria.
    async with httpx.AsyncClient(base_url=_URL_ACREDITA_SALUD, timeout=5.0) as cliente_simulador:
        restaurar_falla = await cliente_simulador.post("/admin/falla", data={"modo": "ninguno"})
        assert restaurar_falla.status_code == 200, restaurar_falla.text

    nueva_sesion_id = await _solicitar_sesion(cliente, token)
    assert nueva_sesion_id != sesion_id_inicial, (
        "SolicitarSesionPlataforma debio crear una nueva solicitud: la anterior ya "
        "esta EXPIRADA, no ACTIVA."
    )

    async def _nueva_esperando_captcha() -> bool:
        fila = await _sesion_por_id(cliente, token, nueva_sesion_id)
        return bool(fila["estado"] == "ESPERANDO_CAPTCHA")

    await esperar_hasta(_nueva_esperando_captcha, tiempo_limite_segundos=_TIMEOUT_INGRESO_SEGUNDOS)
    texto_nuevo = await _texto_captcha_vigente()
    await _responder_captcha(cliente, token, nueva_sesion_id, texto_nuevo)

    async def _trabajo_completado_tras_reanudar() -> bool:
        detalle = await cliente.get(
            f"/trabajos/{trabajo_id}", headers={"Authorization": f"Bearer {token}"}
        )
        return bool(detalle.json()["estado"] == "COMPLETADO")

    await esperar_hasta(
        _trabajo_completado_tras_reanudar, tiempo_limite_segundos=_TIMEOUT_COBERTURA_SEGUNDOS
    )
