"""Adaptador de RepositorioNavegacionRobot. Lo usan el backend (opcion del
administrador, registro del robot y vista en vivo) y el trabajador (que
anota los pasos y publica el cuadro en vivo)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.plataformas.navegacion_robot import (
    CLAVE_LATIDO_ROBOT_CON_PANTALLA,
    CLAVE_OPCION_NAVEGACION_MODO,
    CLAVE_OPCION_NAVEGACION_VISIBLE,
    MODO_SISTEMA,
    MODOS_NAVEGACION,
    ActividadRobot,
    CuadroEnVivo,
    OpcionNavegacion,
    PasoRegistrado,
    PasoRobot,
    RepositorioNavegacionRobot,
    TrabajoEnVivo,
)
from app.infraestructura.persistencia.modelos_integracion import TrabajoModelo
from app.infraestructura.persistencia.modelos_robot import (
    CuadroRobotModelo,
    OpcionSistemaModelo,
    PasoRobotModelo,
)

_ACTIVA = "true"
_INACTIVA = "false"


def _pidio(trabajo: TrabajoModelo, usuario: str) -> bool:
    # Quien pidio la tarea viaja en la carga util del trabajo.
    return trabajo.carga_util.get("usuario_origen") == usuario


class RepositorioNavegacionRobotSql(RepositorioNavegacionRobot):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def opcion_navegacion(self) -> OpcionNavegacion:
        activa = await self._sesion.get(OpcionSistemaModelo, CLAVE_OPCION_NAVEGACION_VISIBLE)
        modo = await self._sesion.get(OpcionSistemaModelo, CLAVE_OPCION_NAVEGACION_MODO)
        conocido = modo is not None and modo.valor in MODOS_NAVEGACION
        return OpcionNavegacion(
            activa=activa is not None and activa.valor == _ACTIVA,
            modo=modo.valor if modo is not None and conocido else MODO_SISTEMA,
        )

    async def _fijar(self, clave: str, valor: str, actor: str) -> None:
        opcion = await self._sesion.get(OpcionSistemaModelo, clave)
        if opcion is None:
            self._sesion.add(OpcionSistemaModelo(clave=clave, valor=valor, actualizado_por=actor))
        else:
            opcion.valor = valor
            opcion.actualizado_por = actor

    async def fijar_opcion_navegacion(self, opcion: OpcionNavegacion, actor: str) -> None:
        visible = _ACTIVA if opcion.activa else _INACTIVA
        await self._fijar(CLAVE_OPCION_NAVEGACION_VISIBLE, visible, actor)
        await self._fijar(CLAVE_OPCION_NAVEGACION_MODO, opcion.modo, actor)
        await self._sesion.flush()

    async def registrar_paso(self, paso: PasoRegistrado) -> int:
        ultimo = await self._sesion.scalar(
            sa.select(sa.func.max(PasoRobotModelo.orden)).where(
                PasoRobotModelo.trabajo_id == paso.trabajo_id
            )
        )
        orden = int(ultimo or 0) + 1
        self._sesion.add(
            PasoRobotModelo(
                trabajo_id=paso.trabajo_id,
                orden=orden,
                plataforma=paso.plataforma,
                descripcion=paso.descripcion,
                url=paso.url,
            )
        )
        await self._sesion.flush()
        return orden

    async def pasos(self, trabajo_id: int) -> list[PasoRobot]:
        filas = await self._sesion.execute(
            sa.select(
                PasoRobotModelo.orden,
                PasoRobotModelo.plataforma,
                PasoRobotModelo.descripcion,
                PasoRobotModelo.url,
                PasoRobotModelo.capturado_en,
            )
            .where(PasoRobotModelo.trabajo_id == trabajo_id)
            .order_by(PasoRobotModelo.orden)
        )
        return [PasoRobot(*fila) for fila in filas.all()]

    async def actividad(self, maximo: int) -> list[ActividadRobot]:
        resumen = (
            sa.select(
                PasoRobotModelo.trabajo_id.label("trabajo_id"),
                sa.func.min(PasoRobotModelo.capturado_en).label("inicio"),
                sa.func.count(PasoRobotModelo.id).label("pasos"),
            )
            .group_by(PasoRobotModelo.trabajo_id)
            .subquery()
        )
        filas = await self._sesion.execute(
            sa.select(TrabajoModelo, resumen.c.inicio, resumen.c.pasos)
            .join(resumen, resumen.c.trabajo_id == TrabajoModelo.id)
            .order_by(TrabajoModelo.id.desc())
            .limit(maximo)
        )
        return [
            ActividadRobot(
                trabajo_id=trabajo.id,
                tipo=trabajo.tipo,
                estado=trabajo.estado,
                usuario=str(trabajo.carga_util.get("usuario_origen") or "—"),
                iniciado_en=inicio,
                pasos=cantidad,
            )
            for trabajo, inicio, cantidad in filas.all()
        ]

    async def guardar_cuadro(self, cuadro: CuadroEnVivo) -> None:
        actual = await self._sesion.get(CuadroRobotModelo, cuadro.trabajo_id)
        if actual is None:
            self._sesion.add(
                CuadroRobotModelo(
                    trabajo_id=cuadro.trabajo_id,
                    url=cuadro.url,
                    cuadro=cuadro.imagen,
                    actualizado_en=cuadro.instante,
                )
            )
        else:
            actual.url = cuadro.url
            actual.cuadro = cuadro.imagen
            actual.actualizado_en = cuadro.instante
        await self._sesion.flush()

    async def borrar_cuadros(self) -> None:
        await self._sesion.execute(sa.delete(CuadroRobotModelo))

    async def trabajo_en_vivo(self, usuario: str, desde: datetime) -> TrabajoEnVivo | None:
        # Sin la columna de la imagen: esta consulta se repite cada segundo.
        filas = await self._sesion.execute(
            sa.select(TrabajoModelo, CuadroRobotModelo.url, CuadroRobotModelo.actualizado_en)
            .join(CuadroRobotModelo, CuadroRobotModelo.trabajo_id == TrabajoModelo.id)
            .where(CuadroRobotModelo.actualizado_en >= desde)
            .order_by(CuadroRobotModelo.actualizado_en.desc())
        )
        for trabajo, url, actualizado_en in filas.all():
            if _pidio(trabajo, usuario):
                return TrabajoEnVivo(
                    trabajo_id=trabajo.id, tipo=trabajo.tipo, url=url, actualizado_en=actualizado_en
                )
        return None

    async def imagen_en_vivo(self, trabajo_id: int, usuario: str) -> bytes | None:
        trabajo = await self._sesion.get(TrabajoModelo, trabajo_id)
        if trabajo is None or not _pidio(trabajo, usuario):
            return None
        cuadro = await self._sesion.get(CuadroRobotModelo, trabajo_id)
        return cuadro.cuadro if cuadro is not None else None

    async def registrar_latido_pantalla(self, instante: datetime) -> None:
        await self._fijar(CLAVE_LATIDO_ROBOT_CON_PANTALLA, instante.isoformat(), "robot")
        await self._sesion.flush()

    async def hay_robot_con_pantalla(self, desde: datetime) -> bool:
        latido = await self._sesion.get(OpcionSistemaModelo, CLAVE_LATIDO_ROBOT_CON_PANTALLA)
        if latido is None:
            return False
        try:
            return datetime.fromisoformat(latido.valor) >= desde
        except (ValueError, TypeError):
            return False

    async def purgar_anteriores_a(self, limite: datetime) -> int:
        resultado = await self._sesion.execute(
            sa.delete(PasoRobotModelo).where(PasoRobotModelo.capturado_en < limite)
        )
        return int(getattr(resultado, "rowcount", 0) or 0)
