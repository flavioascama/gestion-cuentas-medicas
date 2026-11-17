"""Navegacion visible del robot: la opcion que activa el administrador, las
capturas por paso (cifradas en la base), quien puede verlas y que queda en
el historial."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acceso.entidades import NombreRol
from app.dominio.plataformas.navegacion_robot import (
    TIPO_EVENTO_NAVEGACION_CONSULTADA,
    TIPO_EVENTO_OPCION_CAMBIADA,
    CambiarNavegacionVisible,
    ObtenerCapturaPaso,
    PasoCapturado,
    url_sin_consulta,
)
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo
from app.infraestructura.persistencia.modelos_robot import PasoRobotModelo
from app.infraestructura.persistencia.repositorio_navegacion_robot_sql import (
    RepositorioNavegacionRobotSql,
)

_JPEG = b"\xff\xd8\xff\xe0captura-de-prueba\xff\xd9"


@dataclass
class _EventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@dataclass
class _RepositorioFalso:
    activa: bool = False
    capturas: dict[tuple[int, int], bytes] = field(default_factory=dict)

    async def navegacion_visible(self) -> bool:
        return self.activa

    async def fijar_navegacion_visible(self, activa: bool, actor: str) -> None:
        self.activa = activa

    async def captura(self, trabajo_id: int, orden: int) -> bytes | None:
        return self.capturas.get((trabajo_id, orden))


# --- dominio --------------------------------------------------------------


def prueba_la_url_guardada_no_lleva_el_documento_del_asegurado() -> None:
    url = (
        "http://acredita-salud:8000/acreditacion/evaluar?tipo_documento=1&numero_documento=81953443"
    )
    assert url_sin_consulta(url) == "http://acredita-salud:8000/acreditacion/evaluar"
    assert url_sin_consulta("http://tedef-web:8000/menu#inicio") == "http://tedef-web:8000/menu"


async def prueba_cambiar_la_opcion_la_fija_y_deja_evento_del_administrador() -> None:
    repositorio, eventos = _RepositorioFalso(), _EventosFalso()

    activa = await CambiarNavegacionVisible(repositorio, eventos).ejecutar(
        True, actor="administrador", usuario_id=7
    )

    assert activa is True and repositorio.activa is True
    assert [(e.tipo_evento, e.actor, e.sesion_usuario_id, e.datos) for e in eventos.eventos] == [
        (TIPO_EVENTO_OPCION_CAMBIADA, "administrador", 7, {"activa": True})
    ]


async def prueba_abrir_la_primera_captura_queda_en_el_historial_y_las_demas_no() -> None:
    repositorio = _RepositorioFalso(capturas={(5, 1): _JPEG, (5, 2): _JPEG})
    eventos = _EventosFalso()
    caso_uso = ObtenerCapturaPaso(repositorio, eventos)

    assert await caso_uso.ejecutar(5, 1, actor="analista", usuario_id=3) == _JPEG
    assert await caso_uso.ejecutar(5, 2, actor="analista", usuario_id=3) == _JPEG
    assert await caso_uso.ejecutar(5, 9, actor="analista", usuario_id=3) is None

    assert [(e.tipo_evento, e.datos) for e in eventos.eventos] == [
        (TIPO_EVENTO_NAVEGACION_CONSULTADA, {"trabajo_id": 5})
    ]


# --- RepositorioNavegacionRobotSql ----------------------------------------


async def _trabajo(sesion: AsyncSession) -> int:
    trabajo = TrabajoModelo(
        tipo="CONSULTAR_COBERTURA", carga_util={}, proximo_intento=datetime.now(UTC)
    )
    sesion.add(trabajo)
    await sesion.flush()
    return trabajo.id


def _paso(trabajo_id: int, descripcion: str) -> PasoCapturado:
    return PasoCapturado(
        trabajo_id=trabajo_id,
        plataforma="acredita_salud",
        descripcion=descripcion,
        url="http://acredita-salud:8000/menu",
        captura=_JPEG,
    )


async def prueba_la_opcion_nace_apagada_y_se_puede_activar_y_apagar(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioNavegacionRobotSql(sesion)
        assert await repositorio.navegacion_visible() is False
        await repositorio.fijar_navegacion_visible(True, "administrador")
        assert await repositorio.navegacion_visible() is True
        await repositorio.fijar_navegacion_visible(False, "administrador")
        assert await repositorio.navegacion_visible() is False


async def prueba_los_pasos_se_numeran_por_trabajo_y_la_captura_se_guarda_cifrada(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioNavegacionRobotSql(sesion)
        trabajo_id = await _trabajo(sesion)
        otro_id = await _trabajo(sesion)
        assert await repositorio.registrar_paso(_paso(trabajo_id, "Menú principal")) == 1
        assert await repositorio.registrar_paso(_paso(trabajo_id, "Consulta del asegurado")) == 2
        assert await repositorio.registrar_paso(_paso(otro_id, "Menú principal")) == 1
        await sesion.commit()

        pasos = await repositorio.pasos(trabajo_id)
        assert [(p.orden, p.descripcion) for p in pasos] == [
            (1, "Menú principal"),
            (2, "Consulta del asegurado"),
        ]
        assert await repositorio.captura(trabajo_id, 2) == _JPEG
        assert await repositorio.captura(trabajo_id, 3) is None

        # En la base la imagen no esta en claro (C-05).
        crudo = await sesion.scalar(sa.text("select captura from paso_robot limit 1"))
        assert crudo is not None and bytes(crudo) != _JPEG

        actividad = await repositorio.actividad(10)
        assert [(a.trabajo_id, a.pasos) for a in actividad] == [(otro_id, 1), (trabajo_id, 2)]


async def prueba_la_purga_borra_solo_las_capturas_vencidas(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioNavegacionRobotSql(sesion)
        trabajo_id = await _trabajo(sesion)
        await repositorio.registrar_paso(_paso(trabajo_id, "Paso antiguo"))
        await repositorio.registrar_paso(_paso(trabajo_id, "Paso reciente"))
        ahora = datetime.now(UTC)
        await sesion.execute(
            sa.update(PasoRobotModelo)
            .where(PasoRobotModelo.orden == 1)
            .values(capturado_en=ahora - timedelta(days=30))
        )
        await sesion.execute(
            sa.update(PasoRobotModelo).where(PasoRobotModelo.orden == 2).values(capturado_en=ahora)
        )

        await repositorio.purgar_anteriores_a(ahora - timedelta(days=7))

        assert [p.descripcion for p in await repositorio.pasos(trabajo_id)] == ["Paso reciente"]


# --- quien puede que ------------------------------------------------------


async def prueba_solo_el_administrador_cambia_la_opcion(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    assert (
        await cliente.put("/robot/navegacion-visible", json={"activa": True})
    ).status_code == 401
    for rol in (NombreRol.ANALISTA, NombreRol.JEFE):
        cabeceras = {"Authorization": f"Bearer {await token_para_rol(rol)}"}
        respuesta = await cliente.put(
            "/robot/navegacion-visible", json={"activa": True}, headers=cabeceras
        )
        assert respuesta.status_code == 403

    administrador = {"Authorization": f"Bearer {await token_para_rol(NombreRol.ADMINISTRADOR)}"}
    respuesta = await cliente.put(
        "/robot/navegacion-visible", json={"activa": True}, headers=administrador
    )
    assert respuesta.status_code == 200 and respuesta.json() == {"activa": True}
    consulta = await cliente.get("/robot/navegacion-visible", headers=administrador)
    assert consulta.json() == {"activa": True}


@pytest.mark.parametrize("ruta", ["/robot/actividad", "/robot/trabajos/1/pasos"])
async def prueba_el_administrador_no_ve_las_capturas_y_quien_opera_si(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]], ruta: str
) -> None:
    assert (await cliente.get(ruta)).status_code == 401
    administrador = {"Authorization": f"Bearer {await token_para_rol(NombreRol.ADMINISTRADOR)}"}
    assert (await cliente.get(ruta, headers=administrador)).status_code == 403
    for rol in (NombreRol.ANALISTA, NombreRol.JEFE):
        cabeceras = {"Authorization": f"Bearer {await token_para_rol(rol)}"}
        respuesta = await cliente.get(ruta, headers=cabeceras)
        assert respuesta.status_code == 200 and respuesta.json() == []


async def prueba_una_captura_inexistente_responde_404(
    cliente: AsyncClient, token_para_rol: Callable[[NombreRol], Awaitable[str]]
) -> None:
    cabeceras = {"Authorization": f"Bearer {await token_para_rol(NombreRol.ANALISTA)}"}
    respuesta = await cliente.get("/robot/trabajos/1/pasos/1/captura", headers=cabeceras)
    assert respuesta.status_code == 404
