"""API del simulador del sistema hospitalario de la clinica: las atenciones ya
cerradas, que el sistema de cuentas medicas importa. Las rutas de datos exigen
la cabecera X-Clave-Api; la pagina de inicio y /salud no."""

from __future__ import annotations

import hmac
from html import escape
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import HTMLResponse

from app.datos import todas_las_atenciones


def _resumen(atencion: dict[str, Any]) -> dict[str, Any]:
    return {
        "atencion_id": atencion["atencion_id"],
        "tipo_atencion": atencion["tipo_atencion"],
        "fecha_prestacion": atencion["fecha_prestacion"],
        "paciente": atencion["paciente"],
        "iafas_codigo": atencion["iafas_codigo"],
    }


def _pagina(atenciones: list[dict[str, Any]]) -> str:
    filas = "".join(
        "<tr>"
        f"<td>{escape(a['atencion_id'])}</td>"
        f"<td>{escape(a['fecha_prestacion'])}</td>"
        f"<td>{escape(a['tipo_atencion'])}</td>"
        f"<td>{escape(a['paciente']['nombres'])} {escape(a['paciente']['apellidos'])}</td>"
        f"<td>{escape(a['iafas_codigo'])}</td>"
        "</tr>"
        for a in atenciones
    )
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        "<title>Sistema hospitalario (simulador)</title></head><body>"
        "<h1>Sistema hospitalario (simulador)</h1>"
        '<table border="1" cellpadding="4"><thead><tr><th>Codigo</th><th>Fecha</th>'
        "<th>Tipo</th><th>Paciente</th><th>Aseguradora</th></tr></thead>"
        f"<tbody>{filas}</tbody></table></body></html>"
    )


def construir_app(clave_api: str) -> FastAPI:
    app = FastAPI(title="Simulador del sistema hospitalario")

    def exigir_clave(x_clave_api: Annotated[str | None, Header()] = None) -> None:
        if not clave_api or x_clave_api is None:
            raise HTTPException(status_code=401, detail="Clave de API invalida")
        if not hmac.compare_digest(x_clave_api.encode(), clave_api.encode()):
            raise HTTPException(status_code=401, detail="Clave de API invalida")

    def buscar(atencion_id: str) -> dict[str, Any]:
        for atencion in todas_las_atenciones():
            if atencion["atencion_id"] == atencion_id:
                return atencion
        raise HTTPException(status_code=404, detail="Atencion no encontrada")

    @app.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def inicio() -> str:
        return _pagina(todas_las_atenciones())

    @app.get("/atenciones", dependencies=[Depends(exigir_clave)])
    def listar(documento: str | None = None) -> list[dict[str, Any]]:
        return [
            _resumen(a)
            for a in todas_las_atenciones()
            if documento is None or a["paciente"]["numero_documento"] == documento
        ]

    @app.get("/atenciones/{atencion_id}", dependencies=[Depends(exigir_clave)])
    def detalle(atencion_id: str) -> dict[str, Any]:
        return buscar(atencion_id)

    @app.get("/atenciones/{atencion_id}/exportar", dependencies=[Depends(exigir_clave)])
    def exportar(atencion_id: str) -> Response:
        import json

        atencion = buscar(atencion_id)
        return Response(
            content=json.dumps(atencion, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="atencion_{atencion_id}.json"'},
        )

    return app
