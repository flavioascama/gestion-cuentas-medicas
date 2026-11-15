"""Anclaje diario de la cadena de eventos (Seccion 6.2.2, RNF-18, AD-11):
"el ultimo valor resumen de cada dia se ancla fuera de la base". Pensado
para correr una vez al dia (fuera del alcance de este prototipo un
programador de tareas real; ver docs/PENDIENTES.md).

El ancla es un unico valor: el HMAC-SHA256, con la misma clave fuera de la
base que firma los eventos, de la concatenacion ordenada del ultimo
hash_evento de cada agregado. Queda escrito en un archivo fuera de la base
de datos (`reportes/anclas_cadena_eventos/`), nunca en una tabla: un
atacante con privilegios sobre el gestor de base de datos no puede
alcanzarlo. `verificar_cadena_eventos.py` recalcula la cadena completa de
forma independiente; este anclaje es la referencia externa con la que esa
verificacion, o una auditoria posterior, puede confirmar que ademas nadie
sustituyo la cadena entera por una nueva igual de consistente consigo
misma.

Uso (desde sistema/backend/):
    uv run python herramientas/anclar_cadena_eventos.py
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, date, datetime

import sqlalchemy as sa

from app.compartido.configuracion import obtener_configuracion
from app.compartido.rutas import raiz_reportes
from app.infraestructura.persistencia.base import FabricaSesiones


async def _ultimo_hash_por_agregado() -> dict[str, str]:
    async with FabricaSesiones() as sesion:
        filas = (
            (
                await sesion.execute(
                    sa.text(
                        "SELECT DISTINCT ON (tipo_agregado, agregado_id) "
                        "tipo_agregado, agregado_id, hash_evento "
                        "FROM evento "
                        "ORDER BY tipo_agregado, agregado_id, version DESC"
                    )
                )
            )
            .mappings()
            .all()
        )
    return {f"{f['tipo_agregado']}:{f['agregado_id']}": f["hash_evento"] for f in filas}


def _calcular_ancla(clave: bytes, ultimos_hashes: dict[str, str]) -> str:
    contenido = "|".join(
        f"{agregado}={hash_}" for agregado, hash_ in sorted(ultimos_hashes.items())
    )
    return hmac.new(clave, contenido.encode(), hashlib.sha256).hexdigest()


async def main() -> None:
    clave = obtener_configuracion().clave_hmac_eventos.encode("utf-8")
    ultimos_hashes = await _ultimo_hash_por_agregado()
    ancla = _calcular_ancla(clave, ultimos_hashes)

    reporte = {
        "fecha": date.today().isoformat(),
        "anclado_en": datetime.now(UTC).isoformat(timespec="seconds"),
        "agregados_anclados": len(ultimos_hashes),
        "ancla": ancla,
        "ultimos_hashes_por_agregado": ultimos_hashes,
    }

    directorio = raiz_reportes() / "anclas_cadena_eventos"
    directorio.mkdir(parents=True, exist_ok=True)
    ruta = directorio / f"ancla_{date.today().isoformat()}.json"
    ruta.write_text(json.dumps(reporte, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"ancla del dia: {ancla}")
    print(f"{len(ultimos_hashes)} agregados anclados; reporte en {ruta}")


if __name__ == "__main__":
    asyncio.run(main())
