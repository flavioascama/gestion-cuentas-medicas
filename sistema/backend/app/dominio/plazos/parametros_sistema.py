"""CU-18: parametros del sistema que el administrador cambia desde la
pantalla. El valor de la configuracion del despliegue es el valor por
defecto; el que se guarda lo reemplaza sin reiniciar nada. Cada cambio
queda en la bitacora con el valor anterior y el nuevo."""

from __future__ import annotations

import re
from datetime import date
from typing import Protocol

from app.dominio.puertos_comunes import Evento, RegistroEventos

CLAVE_FERIADOS = "FERIADOS"
CLAVES_NUMERICAS = (
    "DURACION_SESION_MINUTOS",
    "MAXIMO_INTENTOS_FALLIDOS_SESION",
    "DURACION_BLOQUEO_SESION_MINUTOS",
    "DIAS_PLAZO_REENVIO_LOTE_RECHAZADO",
    "DIAS_AVISO_PREVIO_VENCIMIENTO",
    "DIAS_AVISO_VIGENCIA_CARTA_GARANTIA",
    "TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS",
    "TEMPORIZADOR_INTERVALO_CADENA_HORAS",
)
CLAVES_PARAMETROS_SISTEMA = (*CLAVES_NUMERICAS, CLAVE_FERIADOS)
# Los mismos nombres que muestra la pantalla de parametros.
_ETIQUETAS = {
    "DURACION_SESION_MINUTOS": "Duración de la sesión",
    "MAXIMO_INTENTOS_FALLIDOS_SESION": "Intentos fallidos antes del bloqueo",
    "DURACION_BLOQUEO_SESION_MINUTOS": "Duración del bloqueo",
    "DIAS_PLAZO_REENVIO_LOTE_RECHAZADO": "Plazo para reenviar un lote rechazado",
    "DIAS_AVISO_PREVIO_VENCIMIENTO": "Aviso antes del vencimiento de un plazo",
    "DIAS_AVISO_VIGENCIA_CARTA_GARANTIA": "Aviso antes del fin de vigencia de la carta de garantía",
    "TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS": "Revisión de vencimientos",
    "TEMPORIZADOR_INTERVALO_CADENA_HORAS": "Verificación de la integridad del historial",
}
# Maximo razonable de cada parametro numerico, para atrapar errores de
# digitacion (tercera auditoria, menor 10): dias, un anio; minutos, un dia;
# horas, una semana.
_MAXIMOS = {
    "DURACION_SESION_MINUTOS": (1440, "minutos"),
    "MAXIMO_INTENTOS_FALLIDOS_SESION": (20, "intentos"),
    "DURACION_BLOQUEO_SESION_MINUTOS": (1440, "minutos"),
    "DIAS_PLAZO_REENVIO_LOTE_RECHAZADO": (365, "días"),
    "DIAS_AVISO_PREVIO_VENCIMIENTO": (365, "días"),
    "DIAS_AVISO_VIGENCIA_CARTA_GARANTIA": (365, "días"),
    "TEMPORIZADOR_INTERVALO_VENCIMIENTOS_MINUTOS": (1440, "minutos"),
    "TEMPORIZADOR_INTERVALO_CADENA_HORAS": (168, "horas"),
}
TIPO_EVENTO_PARAMETROS_SISTEMA = "PARAMETROS_SISTEMA_ACTUALIZADOS"

_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ErrorParametroSistemaInvalido(Exception):
    pass


def feriados_desde_texto(texto: str) -> frozenset[date]:
    return frozenset(date.fromisoformat(f.strip()) for f in texto.split(",") if f.strip())


def _normalizar_feriados(valor: str) -> str:
    fechas = [f.strip() for f in valor.split(",") if f.strip()]
    for fecha in fechas:
        try:
            if not _FECHA.match(fecha):
                raise ValueError(fecha)
            date.fromisoformat(fecha)
        except ValueError as error:
            raise ErrorParametroSistemaInvalido(
                f"Feriados: '{fecha}' no es una fecha válida (AAAA-MM-DD)."
            ) from error
    return ",".join(fechas)


def normalizar_valor(clave: str, valor: str) -> str:
    """Valida el valor de un parametro y lo devuelve como se guarda."""
    if clave == CLAVE_FERIADOS:
        return _normalizar_feriados(valor)
    if clave not in CLAVES_NUMERICAS:
        raise ErrorParametroSistemaInvalido("Hay un parámetro que no existe.")
    texto = valor.strip()
    if not texto.isdigit() or int(texto) < 1:
        raise ErrorParametroSistemaInvalido(
            f"{_ETIQUETAS[clave]}: debe ser un número entero mayor que cero."
        )
    maximo, unidad = _MAXIMOS[clave]
    if int(texto) > maximo:
        raise ErrorParametroSistemaInvalido(
            f"{_ETIQUETAS[clave]}: debe ser como máximo {maximo} {unidad}."
        )
    return str(int(texto))


class RepositorioParametrosSistema(Protocol):
    async def vigentes(self) -> dict[str, str]: ...

    async def guardar(self, clave: str, valor: str, actor: str) -> None: ...


class ActualizarParametrosSistema:
    def __init__(
        self, repositorio: RepositorioParametrosSistema, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(
        self, cambios: dict[str, str], actor: str, usuario_id: int
    ) -> dict[str, str]:
        nuevos = {clave: normalizar_valor(clave, valor) for clave, valor in cambios.items()}
        actuales = await self._repositorio.vigentes()
        diferencias = {
            clave: {"antes": actuales[clave], "despues": valor}
            for clave, valor in nuevos.items()
            if actuales[clave] != valor
        }
        if not diferencias:
            return actuales
        for clave, valores in diferencias.items():
            await self._repositorio.guardar(clave, valores["despues"], actor)
        # Mismo patron que los parametros por IAFAS: el evento va al agregado
        # de sesion de quien hizo el cambio.
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento=TIPO_EVENTO_PARAMETROS_SISTEMA,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"cambios": diferencias},
            )
        )
        return {**actuales, **{c: v["despues"] for c, v in diferencias.items()}}
