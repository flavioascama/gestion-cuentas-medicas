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
# Los mismos nombres que muestra la pantalla de aseguradoras.
_ETIQUETAS_PLAZOS = {
    "periodicidad_remision_dias": "Frecuencia de remisión",
    "ventana_monitoreo_horas": "Monitoreo de respuestas",
    "dias_plazo_respuesta_observacion": "Respuesta a observaciones",
    "dias_plazo_comunicacion_auditoria": "Resultado de auditoría",
    "dias_plazo_pago_liquidacion": "Pago de liquidación",
}
# Cota superior de sentido comun para atrapar errores de digitacion (un
# plazo de "3000" dias); no es un valor normativo. Dias: un anio; horas: una
# semana (tercera auditoria, menor 10).
_MAXIMOS_PLAZOS = {
    campo: (168, "horas") if campo.endswith("_horas") else (365, "días")
    for campo in CAMPOS_PARAMETROS_IAFAS
}


class ErrorParametros(Exception):
    pass


class ErrorIafasInexistente(ErrorParametros):
    pass


class ErrorParametroInvalido(ErrorParametros):
    pass


class ErrorCodigoIafasRepetido(ErrorParametros):
    pass


class ErrorIafasConRegistros(ErrorParametros):
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
    correo_remitente: str | None = None


class RepositorioParametrosIafas(Protocol):
    async def listar(self) -> list[ParametrosIafas]: ...

    async def obtener(self, iafas_id: int) -> ParametrosIafas | None: ...

    async def actualizar(self, iafas_id: int, cambios: dict[str, int | str]) -> ParametrosIafas: ...


class RepositorioRemitenteIafas(Protocol):
    """Lo que necesita el registro del remitente de una aseguradora."""

    async def obtener(self, iafas_id: int) -> ParametrosIafas | None: ...

    async def actualizar_remitente(
        self, iafas_id: int, correo_remitente: str | None
    ) -> ParametrosIafas: ...


@dataclass(frozen=True, slots=True)
class NuevaIafas:
    codigo: str
    razon_social: str
    plazos: dict[str, int]


class RepositorioAltaBajaIafas(Protocol):
    """Lo que necesitan el alta y la baja de una aseguradora."""

    async def obtener(self, iafas_id: int) -> ParametrosIafas | None: ...

    async def existe_codigo(self, codigo: str) -> bool: ...

    async def crear(
        self, codigo: str, razon_social: str, plazos: dict[str, int]
    ) -> ParametrosIafas: ...

    async def tiene_registros(self, iafas_id: int) -> bool: ...

    async def eliminar(self, iafas_id: int) -> None: ...


class ListarParametrosIafas:
    def __init__(self, repositorio: RepositorioParametrosIafas) -> None:
        self._repositorio = repositorio

    async def ejecutar(self) -> list[ParametrosIafas]:
        return await self._repositorio.listar()


def _validar(cambios: dict[str, int]) -> None:
    if set(cambios) - set(CAMPOS_PARAMETROS_IAFAS):
        raise ErrorParametroInvalido("Hay plazos que no existen.")
    fuera = [
        f"{_ETIQUETAS_PLAZOS[campo]}: debe estar entre 1 y {maximo} {unidad}"
        for campo, valor in cambios.items()
        for maximo, unidad in [_MAXIMOS_PLAZOS[campo]]
        if not 1 <= valor <= maximo
    ]
    if fuera:
        raise ErrorParametroInvalido("; ".join(fuera) + ".")


class ActualizarParametrosIafas:
    def __init__(
        self, repositorio: RepositorioParametrosIafas, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(
        self,
        iafas_id: int,
        cambios: dict[str, int],
        actor: str,
        usuario_id: int,
        razon_social: str | None = None,
    ) -> ParametrosIafas:
        _validar(cambios)
        nueva_razon = razon_social.strip() if razon_social is not None else None
        if nueva_razon == "":
            raise ErrorParametroInvalido("Falta la razón social.")
        actuales = await self._repositorio.obtener(iafas_id)
        if actuales is None:
            raise ErrorIafasInexistente("No se encontró la IAFAS.")
        propuestos: dict[str, int | str] = dict(cambios)
        if nueva_razon is not None:
            propuestos["razon_social"] = nueva_razon
        diferencias = {
            campo: {"antes": getattr(actuales, campo), "despues": valor}
            for campo, valor in propuestos.items()
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


def _evento_iafas(tipo: str, iafas: ParametrosIafas, actor: str, usuario_id: int) -> Evento:
    return Evento(
        cuenta_medica_id=None,
        sesion_usuario_id=usuario_id,
        tipo_evento=tipo,
        actor=actor,
        estado_previo=None,
        estado_nuevo=None,
        datos={"iafas_codigo": iafas.codigo, "razon_social": iafas.razon_social},
    )


class CrearIafas:
    def __init__(
        self, repositorio: RepositorioAltaBajaIafas, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(self, datos: NuevaIafas, actor: str, usuario_id: int) -> ParametrosIafas:
        codigo, razon_social = datos.codigo.strip(), datos.razon_social.strip()
        # Cinco digitos: el codigo va en el nombre de los archivos del lote.
        if not (len(codigo) == 5 and codigo.isascii() and codigo.isdigit()):
            raise ErrorParametroInvalido("El código debe tener exactamente cinco dígitos.")
        if not razon_social:
            raise ErrorParametroInvalido("Falta la razón social.")
        faltan = [
            _ETIQUETAS_PLAZOS[campo]
            for campo in CAMPOS_PARAMETROS_IAFAS
            if campo not in datos.plazos
        ]
        if faltan:
            raise ErrorParametroInvalido("Faltan plazos: " + ", ".join(faltan) + ".")
        _validar(datos.plazos)
        if await self._repositorio.existe_codigo(codigo):
            raise ErrorCodigoIafasRepetido(f"Ya existe una IAFAS con el código {codigo}.")
        creada = await self._repositorio.crear(codigo, razon_social, datos.plazos)
        await self._registro_eventos.registrar(
            _evento_iafas("IAFAS_REGISTRADA", creada, actor, usuario_id)
        )
        return creada


class EliminarIafas:
    """Solo una aseguradora sin cuentas, lotes ni otros registros: no se
    borra en cascada."""

    def __init__(
        self, repositorio: RepositorioAltaBajaIafas, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(self, iafas_id: int, actor: str, usuario_id: int) -> None:
        actual = await self._repositorio.obtener(iafas_id)
        if actual is None:
            raise ErrorIafasInexistente("No se encontró la IAFAS.")
        if await self._repositorio.tiene_registros(iafas_id):
            raise ErrorIafasConRegistros("La IAFAS tiene registros y no se puede eliminar.")
        await self._repositorio.eliminar(iafas_id)
        await self._registro_eventos.registrar(
            _evento_iafas("IAFAS_ELIMINADA", actual, actor, usuario_id)
        )


class ActualizarRemitenteIafas:
    """Registra el remitente del que se aceptan comunicaciones por correo de
    una aseguradora. El valor llega ya validado (direcciones o dominios)."""

    def __init__(
        self, repositorio: RepositorioRemitenteIafas, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(
        self, iafas_id: int, correo_remitente: str | None, actor: str, usuario_id: int
    ) -> ParametrosIafas:
        actuales = await self._repositorio.obtener(iafas_id)
        if actuales is None:
            raise ErrorIafasInexistente("No se encontró la IAFAS.")
        if actuales.correo_remitente == correo_remitente:
            return actuales
        actualizados = await self._repositorio.actualizar_remitente(iafas_id, correo_remitente)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento="PARAMETROS_IAFAS_ACTUALIZADOS",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "iafas_codigo": actuales.codigo,
                    "cambios": {
                        "correo_remitente": {
                            "antes": actuales.correo_remitente,
                            "despues": correo_remitente,
                        }
                    },
                },
            )
        )
        return actualizados
