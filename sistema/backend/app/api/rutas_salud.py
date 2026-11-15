"""Ruta publica de verificacion de salud. Entregable minimo de la Fase 1."""

from __future__ import annotations

from fastapi import APIRouter

from app.infraestructura.observabilidad.registro import obtener_registrador

router = APIRouter(tags=["salud"])
_registrador = obtener_registrador("api.salud")


@router.get("/salud")
async def verificar_salud() -> dict[str, str]:
    _registrador.info(
        "verificacion_salud", caso_uso="verificar_salud", actor="anonimo", estado="ok"
    )
    return {"estado": "ok"}
