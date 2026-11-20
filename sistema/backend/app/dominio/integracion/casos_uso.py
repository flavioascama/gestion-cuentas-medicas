"""Casos de uso del contexto de integracion que no tocan el sistema de
archivos (a diferencia de GenerarLote/RemitirLote, que por eso viven en
infraestructura/tedef/ -- Seccion 5.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.dominio.integracion.puertos import (
    ConsultorRespuestaReceptor,
    ErrorLoteNoMonitoreable,
    RepositorioMonitoreoRespuesta,
)
from app.dominio.integracion.puertos_validacion import RepositorioValidacionOficial
from app.dominio.puertos_comunes import (
    Evento,
    MedicionPaso,
    Observabilidad,
    Reloj,
    RepositorioTrabajos,
)

TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS = "MONITOREAR_RESPUESTA_IAFAS"

_RESULTADO_RESPONDIDO = "respondido"
_RESULTADO_SIN_RESPUESTA = "sin_respuesta"
_RESULTADO_AGOTADO = "agotado"
TIPO_EVENTO_MONITOREO_EXCEDIDO = "LOTE_MONITOREO_EXCEDIDO"
TIPO_EVENTO_MONITOREO_SOLICITADO = "LOTE_MONITOREO_SOLICITADO"
_ESTADO_REMITIDO_IAFAS = "REMITIDO_IAFAS"


async def encolar_monitoreo_respuesta(
    repositorio_trabajos: RepositorioTrabajos,
    lote_id: int,
    actor: str,
    proximo_intento: datetime,
) -> int:
    """Unico lugar que arma el trabajo de monitoreo: lo usan la remision
    (primera vez) y la reconsulta pedida por el analista."""
    return await repositorio_trabajos.encolar(
        tipo=TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS,
        # Control C-07 (Seccion 5.2.7): LOTE_ACEPTADO/LOTE_RECHAZADO los
        # registra el robot de monitoreo, mas tarde; se atribuyen a quien
        # encolo el trabajo.
        carga_util={"lote_id": lote_id, "usuario_origen": actor},
        proximo_intento=proximo_intento,
    )


@dataclass(frozen=True, slots=True)
class ResultadoMonitoreo:
    resultado: str  # 'respondido' | 'sin_respuesta' | 'agotado'
    proximo_intento: datetime | None = None  # solo si resultado == 'sin_respuesta'


@dataclass(frozen=True, slots=True)
class _MedicionMonitoreo:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo que
    `_registrar_medicion` necesita en cada uno de los tres desenlaces de
    `ejecutar` (agotado, sin respuesta, respondido)."""

    lote_id: int
    actor: str
    inicio: datetime
    fin: datetime
    resultado: str
    usuario_origen: str | None


class SolicitarMonitoreoRespuestaIafas:
    """Reconsulta pedida por el analista: el trabajo de la remision se
    agota si la IAFAS no responde en la ventana, y sin esto el lote
    quedaba REMITIDO_IAFAS para siempre."""

    def __init__(
        self,
        repositorio: RepositorioValidacionOficial,
        repositorio_trabajos: RepositorioTrabajos,
        observabilidad: Observabilidad,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._repositorio_trabajos = repositorio_trabajos
        self._observabilidad = observabilidad
        self._reloj = reloj

    async def ejecutar(self, lote_id: int, actor: str) -> int:
        estado = await self._repositorio.obtener_estado_lote(lote_id)
        if estado is None:
            raise ErrorLoteNoMonitoreable(f"No existe el lote {lote_id}.")
        if estado != _ESTADO_REMITIDO_IAFAS:
            raise ErrorLoteNoMonitoreable(
                f"El lote {lote_id} esta en estado {estado!r}; solo se puede consultar la "
                f"respuesta de un lote en estado {_ESTADO_REMITIDO_IAFAS!r}."
            )
        if await self._repositorio_trabajos.hay_sin_terminar(
            TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS, lote_id
        ):
            raise ErrorLoteNoMonitoreable(
                f"El lote {lote_id} ya tiene una consulta de la respuesta en curso."
            )
        ahora = self._reloj.ahora()
        trabajo_id = await encolar_monitoreo_respuesta(
            self._repositorio_trabajos, lote_id, actor, ahora
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento=TIPO_EVENTO_MONITOREO_SOLICITADO,
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={"lote_id": lote_id, "trabajo_id": trabajo_id},
            )
        )
        return trabajo_id


class MonitorearRespuestaIafas:
    """Seccion 8.3, CU-05/RF-07, puntos 2-5. El punto 1 (encolar la
    primera vez) ya lo hace RemitirLote (Fase 8/11); este caso de uso es
    lo que ejecuta el trabajador cada vez que toma el trabajo, ya sea la
    primera vez o en un reencolado."""

    def __init__(
        self,
        repositorio: RepositorioMonitoreoRespuesta,
        consultor: ConsultorRespuestaReceptor,
        observabilidad: Observabilidad,
        reloj: Reloj,
        intervalo_reconsulta: timedelta,
    ) -> None:
        self._repositorio = repositorio
        self._consultor = consultor
        self._observabilidad = observabilidad
        self._reloj = reloj
        self._intervalo_reconsulta = intervalo_reconsulta

    async def ejecutar(
        self,
        lote_id: int,
        trabajo_creado_en: datetime,
        actor: str,
        usuario_origen: str | None = None,
    ) -> ResultadoMonitoreo:
        inicio = self._reloj.ahora()
        contexto = await self._repositorio.obtener_contexto_lote(lote_id)
        if contexto is None:
            raise ErrorLoteNoMonitoreable(f"No existe el lote {lote_id}.")

        respuesta = await self._consultor.consultar(contexto.nombre_s01)
        ahora = self._reloj.ahora()

        if respuesta is None:
            ventana = timedelta(hours=contexto.ventana_monitoreo_horas)
            if ahora - trabajo_creado_en > ventana:
                # Seccion 8.3, punto 5: 'al superarse la ventana maxima de
                # espera... el trabajo pasa a AGOTADO'.
                await self._registrar_medicion(
                    _MedicionMonitoreo(
                        lote_id, actor, inicio, ahora, _RESULTADO_AGOTADO, usuario_origen
                    )
                )
                # CU-05: el lote queda senalado como excedido. No cambia su
                # estado (sigue REMITIDO_IAFAS: la IAFAS aun puede
                # responder); el aviso al analista es el del trabajo agotado.
                await self._observabilidad.eventos.registrar(
                    Evento(
                        cuenta_medica_id=None,
                        lote_id=lote_id,
                        tipo_evento=TIPO_EVENTO_MONITOREO_EXCEDIDO,
                        actor=actor,
                        estado_previo=None,
                        estado_nuevo=None,
                        datos={"ventana_monitoreo_horas": contexto.ventana_monitoreo_horas},
                        usuario_origen=usuario_origen,
                    )
                )
                return ResultadoMonitoreo(resultado=_RESULTADO_AGOTADO)
            # Punto 3: 'se reencola actualizando proximo_intento, sin
            # crear un trabajo nuevo'.
            await self._registrar_medicion(
                _MedicionMonitoreo(
                    lote_id, actor, inicio, ahora, _RESULTADO_SIN_RESPUESTA, usuario_origen
                )
            )
            return ResultadoMonitoreo(
                resultado=_RESULTADO_SIN_RESPUESTA,
                proximo_intento=ahora + self._intervalo_reconsulta,
            )

        acuse_id, cuenta_medica_ids = await self._repositorio.aplicar_respuesta(
            lote_id, respuesta.estado, respuesta.motivo, ahora
        )
        tipo_evento = "LOTE_ACEPTADO" if respuesta.estado == "ACEPTADO" else "LOTE_RECHAZADO"
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento=tipo_evento,
                actor=actor,
                # Tabla 69 (consistencia): el lote solo se monitorea ya
                # remitido, asi que ese es siempre su estado previo.
                estado_previo="REMITIDO_IAFAS",
                estado_nuevo=respuesta.estado,
                datos={
                    "lote_id": lote_id,
                    "acuse_id": acuse_id,
                    "motivo": respuesta.motivo,
                    "cuentas_afectadas": list(cuenta_medica_ids),
                },
                usuario_origen=usuario_origen,
            )
        )
        # T-06 (aceptado) o T-04 (rechazado), Seccion 5.2.4: ademas del
        # evento del lote de arriba, un evento propio por cada cuenta
        # (RF-16/RT-01: la transicion es de la cuenta; el repositorio ya
        # la valido contra el motor de orquestacion al aplicarla).
        aceptado = respuesta.estado == "ACEPTADO"
        for cuenta_medica_id in cuenta_medica_ids:
            await self._observabilidad.eventos.registrar(
                Evento(
                    cuenta_medica_id=cuenta_medica_id,
                    tipo_evento="CUENTA_EN_AUDITORIA" if aceptado else "CUENTA_RECHAZADA",
                    actor=actor,
                    estado_previo="ENVIADA",
                    estado_nuevo="EN_AUDITORIA" if aceptado else "RECHAZADA",
                    datos={"lote_id": lote_id, "motivo": None if aceptado else respuesta.motivo},
                    usuario_origen=usuario_origen,
                )
            )
        await self._registrar_medicion(
            _MedicionMonitoreo(lote_id, actor, inicio, ahora, _RESULTADO_RESPONDIDO, usuario_origen)
        )
        return ResultadoMonitoreo(resultado=_RESULTADO_RESPONDIDO)

    async def _registrar_medicion(self, m: _MedicionMonitoreo) -> None:
        await self._observabilidad.mediciones.registrar(
            MedicionPaso(
                paso="monitoreo_respuesta_iafas",
                inicio=m.inicio,
                fin=m.fin,
                actor=m.actor,
                lote_id=m.lote_id,
                resultado=m.resultado,
                datos={"usuario_origen": m.usuario_origen},
            )
        )
