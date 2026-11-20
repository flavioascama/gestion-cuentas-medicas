"""Importacion de la atencion por las rutas HTTP, contra SQLite en memoria
(2026-11-19): por archivo y por consulta, atencion repetida, sistema
hospitalario caido, procedimientos por codificar, copago cobrado, detalle
de la cuenta y comprobante de una hospitalizacion sin carta."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.main import app
from app.api.rutas_atenciones_hospitalarias import obtener_fuente_atenciones
from app.dominio.acceso.entidades import NombreRol
from app.dominio.integracion.atencion_hospitalaria import (
    AtencionHospitalaria,
    ErrorSistemaHospitalarioNoDisponible,
    ResumenAtencionHospitalaria,
)
from app.infraestructura.persistencia.modelos_catalogo_gtin import (
    CatalogoGtinProductoModelo,
    CatalogoGtinVersionModelo,
)
from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo, Cie10VersionModelo
from app.infraestructura.persistencia.modelos_cpms import (
    CpmsProcedimientoModelo,
    CpmsVersionModelo,
)
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.sistema_hospitalario.esquema_atencion import AtencionJson

GTIN = "7750000000017"
Token = Callable[[NombreRol], Awaitable[str]]


def atencion_json(**cambios: Any) -> dict[str, Any]:
    datos: dict[str, Any] = {
        "atencion_id": "AT-2026-000123",
        "tipo_atencion": "AMBULATORIA",
        "fecha_prestacion": "2026-11-18",
        "hora_prestacion": "10:30:00",
        "numero_historia_clinica": "00045871",
        "paciente": {
            "tipo_documento": "1",
            "numero_documento": "81953443",
            "nombres": "Elvira",
            "apellidos": "Ochoa",
        },
        "iafas_codigo": "20001",
        "profesional": {"numero_colegiatura": "045871", "nombres": "Luis Paredes Soto"},
        "diagnostico_principal_cie10": "A072",
        "diagnosticos_secundarios_cie10": ["E119"],
        "hospitalizacion": None,
        "procedimientos": [
            {
                "descripcion": "hemograma completo",
                "area": "LABORATORIO",
                "cantidad": 1,
                "monto_unitario": "35.00",
                "fecha": "2026-11-18",
            }
        ],
        "farmacia": [
            {
                "codigo_producto": GTIN,
                "cantidad": "2",
                "tipo_unidad_dispensacion": "1",
                "monto_unitario": "12.50",
                "fecha_dispensacion": "2026-11-18",
            }
        ],
        "copago_cobrado": {"monto": "20.00", "referencia": "REC-001", "fecha": "2026-11-18"},
    }
    datos.update(cambios)
    return datos


async def _sembrar(sesion: AsyncSession) -> None:
    cie10 = Cie10VersionModelo(ruta_origen="x", huella_sha256="0" * 64, conteo=2)
    gtin = CatalogoGtinVersionModelo(ruta_origen="x")
    cpms = CpmsVersionModelo(etiqueta="v1", archivos_origen=[], conteo=1)
    sesion.add_all(
        [
            IafasModelo(
                codigo="20001",
                razon_social="IAFAS",
                periodicidad_remision_dias=7,
                ventana_monitoreo_horas=48,
            ),
            IpressModelo(ruc="20123456789", codigo_ipress="12345678", razon_social="Clinica"),
            cie10,
            gtin,
            cpms,
        ]
    )
    await sesion.flush()
    sesion.add_all(
        [
            Cie10CodigoModelo(cie10_version_id=cie10.id, codigo="A072", descripcion="a"),
            Cie10CodigoModelo(cie10_version_id=cie10.id, codigo="E119", descripcion="b"),
            CatalogoGtinProductoModelo(
                version_id=gtin.id,
                codigo=GTIN,
                tipo_codigo="GTIN-13",
                tipo_producto_catalogo="PRODUCTO FARMACEUTICO",
                tipo_producto_tedef="M",
                nombre="Paracetamol",
                denominacion_comun="paracetamol",
                captura="c",
                fila=1,
            ),
            CpmsProcedimientoModelo(
                cpms_version_id=cpms.id,
                codigo_grupo="1",
                nombre_grupo="g",
                codigo_seccion="1.5",
                nombre_seccion="s",
                codigo_subseccion="1.5.2",
                nombre_subseccion="Hematologia",
                codigo_procedimiento="85025",
                denominacion_procedimiento="Hemograma completo",
            ),
        ]
    )
    await sesion.commit()


async def _cabeceras(token_para_rol: Token, rol: NombreRol) -> dict[str, str]:
    return {"Authorization": f"Bearer {await token_para_rol(rol)}"}


@pytest.fixture
async def base(fabrica_sesiones: async_sessionmaker[AsyncSession]) -> None:
    async with fabrica_sesiones() as sesion:
        await _sembrar(sesion)


async def _importar(cliente: AsyncClient, cabeceras: dict[str, str], **cambios: Any) -> Any:
    return await cliente.post("/cuentas/importar", json=atencion_json(**cambios), headers=cabeceras)


async def prueba_importa_por_archivo_con_lo_que_trae_la_atencion(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)

    respuesta = await _importar(cliente, analista)

    assert respuesta.status_code == 201, respuesta.text
    cuenta_id = respuesta.json()["cuenta_id"]
    detalle = (await cliente.get(f"/cuentas/{cuenta_id}", headers=analista)).json()
    assert detalle["estado"] == "REGISTRADA"
    assert detalle["numero_historia_clinica"] == "00045871"
    assert detalle["tipo_atencion"] == "AMBULATORIA"
    assert detalle["atencion_origen_id"] == "AT-2026-000123"
    assert (detalle["nombre_medico"], detalle["colegiatura_medico"]) == (
        "Luis Paredes Soto",
        "045871",
    )
    assert detalle["diagnosticos_secundarios_cie10"] == ["E119"]
    assert detalle["procedimientos"] == []
    assert [p["codigo_producto"] for p in detalle["productos"]] == [GTIN]
    pendientes = (
        await cliente.get(f"/cuentas/{cuenta_id}/procedimientos-por-codificar", headers=analista)
    ).json()
    assert [(p["descripcion"], p["area"], p["monto_unitario"]) for p in pendientes] == [
        ("hemograma completo", "LABORATORIO", "35.00")
    ]
    copago = (await cliente.get(f"/cuentas/{cuenta_id}/copago-cobrado", headers=analista)).json()
    assert (copago["monto"], copago["origen"]) == ("20.00", "sistema_hospitalario")


async def prueba_atencion_repetida_responde_409_con_la_cuenta_existente(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    cuenta_id = (await _importar(cliente, analista)).json()["cuenta_id"]

    respuesta = await _importar(cliente, analista)

    assert respuesta.status_code == 409
    assert respuesta.json()["codigo"] == "ATENCION_YA_IMPORTADA"
    assert respuesta.json()["detalles"] == {"cuenta_id": cuenta_id}


async def prueba_aseguradora_desconocida_responde_422_sin_crear_la_cuenta(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)

    respuesta = await _importar(cliente, analista, iafas_codigo="99999")

    assert respuesta.status_code == 422
    assert respuesta.json()["codigo"] == "IAFAS_DESCONOCIDA"
    assert (await cliente.get("/cuentas", headers=analista)).json() == []


class _FuenteFalsa:
    def __init__(self, caida: bool = False) -> None:
        self._caida = caida

    async def listar(self, documento: str | None) -> list[ResumenAtencionHospitalaria]:
        if self._caida:
            raise ErrorSistemaHospitalarioNoDisponible("El sistema hospitalario no responde.")
        atencion = await self.obtener("AT-2026-000123")
        assert atencion is not None
        return [
            ResumenAtencionHospitalaria(
                atencion.atencion_id,
                "AMBULATORIA",
                atencion.fecha_prestacion,
                atencion.paciente,
                "20001",
            )
        ]

    async def obtener(self, atencion_id: str) -> AtencionHospitalaria | None:
        if self._caida:
            raise ErrorSistemaHospitalarioNoDisponible("El sistema hospitalario no responde.")
        return AtencionJson.model_validate(atencion_json()).a_valor()


async def prueba_importa_por_consulta_y_la_lista_ya_no_la_muestra(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    app.dependency_overrides[obtener_fuente_atenciones] = lambda: _FuenteFalsa()
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    antes = (await cliente.get("/atenciones-hospitalarias", headers=analista)).json()

    respuesta = await cliente.post(
        "/atenciones-hospitalarias/AT-2026-000123/importar", headers=analista
    )
    despues = (await cliente.get("/atenciones-hospitalarias", headers=analista)).json()

    assert [a["atencion_id"] for a in antes] == ["AT-2026-000123"]
    assert respuesta.status_code == 201
    assert despues == []


async def prueba_sistema_hospitalario_caido_responde_503(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    app.dependency_overrides[obtener_fuente_atenciones] = lambda: _FuenteFalsa(caida=True)
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)

    lista = await cliente.get("/atenciones-hospitalarias", headers=analista)
    importacion = await cliente.post("/atenciones-hospitalarias/AT-1/importar", headers=analista)

    assert lista.status_code == importacion.status_code == 503
    assert importacion.json()["codigo"] == "SISTEMA_HOSPITALARIO_NO_DISPONIBLE"


async def prueba_solo_el_analista_importa(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    auditor = await _cabeceras(token_para_rol, NombreRol.AUDITOR)

    assert (await _importar(cliente, auditor)).status_code == 403


async def _acreditar(fabrica: async_sessionmaker[AsyncSession], cuenta_id: int) -> None:
    async with fabrica() as sesion:
        sesion.add(
            AcreditacionModelo(
                cuenta_id=cuenta_id,
                condicion_cobertura="ACREDITABLE",
                codigo_autorizacion="AUT1",
                tipo_documento_autorizacion="01",
                codigo_asegurado="AS1",
                tipo_afiliacion="1",
                instante=datetime.now(UTC),
                componente_ejecutor="prueba",
            )
        )
        await sesion.commit()


async def prueba_codificar_el_pendiente_y_exigir_la_carta_de_la_hospitalizacion(
    base: None,
    cliente: AsyncClient,
    token_para_rol: Token,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    auditor = await _cabeceras(token_para_rol, NombreRol.AUDITOR)
    hospitalizacion = {"fecha_ingreso": "2026-11-18", "fecha_alta": "2026-11-20"}
    cuenta_id = (
        await _importar(
            cliente, analista, tipo_atencion="HOSPITALIZACION", hospitalizacion=hospitalizacion
        )
    ).json()["cuenta_id"]
    await _acreditar(fabrica_sesiones, cuenta_id)
    pendiente = (
        await cliente.get(f"/cuentas/{cuenta_id}/procedimientos-por-codificar", headers=auditor)
    ).json()[0]
    completitud = (await cliente.get(f"/cuentas/{cuenta_id}/completitud", headers=analista)).json()
    piezas = {p["clave"]: p["completa"] for p in completitud["piezas"]}
    assert (piezas["codificacion"], piezas["cobertura"]) == (False, False)

    confirmado = await cliente.post(
        f"/cuentas/{cuenta_id}/procedimientos",
        json={
            "descripcion_registrada": "Hemograma completo",
            "codigo_elegido": "85025",
            "cantidad": 1,
            "monto_unitario": "35.00",
            "fecha": str(date(2026, 11, 18)),
            "inicio_sugerencia": datetime.now(UTC).isoformat(),
            "procedimiento_por_codificar_id": pendiente["id"],
        },
        headers=auditor,
    )
    comprobante = await cliente.post(f"/cuentas/{cuenta_id}/comprobante", headers=analista)
    completitud = (await cliente.get(f"/cuentas/{cuenta_id}/completitud", headers=analista)).json()
    piezas = {p["clave"]: p["completa"] for p in completitud["piezas"]}

    assert confirmado.status_code == 201, confirmado.text
    assert (
        await cliente.get(f"/cuentas/{cuenta_id}/procedimientos-por-codificar", headers=auditor)
    ).json() == []
    assert (piezas["codificacion"], piezas["cobertura"]) == (True, False)
    assert comprobante.status_code == 409
    assert "la carta de garantía de la hospitalización" in comprobante.json()["mensaje"]


async def prueba_tesoreria_no_ve_al_medico_ni_los_diagnosticos(
    base: None, cliente: AsyncClient, token_para_rol: Token
) -> None:
    analista = await _cabeceras(token_para_rol, NombreRol.ANALISTA)
    tesoreria = await _cabeceras(token_para_rol, NombreRol.TESORERIA)
    cuenta_id = (await _importar(cliente, analista)).json()["cuenta_id"]

    detalle = (await cliente.get(f"/cuentas/{cuenta_id}", headers=tesoreria)).json()
    pendientes = await cliente.get(
        f"/cuentas/{cuenta_id}/procedimientos-por-codificar", headers=tesoreria
    )

    assert detalle["tipo_atencion"] == "AMBULATORIA"
    assert detalle["nombre_medico"] is None
    assert detalle["colegiatura_medico"] is None
    assert detalle["diagnosticos_secundarios_cie10"] == []
    assert pendientes.status_code == 403
