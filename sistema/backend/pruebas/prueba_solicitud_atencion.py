"""Solicitud de Atencion Medica de la acreditacion vigente: la ruta por
rol, el caso de uso (evento sin datos del paciente) y la lectura cifrada."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from httpx import AsyncClient

from app.dominio.acceso.entidades import NombreRol
from app.dominio.acreditacion.puertos import AcreditacionRegistrada
from app.dominio.acreditacion.solicitud_atencion import (
    ErrorSolicitudAtencionNoDisponible,
    VerSolicitudAtencion,
)
from app.dominio.acreditacion.valores import ResultadoAcreditacion
from app.dominio.puertos_comunes import Evento
from app.infraestructura.seguridad.almacen_evidencias_cifrado import AlmacenEvidenciasCifrado

_RUTA = "/cuentas/1/acreditacion/solicitud-atencion"
_EVIDENCIA = "evidencia_acreditacion/7/documento.png.cifrado"


async def prueba_solicitud_sin_token_devuelve_401(cliente: AsyncClient) -> None:
    assert (await cliente.get(_RUTA)).status_code == 401


@pytest.mark.parametrize("rol", [NombreRol.TESORERIA, NombreRol.GERENTE, NombreRol.ADMINISTRADOR])
async def prueba_solicitud_con_rol_sin_acceso_devuelve_403(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]], rol: NombreRol
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.get(_RUTA, headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 403


@pytest.mark.parametrize("rol", [NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE])
async def prueba_solicitud_con_rol_con_acceso_no_devuelve_401_ni_403(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]], rol: NombreRol
) -> None:
    token = await token_para_rol(rol)
    respuesta = await cliente.get(_RUTA, headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code not in (401, 403)


def _acreditacion(ruta: str | None) -> AcreditacionRegistrada:
    return AcreditacionRegistrada(
        id=5,
        instante=datetime(2026, 11, 19, tzinfo=UTC),
        resultado=ResultadoAcreditacion(
            condicion_cobertura="ACREDITABLE",
            codigo_autorizacion="AUT1",
            tipo_documento_autorizacion="01",
            codigo_asegurado="00012-1",
            tipo_afiliacion="1",
            plan=None,
            vigente_desde=None,
            vigente_hasta=None,
            tipo_copago=None,
            monto_copago_fijo=None,
            porcentaje_coaseguro=None,
            ruta_evidencia=ruta,
        ),
    )


@dataclass
class _Repositorio:
    acreditacion: AcreditacionRegistrada | None

    async def obtener_acreditacion(self, cuenta_medica_id: int) -> AcreditacionRegistrada | None:
        return self.acreditacion


class _Almacen:
    def leer(self, ruta: str) -> bytes:
        return b"PNG"


@dataclass
class _Eventos:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


async def prueba_entrega_el_documento_y_deja_evento_sin_datos_del_paciente() -> None:
    eventos = _Eventos()
    caso_uso = VerSolicitudAtencion(
        _Repositorio(_acreditacion(_EVIDENCIA)),  # type: ignore[arg-type]
        _Almacen(),
        eventos,
    )
    documento = await caso_uso.ejecutar(1, "ana.analista")
    assert (documento.contenido, documento.tipo_contenido) == (b"PNG", "image/png")
    assert eventos.eventos[0].tipo_evento == "SOLICITUD_ATENCION_CONSULTADA"
    assert eventos.eventos[0].datos == {"acreditacion_id": 5}


async def prueba_sin_documento_capturado_no_esta_disponible() -> None:
    eventos = _Eventos()
    caso_uso = VerSolicitudAtencion(
        _Repositorio(_acreditacion(None)),  # type: ignore[arg-type]
        _Almacen(),
        eventos,
    )
    with pytest.raises(ErrorSolicitudAtencionNoDisponible):
        await caso_uso.ejecutar(1, "ana.analista")
    assert eventos.eventos == []


def prueba_almacen_descifra_y_no_sale_de_su_carpeta(tmp_path: Path) -> None:
    clave = Fernet.generate_key().decode()
    archivo = tmp_path / _EVIDENCIA
    archivo.parent.mkdir(parents=True)
    archivo.write_bytes(Fernet(clave.encode()).encrypt(b"PNG"))
    almacen = AlmacenEvidenciasCifrado(tmp_path, clave)
    assert almacen.leer(_EVIDENCIA) == b"PNG"
    with pytest.raises(ErrorSolicitudAtencionNoDisponible):
        almacen.leer("../fuera.png.cifrado")
    with pytest.raises(ErrorSolicitudAtencionNoDisponible):
        AlmacenEvidenciasCifrado(tmp_path, Fernet.generate_key().decode()).leer(_EVIDENCIA)
