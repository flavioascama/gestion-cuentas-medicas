"""Navegacion visible del robot: la opcion y el modo que fija el
administrador, el registro de pasos (sin imagenes), el cuadro en vivo (uno
por trabajo, cifrado, solo para quien pidio la tarea) y quien puede que."""

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
    MODO_SISTEMA,
    MODO_VENTANA,
    TIPO_EVENTO_NAVEGACION_CONSULTADA,
    TIPO_EVENTO_OPCION_CAMBIADA,
    CambiarNavegacionVisible,
    CuadroEnVivo,
    ErrorModoNavegacion,
    OpcionNavegacion,
    PasoRegistrado,
    VerRobotEnVivo,
    le_toca_atender,
    url_sin_consulta,
)
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo
from app.infraestructura.persistencia.modelos_robot import PasoRobotModelo
from app.infraestructura.persistencia.repositorio_navegacion_robot_sql import (
    RepositorioNavegacionRobotSql,
)

_JPEG = b"\xff\xd8\xff\xe0cuadro-de-prueba\xff\xd9"


@dataclass
class _EventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@dataclass
class _RepositorioFalso:
    opcion: OpcionNavegacion = OpcionNavegacion(False, MODO_SISTEMA)
    imagenes: dict[tuple[int, str], bytes] = field(default_factory=dict)

    async def fijar_opcion_navegacion(self, opcion: OpcionNavegacion, actor: str) -> None:
        self.opcion = opcion

    async def imagen_en_vivo(self, trabajo_id: int, usuario: str) -> bytes | None:
        return self.imagenes.get((trabajo_id, usuario))


# --- dominio --------------------------------------------------------------


def prueba_la_url_guardada_no_lleva_el_documento_del_asegurado() -> None:
    url = (
        "http://acredita-salud:8000/acreditacion/evaluar?tipo_documento=1&numero_documento=81953443"
    )
    assert url_sin_consulta(url) == "http://acredita-salud:8000/acreditacion/evaluar"
    assert url_sin_consulta("http://tedef-web:8000/menu#inicio") == "http://tedef-web:8000/menu"


async def prueba_cambiar_la_opcion_la_fija_y_deja_evento_del_administrador() -> None:
    repositorio, eventos = _RepositorioFalso(), _EventosFalso()
    opcion = OpcionNavegacion(activa=True, modo=MODO_VENTANA)

    await CambiarNavegacionVisible(repositorio, eventos).ejecutar(  # type: ignore[arg-type]
        opcion, actor="administrador", usuario_id=7
    )

    assert repositorio.opcion == opcion
    assert [(e.tipo_evento, e.actor, e.sesion_usuario_id, e.datos) for e in eventos.eventos] == [
        (TIPO_EVENTO_OPCION_CAMBIADA, "administrador", 7, {"activa": True, "modo": MODO_VENTANA})
    ]


async def prueba_un_modo_desconocido_no_se_guarda() -> None:
    repositorio, eventos = _RepositorioFalso(), _EventosFalso()

    with pytest.raises(ErrorModoNavegacion):
        await CambiarNavegacionVisible(repositorio, eventos).ejecutar(  # type: ignore[arg-type]
            OpcionNavegacion(activa=True, modo="otro"), actor="administrador", usuario_id=7
        )

    assert repositorio.opcion.activa is False and eventos.eventos == []


async def prueba_empezar_a_mirar_al_robot_queda_en_el_historial_una_sola_vez() -> None:
    repositorio = _RepositorioFalso(imagenes={(5, "analista"): _JPEG})
    eventos = _EventosFalso()
    caso_uso = VerRobotEnVivo(repositorio, eventos)  # type: ignore[arg-type]

    assert await caso_uso.ejecutar(5, "analista", usuario_id=3, primera=True) == _JPEG
    assert await caso_uso.ejecutar(5, "analista", usuario_id=3, primera=False) == _JPEG
    # El trabajo de otra persona no se ve, ni queda como consultado.
    assert await caso_uso.ejecutar(5, "otro.analista", usuario_id=4, primera=True) is None

    assert [(e.tipo_evento, e.actor, e.datos) for e in eventos.eventos] == [
        (TIPO_EVENTO_NAVEGACION_CONSULTADA, "analista", {"trabajo_id": 5})
    ]


def prueba_el_robot_con_pantalla_atiende_solo_si_se_pide_la_ventana_real() -> None:
    local = OpcionNavegacion(activa=True, modo=MODO_VENTANA)
    desplegado = OpcionNavegacion(activa=True, modo=MODO_SISTEMA)
    apagada = OpcionNavegacion(activa=False, modo=MODO_VENTANA)

    # El robot con pantalla solo trabaja para mostrar la ventana real.
    assert le_toca_atender(local, con_pantalla=True, hay_robot_con_pantalla=True)
    assert not le_toca_atender(desplegado, con_pantalla=True, hay_robot_con_pantalla=True)
    assert not le_toca_atender(apagada, con_pantalla=True, hay_robot_con_pantalla=True)
    # El del servidor le cede el turno solo mientras el otro este encendido.
    assert not le_toca_atender(local, con_pantalla=False, hay_robot_con_pantalla=True)
    assert le_toca_atender(local, con_pantalla=False, hay_robot_con_pantalla=False)
    assert le_toca_atender(desplegado, con_pantalla=False, hay_robot_con_pantalla=True)
    assert le_toca_atender(apagada, con_pantalla=False, hay_robot_con_pantalla=True)


# --- RepositorioNavegacionRobotSql ----------------------------------------


async def _trabajo(sesion: AsyncSession, usuario: str = "analista.prueba") -> int:
    trabajo = TrabajoModelo(
        tipo="CONSULTAR_COBERTURA",
        carga_util={"usuario_origen": usuario},
        proximo_intento=datetime.now(UTC),
    )
    sesion.add(trabajo)
    await sesion.flush()
    return trabajo.id


def _paso(trabajo_id: int, descripcion: str) -> PasoRegistrado:
    return PasoRegistrado(
        trabajo_id=trabajo_id,
        plataforma="acredita_salud",
        descripcion=descripcion,
        url="http://acredita-salud:8000/menu",
    )


def _cuadro(trabajo_id: int, imagen: bytes, instante: datetime) -> CuadroEnVivo:
    return CuadroEnVivo(
        trabajo_id=trabajo_id,
        url="http://acredita-salud:8000/acreditacion/iafas",
        imagen=imagen,
        instante=instante,
    )


async def prueba_la_opcion_nace_apagada_y_guarda_el_modo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioNavegacionRobotSql(sesion)
        assert await repositorio.opcion_navegacion() == OpcionNavegacion(False, MODO_SISTEMA)
        await repositorio.fijar_opcion_navegacion(OpcionNavegacion(True, MODO_VENTANA), "admin")
        assert await repositorio.opcion_navegacion() == OpcionNavegacion(True, MODO_VENTANA)
        await repositorio.fijar_opcion_navegacion(OpcionNavegacion(False, MODO_SISTEMA), "admin")
        assert await repositorio.opcion_navegacion() == OpcionNavegacion(False, MODO_SISTEMA)


async def prueba_el_latido_del_robot_con_pantalla_vence(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    ahora = datetime.now(UTC)
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioNavegacionRobotSql(sesion)
        assert await repositorio.hay_robot_con_pantalla(ahora - timedelta(seconds=20)) is False
        await repositorio.registrar_latido_pantalla(ahora)
        await sesion.commit()
        assert await repositorio.hay_robot_con_pantalla(ahora - timedelta(seconds=20)) is True
        assert await repositorio.hay_robot_con_pantalla(ahora + timedelta(seconds=1)) is False


async def prueba_los_pasos_se_numeran_por_trabajo_y_quedan_con_su_usuario(
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
        actividad = await repositorio.actividad(10)
        assert [(a.trabajo_id, a.pasos) for a in actividad] == [(otro_id, 1), (trabajo_id, 2)]
        assert {a.usuario for a in actividad} == {"analista.prueba"}


async def prueba_el_cuadro_en_vivo_es_uno_por_trabajo_cifrado_y_de_quien_lo_pidio(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    ahora = datetime.now(UTC)
    async with fabrica_sesiones() as sesion:
        repositorio = RepositorioNavegacionRobotSql(sesion)
        trabajo_id = await _trabajo(sesion, "analista.uno")
        await repositorio.guardar_cuadro(_cuadro(trabajo_id, b"primer-cuadro", ahora))
        await repositorio.guardar_cuadro(_cuadro(trabajo_id, _JPEG, ahora))
        await sesion.commit()

        assert await sesion.scalar(sa.text("select count(*) from cuadro_robot")) == 1
        # En la base la imagen no esta en claro (C-05).
        crudo = await sesion.scalar(sa.text("select cuadro from cuadro_robot"))
        assert crudo is not None and bytes(crudo) != _JPEG

        desde = ahora - timedelta(seconds=15)
        en_vivo = await repositorio.trabajo_en_vivo("analista.uno", desde)
        assert en_vivo is not None and en_vivo.trabajo_id == trabajo_id
        assert en_vivo.tipo == "CONSULTAR_COBERTURA"
        assert await repositorio.imagen_en_vivo(trabajo_id, "analista.uno") == _JPEG
        # Otra persona no ve ni el trabajo ni la imagen.
        assert await repositorio.trabajo_en_vivo("analista.dos", desde) is None
        assert await repositorio.imagen_en_vivo(trabajo_id, "analista.dos") is None
        # Un cuadro que dejo de actualizarse ya no cuenta como en vivo.
        despues = ahora + timedelta(seconds=1)
        assert await repositorio.trabajo_en_vivo("analista.uno", despues) is None

        await repositorio.borrar_cuadros()
        assert await repositorio.trabajo_en_vivo("analista.uno", desde) is None
        assert await repositorio.imagen_en_vivo(trabajo_id, "analista.uno") is None


async def prueba_la_purga_borra_solo_los_pasos_vencidos(
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

_Token = Callable[[NombreRol], Awaitable[str]]


async def _cabeceras(token_para_rol: _Token, rol: NombreRol) -> dict[str, str]:
    return {"Authorization": f"Bearer {await token_para_rol(rol)}"}


async def prueba_solo_el_administrador_cambia_la_opcion(
    cliente: AsyncClient, token_para_rol: _Token
) -> None:
    cuerpo = {"activa": True, "modo": "ventana"}
    assert (await cliente.put("/robot/navegacion-visible", json=cuerpo)).status_code == 401
    for rol in (NombreRol.ANALISTA, NombreRol.JEFE):
        respuesta = await cliente.put(
            "/robot/navegacion-visible", json=cuerpo, headers=await _cabeceras(token_para_rol, rol)
        )
        assert respuesta.status_code == 403

    administrador = await _cabeceras(token_para_rol, NombreRol.ADMINISTRADOR)
    respuesta = await cliente.put("/robot/navegacion-visible", json=cuerpo, headers=administrador)
    estado = {**cuerpo, "robot_con_pantalla": False}
    assert respuesta.status_code == 200 and respuesta.json() == estado
    consulta = await cliente.get("/robot/navegacion-visible", headers=administrador)
    assert consulta.json() == estado
    invalido = await cliente.put(
        "/robot/navegacion-visible", json={"activa": True, "modo": "otro"}, headers=administrador
    )
    assert invalido.status_code == 422


@pytest.mark.parametrize("ruta", ["/robot/actividad", "/robot/trabajos/1/pasos"])
async def prueba_el_registro_del_robot_es_solo_del_administrador(
    cliente: AsyncClient, token_para_rol: _Token, ruta: str
) -> None:
    assert (await cliente.get(ruta)).status_code == 401
    for rol in (NombreRol.ANALISTA, NombreRol.JEFE):
        respuesta = await cliente.get(ruta, headers=await _cabeceras(token_para_rol, rol))
        assert respuesta.status_code == 403
    administrador = await _cabeceras(token_para_rol, NombreRol.ADMINISTRADOR)
    respuesta = await cliente.get(ruta, headers=administrador)
    assert respuesta.status_code == 200 and respuesta.json() == []


async def prueba_la_vista_en_vivo_es_de_quien_opera_y_no_del_administrador(
    cliente: AsyncClient, token_para_rol: _Token
) -> None:
    assert (await cliente.get("/robot/en-vivo")).status_code == 401
    administrador = await _cabeceras(token_para_rol, NombreRol.ADMINISTRADOR)
    assert (await cliente.get("/robot/en-vivo", headers=administrador)).status_code == 403
    assert (await cliente.get("/robot/en-vivo/1/cuadro", headers=administrador)).status_code == 403
    for rol in (NombreRol.ANALISTA, NombreRol.JEFE):
        cabeceras = await _cabeceras(token_para_rol, rol)
        en_vivo = await cliente.get("/robot/en-vivo", headers=cabeceras)
        assert en_vivo.status_code == 200 and en_vivo.json() is None
        cuadro = await cliente.get("/robot/en-vivo/1/cuadro", headers=cabeceras)
        assert cuadro.status_code == 404
