"""Proteccion de los datos sensibles frente a usuarios no autorizados
(observacion del jurado sobre los controles C-02, C-08 y C-12).

Verifica, con los seis roles del sistema y sin credencial, tres cosas:

1. El detalle de la cuenta solo entrega el diagnostico, la historia
   clinica, los procedimientos y los productos dispensados a los roles
   que trabajan sobre la atencion (Ley N. 26842, art. 25); tesoreria
   recibe la cuenta con esos datos reservados, y el gerente y el
   administrador no la reciben.
2. Cada ruta que entrega datos de pacientes o de salud responde 403 a
   los roles que la matriz de permisos (Tabla 46) no autoriza.
3. Ninguna ruta de la interfaz de programacion entrega las evidencias
   del robot (capturas y trazas de la consulta de cobertura): solo se
   descifran con la herramienta del proceso de automatizacion, que deja
   el evento EVIDENCIA_DESCIFRADA en la cuenta."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, time
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.infraestructura.persistencia.modelos_cpms import CpmsVersionModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
    ProcedimientoFacturadoModelo,
)

_TODOS = tuple(NombreRol)
_CLINICOS = (NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE)
_SIN_DETALLE = (NombreRol.GERENTE, NombreRol.ADMINISTRADOR)

# Ruta que entrega datos de pacientes o de salud, y roles que la Tabla 46
# autoriza a consultarla.
_RUTAS_SENSIBLES: tuple[tuple[str, str, frozenset[NombreRol]], ...] = (
    ("GET", "/cuentas", frozenset({*_CLINICOS, NombreRol.TESORERIA})),
    ("GET", "/cuentas/1", frozenset({*_CLINICOS, NombreRol.TESORERIA})),
    ("GET", "/cuentas/1/acreditacion", frozenset(_CLINICOS)),
    ("GET", "/cuentas/1/historial", frozenset({NombreRol.JEFE})),
    ("POST", "/cuentas/1/expediente", frozenset({NombreRol.JEFE})),
    ("GET", "/lotes/1/cuentas", frozenset({NombreRol.ANALISTA, NombreRol.JEFE})),
    ("GET", "/lotes/1/archivo-s01", frozenset({NombreRol.ANALISTA, NombreRol.JEFE})),
    ("GET", "/lotes/1/historial", frozenset({NombreRol.JEFE})),
    (
        "GET",
        "/comunicaciones-iafas?cuenta_id=1",
        frozenset({*_CLINICOS, NombreRol.TESORERIA}),
    ),
)

_CASOS_RUTA_ROL = [
    pytest.param((metodo, ruta, rol, rol in autorizados), id=f"{metodo} {ruta} {rol.value}")
    for metodo, ruta, autorizados in _RUTAS_SENSIBLES
    for rol in _TODOS
]


async def _sembrar_cuenta_con_datos_clinicos(sesion: AsyncSession) -> int:
    iafas = IafasModelo(
        codigo="19395",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    ipress = IpressModelo(ruc="20123456789", codigo_ipress="12345678", razon_social="Clinica")
    version_cpms = CpmsVersionModelo(etiqueta="v1", archivos_origen=[], conteo=0)
    sesion.add_all([iafas, ipress, version_cpms])
    await sesion.flush()
    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento="12345678",
        nombres="Ana",
        apellidos="Perez",
        iafas_id=iafas.id,
        ficticio=True,
    )
    sesion.add(asegurado)
    await sesion.flush()
    cuenta = CuentaMedicaModelo(
        identificacion_interna="CTA0000001",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=date(2026, 9, 10),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica="00000001",
        diagnostico_principal_cie10="J18.9",
        estado="EN_AUDITORIA",
    )
    sesion.add(cuenta)
    await sesion.flush()
    sesion.add(
        ProcedimientoFacturadoModelo(
            cuenta_id=cuenta.id,
            descripcion_registrada="Consulta",
            codigo_asignado="99201",
            cpms_version_id=version_cpms.id,
            origen_codigo="coincidencia_exacta",
            cantidad=1,
            monto_unitario=Decimal("50.00"),
            fecha=date(2026, 9, 10),
        )
    )
    await sesion.commit()
    return cuenta.id


@pytest.mark.parametrize("rol", _CLINICOS)
async def prueba_roles_clinicos_ven_diagnostico_historia_y_procedimientos(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    rol: NombreRol,
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta_con_datos_clinicos(sesion)
    token = await token_para_rol(rol)

    respuesta = await cliente.get(
        f"/cuentas/{cuenta_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["datos_clinicos_reservados"] is False
    assert cuerpo["diagnostico_principal_cie10"] == "J18.9"
    assert cuerpo["numero_historia_clinica"] == "00000001"
    assert [p["codigo_asignado"] for p in cuerpo["procedimientos"]] == ["99201"]


async def prueba_tesoreria_recibe_la_cuenta_con_los_datos_clinicos_reservados(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta_con_datos_clinicos(sesion)
    token = await token_para_rol(NombreRol.TESORERIA)

    respuesta = await cliente.get(
        f"/cuentas/{cuenta_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["datos_clinicos_reservados"] is True
    assert cuerpo["diagnostico_principal_cie10"] is None
    assert cuerpo["numero_historia_clinica"] is None
    assert cuerpo["procedimientos"] == []
    assert cuerpo["productos"] == []
    assert cuerpo["identificacion_interna"] == "CTA0000001"
    assert "J18.9" not in respuesta.text


@pytest.mark.parametrize("rol", _SIN_DETALLE)
async def prueba_gerente_y_administrador_no_reciben_el_detalle_de_la_cuenta(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    rol: NombreRol,
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta_id = await _sembrar_cuenta_con_datos_clinicos(sesion)
    token = await token_para_rol(rol)

    respuesta = await cliente.get(
        f"/cuentas/{cuenta_id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert respuesta.status_code == 403
    assert "J18.9" not in respuesta.text


@pytest.mark.parametrize("caso", _CASOS_RUTA_ROL)
async def prueba_ruta_sensible_solo_responde_a_los_roles_autorizados(
    cliente: AsyncClient,
    token_para_rol: Callable[[NombreRol], Awaitable[str]],
    caso: tuple[str, str, NombreRol, bool],
) -> None:
    metodo, ruta, rol, autorizado = caso
    token = await token_para_rol(rol)
    cuerpo = {"motivo": "Revision de auditoria"} if metodo == "POST" else None

    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )

    if autorizado:
        assert respuesta.status_code not in (401, 403)
    else:
        assert respuesta.status_code == 403


@pytest.mark.parametrize("metodo,ruta", [(m, r) for m, r, _ in _RUTAS_SENSIBLES])
async def prueba_ruta_sensible_sin_credencial_responde_401(
    cliente: AsyncClient, metodo: str, ruta: str
) -> None:
    respuesta = await cliente.request(metodo, ruta)
    assert respuesta.status_code == 401


def prueba_ninguna_ruta_entrega_las_evidencias_del_robot() -> None:
    from app.api.main import app

    rutas = [getattr(ruta, "path", "") for ruta in app.routes]
    assert rutas
    assert not [ruta for ruta in rutas if "evidencia" in ruta.lower()]
