"""Verificacion diaria de la cadena de eventos (Seccion 6.2.2, RNF-18,
AD-11, control C-10): recorre cada agregado del almacen de eventos,
recalcula su cadena de valores resumen con clave (HMAC-SHA256) con la
misma logica de `cadena_eventos.py`, y la compara contra lo guardado.

Una ruptura significa que un evento fue alterado por fuera de la
aplicacion (el unico camino de escritura normal es `RegistroEventosSql`,
que siempre calcula el encadenamiento correcto) -- incluso por quien
administra el gestor de base de datos, que no tiene la clave fuera de
ella. Ante una ruptura, se alerta al jefe de cuentas medicas y al
administrador (RT-10, control C-15): en este prototipo, la alerta es un
registro en `reportes/alertas_integridad/`, no un envio real de correo o
SMS (fuera del alcance del proyecto).

Uso (desde sistema/backend/):
    uv run python herramientas/verificar_cadena_eventos.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import sqlalchemy as sa

from app.compartido.configuracion import obtener_configuracion
from app.compartido.rutas import raiz_reportes
from app.dominio.puertos_comunes import (
    TIPO_AGREGADO_CUENTA,
    TIPO_AGREGADO_LOTE,
    TIPO_AGREGADO_SESION_PLATAFORMA,
    TIPO_AGREGADO_SESION_USUARIO,
    Evento,
)
from app.infraestructura.persistencia.base import FabricaSesiones
from app.infraestructura.persistencia.cadena_eventos import (
    GENESIS,
    DatosEventoParaHash,
    calcular_hash_evento,
)
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql


async def _verificar() -> dict[str, object]:
    clave = obtener_configuracion().clave_hmac_eventos.encode("utf-8")
    rupturas: list[dict[str, object]] = []
    agregados_verificados = 0
    eventos_verificados = 0

    async with FabricaSesiones() as sesion:
        filas = (
            (
                await sesion.execute(
                    sa.text(
                        "SELECT evento_id, tipo_agregado, agregado_id, version, tipo_evento, "
                        "actor, estado_previo, estado_nuevo, ocurrido_en, hash_evento "
                        "FROM evento ORDER BY tipo_agregado, agregado_id, version"
                    )
                )
            )
            .mappings()
            .all()
        )

    ultimo_hash: dict[tuple[str, int], str] = {}
    agregados_vistos: set[tuple[str, int]] = set()
    for fila in filas:
        clave_agregado = (fila["tipo_agregado"], fila["agregado_id"])
        agregados_vistos.add(clave_agregado)
        hash_anterior = ultimo_hash.get(clave_agregado, GENESIS)
        hash_esperado = calcular_hash_evento(
            clave,
            hash_anterior,
            DatosEventoParaHash(
                tipo_agregado=fila["tipo_agregado"],
                agregado_id=fila["agregado_id"],
                version=fila["version"],
                tipo_evento=fila["tipo_evento"],
                actor=fila["actor"],
                estado_previo=fila["estado_previo"],
                estado_nuevo=fila["estado_nuevo"],
                ocurrido_en=fila["ocurrido_en"],
            ),
        )
        eventos_verificados += 1
        if hash_esperado != fila["hash_evento"]:
            rupturas.append(
                {
                    "evento_id": str(fila["evento_id"]),
                    "tipo_agregado": fila["tipo_agregado"],
                    "agregado_id": fila["agregado_id"],
                    "version": fila["version"],
                    "hash_guardado": fila["hash_evento"],
                    "hash_esperado": hash_esperado,
                }
            )
        # Independientemente de si este evento rompio la cadena, la
        # verificacion sigue encadenando desde el valor ESPERADO (no el
        # guardado): una sola alteracion se reporta una vez, no arrastra
        # un falso positivo en todos los eventos posteriores del agregado.
        ultimo_hash[clave_agregado] = hash_esperado

    agregados_verificados = len(agregados_vistos)
    return {
        "verificado_en": datetime.now(UTC).isoformat(timespec="seconds"),
        "agregados_verificados": agregados_verificados,
        "eventos_verificados": eventos_verificados,
        "cadena_integra": not rupturas,
        "rupturas": rupturas,
    }


def _alertar_si_hay_rupturas(resultado: dict[str, object]) -> None:
    rupturas = resultado["rupturas"]
    assert isinstance(rupturas, list)
    if not rupturas:
        return
    directorio = raiz_reportes() / "alertas_integridad"
    directorio.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ruta = directorio / f"ruptura_cadena_eventos_{marca}.json"
    ruta.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        f"ALERTA (RT-10, C-15): {len(rupturas)} ruptura(s) detectada(s) en la cadena de "
        f"eventos. Destinada al jefe de cuentas medicas y al administrador; registrada en {ruta}"
    )


# Campo de Evento que identifica cada tipo de agregado (Fase 24).
_CAMPO_AGREGADO = {
    TIPO_AGREGADO_CUENTA: "cuenta_medica_id",
    TIPO_AGREGADO_LOTE: "lote_id",
    TIPO_AGREGADO_SESION_USUARIO: "sesion_usuario_id",
    TIPO_AGREGADO_SESION_PLATAFORMA: "sesion_plataforma_id",
}


async def _registrar_eventos_de_ruptura(resultado: dict[str, object]) -> None:
    """Desde la verificacion de cumplimiento del 12 de noviembre: ademas
    del archivo de alerta, un evento RUPTURA_CADENA_DETECTADA en cada
    agregado roto, para que la alerta llegue a la bandeja de avisos del
    jefe y del administrador (RT-10, C-15) y no solo a un archivo. Se
    repite en cada verificacion mientras la ruptura siga ahi."""
    rupturas = resultado["rupturas"]
    assert isinstance(rupturas, list)
    por_agregado: dict[tuple[str, int], list[str]] = {}
    for ruptura in rupturas:
        clave = (str(ruptura["tipo_agregado"]), int(ruptura["agregado_id"]))
        por_agregado.setdefault(clave, []).append(str(ruptura["evento_id"]))
    if not por_agregado:
        return
    async with FabricaSesiones() as sesion:
        registro = RegistroEventosSql(sesion)
        for (tipo_agregado, agregado_id), evento_ids in por_agregado.items():
            campo = _CAMPO_AGREGADO.get(tipo_agregado)
            if campo is None:
                continue
            argumentos: dict[str, object] = {"cuenta_medica_id": None, campo: agregado_id}
            await registro.registrar(
                Evento(
                    tipo_evento="RUPTURA_CADENA_DETECTADA",
                    actor="temporizador_sistema",
                    estado_previo=None,
                    estado_nuevo=None,
                    datos={"origen": "verificacion_diaria", "eventos_alterados": evento_ids},
                    **argumentos,  # type: ignore[arg-type]
                )
            )
        await sesion.commit()


async def main() -> None:
    resultado = await _verificar()
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    _alertar_si_hay_rupturas(resultado)
    await _registrar_eventos_de_ruptura(resultado)

    directorio = raiz_reportes() / "verificaciones_cadena_eventos"
    directorio.mkdir(parents=True, exist_ok=True)
    marca = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    ruta = directorio / f"verificacion_{marca}.json"
    ruta.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nreporte de verificacion escrito en {ruta}")


if __name__ == "__main__":
    asyncio.run(main())
