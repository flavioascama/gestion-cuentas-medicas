"""Matriz de permisos de la tesis con el perfil Jefe de la pantalla (roles
jefe, tesoreria y gerente): genera y valida lotes; no remite ni envia a
SUSALUD. Mas el mensaje exacto de `POST /lotes` cuando las cuentas elegidas
ya estan en un lote en curso."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.casos_uso import RegistrarUsuario
from app.dominio.acceso.entidades import NombreRol
from app.dominio.integracion.puertos import ErrorRepositorioLote
from app.infraestructura.persistencia.repositorio_lote_sql import RepositorioLoteFacturacionSql
from app.infraestructura.persistencia.repositorio_usuarios import RepositorioUsuariosSql
from app.infraestructura.seguridad.verificador_clave_bcrypt import VerificadorClaveBcrypt
from pruebas.prueba_lotes_sugeridos import _crear_cuenta
from pruebas.prueba_vigencia_lote_sql import _base, _lote

_CLAVE = "Clave-de-prueba-123"
_PERFIL_JEFE = frozenset({NombreRol.JEFE, NombreRol.TESORERIA, NombreRol.GERENTE})

_GENERAR_Y_VALIDAR: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("POST", "/lotes", {"iafas_id": 1, "periodo": "2026-01", "cuenta_ids": []}),
    ("GET", "/lotes/sugeridos", None),
    ("GET", "/lotes/1/prevalidacion", None),
    ("POST", "/lotes/1/carga-validador", None),
)
_REMITIR_Y_SUSALUD: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("POST", "/lotes/1/remision-iafas", None),
    ("POST", "/lotes/envio-susalud", {"periodo": "2026-01"}),
)


async def _token_perfil_jefe(
    cliente: AsyncClient, fabrica_sesiones: async_sessionmaker[AsyncSession]
) -> str:
    async with fabrica_sesiones() as sesion:
        await RegistrarUsuario(RepositorioUsuariosSql(sesion), VerificadorClaveBcrypt()).ejecutar(
            nombre_usuario="perfil.jefe", clave=_CLAVE, nombres="Jefe", roles=_PERFIL_JEFE
        )
    respuesta = await cliente.post(
        "/auth/sesion", json={"nombre_usuario": "perfil.jefe", "clave": _CLAVE}
    )
    return str(respuesta.json()["token"])


@pytest.mark.parametrize("metodo,ruta,cuerpo", _GENERAR_Y_VALIDAR)
async def prueba_el_perfil_jefe_genera_y_valida_lotes(
    cliente: AsyncClient,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    token = await _token_perfil_jefe(cliente, fabrica_sesiones)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code not in (401, 403)


@pytest.mark.parametrize("metodo,ruta,cuerpo", _REMITIR_Y_SUSALUD)
async def prueba_el_perfil_jefe_no_remite_ni_envia_a_susalud(
    cliente: AsyncClient,
    fabrica_sesiones: async_sessionmaker[AsyncSession],
    metodo: str,
    ruta: str,
    cuerpo: dict[str, Any] | None,
) -> None:
    token = await _token_perfil_jefe(cliente, fabrica_sesiones)
    respuesta = await cliente.request(
        metodo, ruta, json=cuerpo, headers={"Authorization": f"Bearer {token}"}
    )
    assert respuesta.status_code == 403


async def prueba_cuentas_ya_en_un_lote_en_curso_tienen_su_propio_mensaje(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress, iafas = await _base(sesion)
        documento = await _crear_cuenta(sesion, ipress, iafas, "1", "FACTURADA")
        await _lote(sesion, iafas, [documento])
        repositorio = RepositorioLoteFacturacionSql(sesion)
        with pytest.raises(
            ErrorRepositorioLote, match="Las cuentas elegidas ya están en un lote en curso."
        ):
            await repositorio.obtener_documentos_facturados(iafas.id, [documento.cuenta_id])
