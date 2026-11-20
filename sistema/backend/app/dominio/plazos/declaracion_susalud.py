"""Declaracion jurada de un mes sin facturacion (Resolucion
043-2025-SUSALUD/S): la clinica que no remitio lotes en el mes lo declara a
SUSALUD en el mismo plazo del reporte mensual. El sistema solo deja
constancia de que el analista la presento."""

from __future__ import annotations

from datetime import datetime

from app.dominio.plazos.susalud import ZONA_PERU, RepositorioControlSusalud, periodo_de
from app.dominio.puertos_comunes import Evento, RegistroEventos, Reloj

TIPO_EVENTO_DECLARACION = "DECLARACION_SIN_FACTURACION_REGISTRADA"


class ErrorDeclaracionSusalud(Exception):
    """Base de los rechazos al registrar la declaracion."""


class ErrorPeriodoInvalido(ErrorDeclaracionSusalud):
    pass


class ErrorPeriodoNoCerrado(ErrorDeclaracionSusalud):
    pass


class ErrorPeriodoConLotes(ErrorDeclaracionSusalud):
    pass


class ErrorPeriodoYaDeclarado(ErrorDeclaracionSusalud):
    pass


class RegistrarDeclaracionSinFacturacion:
    def __init__(
        self,
        repositorio: RepositorioControlSusalud,
        registro_eventos: RegistroEventos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos
        self._reloj = reloj

    async def ejecutar(self, periodo: str, actor: str, usuario_id: int) -> datetime:
        if not (periodo.isdigit() and len(periodo) == 6 and 1 <= int(periodo[4:]) <= 12):
            raise ErrorPeriodoInvalido(f"El periodo {periodo!r} no es AAAAMM.")
        if periodo >= periodo_de(self._reloj.ahora().astimezone(ZONA_PERU).date()):
            raise ErrorPeriodoNoCerrado(f"El periodo {periodo} aun no cierra.")
        if any(
            r.periodo == periodo and r.lotes > 0
            for r in await self._repositorio.lotes_por_periodo()
        ):
            raise ErrorPeriodoConLotes(f"El periodo {periodo} tiene lotes que reportar.")
        if periodo in await self._repositorio.declaraciones():
            raise ErrorPeriodoYaDeclarado(f"El periodo {periodo} ya tiene su declaracion.")
        registrada_en = await self._repositorio.registrar_declaracion(periodo, actor)
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                sesion_usuario_id=usuario_id,
                tipo_evento=TIPO_EVENTO_DECLARACION,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"periodo": periodo},
            )
        )
        return registrada_en
