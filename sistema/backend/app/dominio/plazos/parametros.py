"""CU-18: administracion de los parametros por IAFAS (Tabla 61: los plazos
"por convenio" con cada aseguradora; Seccion 8.3: la ventana de monitoreo
y la periodicidad de remision). Solo el administrador los cambia y cada
cambio queda en la bitacora, con el valor anterior y el nuevo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.dominio.puertos_comunes import Evento, RegistroEventos

CAMPOS_PARAMETROS_IAFAS = (
    "periodicidad_remision_dias",
    "ventana_monitoreo_horas",
    "dias_plazo_respuesta_observacion",
    "dias_plazo_comunicacion_auditoria",
    "dias_plazo_pago_liquidacion",
)
# Cota superior de sentido comun para atrapar errores de digitacion (un
# plazo de "3000" dias); no es un valor normativo.
VALOR_MAXIMO = 365


class ErrorParametros(Exception):
    pass


class ErrorIafasInexistente(ErrorParametros):
    pass


class ErrorParametroInvalido(ErrorParametros):
    pass


@dataclass(frozen=True, slots=True)
class ParametrosIafas:
    iafas_id: int
    codigo: str
    razon_social: str
    periodicidad_remision_dias: int
    ventana_monitoreo_horas: int
    dias_plazo_respuesta_observacion: int
    dias_plazo_comunicacion_auditoria: int
    dias_plazo_pago_liquidacion: int


class RepositorioParametrosIafas(Protocol):
    async def listar(self) -> list[ParametrosIafas]: ...

    async def obtener(self, iafas_id: int) -> ParametrosIafas | None: ...

    async def actualizar(self, iafas_id: int, cambios: dict[str, int]) -> ParametrosIafas: ...


class ListarParametrosIafas:
    def __init__(self, repositorio: RepositorioParametrosIafas) -> None:
        self._repositorio = repositorio

    async def ejecutar(self) -> list[ParametrosIafas]:
        return await self._repositorio.listar()


def _validar(cambios: dict[str, int]) -> None:
    desconocidos = sorted(set(cambios) - set(CAMPOS_PARAMETROS_IAFAS))
    if desconocidos:
        raise ErrorParametroInvalido("Parametros desconocidos: " + ", ".join(desconocidos) + ".")
    fuera = sorted(campo for campo, valor in cambios.items() if not 1 <= valor <= VALOR_MAXIMO)
    if fuera:
        raise ErrorParametroInvalido(
            f"Deben estar entre 1 y {VALOR_MAXIMO}: " + ", ".join(fuera) + "."
        )


class ActualizarParametrosIafas:
    def __init__(
        self, repositorio: RepositorioParametrosIafas, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(
        self, iafas_id: int, cambios: dict[str, int], actor: str, usuario_id: int
    ) -> ParametrosIafas:
        _validar(cambios)
        actuales = await self._repositorio.obtener(iafas_id)
        if actuales is None:
            raise ErrorIafasInexistente(f"No existe la IAFAS {iafas_id}.")
        diferencias = {
            campo: {"antes": getattr(actuales, campo), "despues": valor}
            for campo, valor in cambios.items()
            if getattr(actuales, campo) != valor
        }
        if not diferencias:
            return actuales
        actualizados = await self._repositorio.actualizar(
            iafas_id, {campo: valores["despues"] for campo, valores in diferencias.items()}
        )
        # La bitacora de administracion va al agregado de sesion de quien
        # hizo el cambio (la IAFAS no es un agregado del almacen).
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento="PARAMETROS_IAFAS_ACTUALIZADOS",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"iafas_codigo": actuales.codigo, "cambios": diferencias},
            )
        )
        return actualizados
