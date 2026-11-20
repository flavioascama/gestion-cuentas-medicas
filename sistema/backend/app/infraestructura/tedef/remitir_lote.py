"""Caso de uso RemitirLote (Seccion 7.8, precondicion ajustada en la Fase
13: ver docs/MIGRACION_V2_A_V3.md, seccion 3).

Vive en infraestructura/tedef/, igual que GenerarLote: lee el archivo .S01
ya escrito en disco (operacion de filesystem, no delegable a un puerto sin
valor real), asi que no puede vivir en dominio/. Orquesta el puerto
Transmisor (que si es intercambiable de verdad: FTP hoy, otro mecanismo de
transporte manana) y los puertos comunes de siempre.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.compartido.huella import huella_sha256
from app.compartido.rutas import ruta_local_s01
from app.dominio.integracion.casos_uso import encolar_monitoreo_respuesta
from app.dominio.integracion.puertos import (
    ErrorLoteNoRemisible,
    LoteParaRemitir,
    RepositorioLoteRemision,
    ResultadoTransmision,
    Transmisor,
)
from app.dominio.integracion.vigencia_lote import exigir_lote_vigente
from app.dominio.puertos_comunes import (
    Evento,
    MedicionPaso,
    Observabilidad,
    Reloj,
    RepositorioTrabajos,
)

# Seccion 8.3, punto 1: 'proximo_intento igual al instante de remision mas
# el intervalo configurado para esa IAFAS'. El esquema de `iafas` (Seccion
# 6.1) solo tiene `periodicidad_remision_dias` (cada cuanto se remiten
# lotes) y `ventana_monitoreo_horas` (limite maximo antes de AGOTADO,
# Seccion 8.3 punto 5); ninguno de los dos es literalmente 'cada cuanto
# revisar'. Se fija aqui un primer chequeo a los 15 minutos, como supuesto
# de esta fase -- la Fase 12, que es quien de verdad consume y reencola
# este trabajo, es la que define el intervalo de reconsulta completo (y,
# si hace falta un valor por IAFAS, el campo nuevo que lo sostenga).
INTERVALO_INICIAL_MONITOREO = timedelta(minutes=15)

# Unico estado desde el que un lote puede remitirse (Seccion 7.8, punto 1,
# reescrito en la Fase 13, Seccion 3 de docs/MIGRACION_V2_A_V3.md): antes
# de la version 3 era GENERADO (el propio backend producia el .S01, asi
# que "conforme" ya bastaba); ahora el archivo lo entrega el validador
# TEDEF Web (Fase 16), asi que hace falta esperar a VALIDADO.
_ESTADO_VALIDADO = "VALIDADO"
_ESTADO_REMITIDO_IAFAS = "REMITIDO_IAFAS"


@dataclass(frozen=True, slots=True)
class ResultadoRemitirLote:
    exitosa: bool
    lote_id: int
    acuse_id: int
    motivo: str | None


@dataclass(frozen=True, slots=True)
class _IntentoRemision:
    """Objeto de parametros (GUIA_ESTILO_CODIGO.md, Seccion 2.2): lo que
    `_registrar_resultado` necesita para dejar constancia (medicion y
    evento) de un intento de remision, exitoso o no."""

    lote: LoteParaRemitir
    resultado_transmision: ResultadoTransmision
    acuse_id: int
    inicio: datetime
    fin: datetime
    cuenta_medica_ids: tuple[int, ...] = ()


class RemitirLote:
    def __init__(
        self,
        repositorio: RepositorioLoteRemision,
        transmisor: Transmisor,
        observabilidad: Observabilidad,
        repositorio_trabajos: RepositorioTrabajos,
        reloj: Reloj,
    ) -> None:
        self._repositorio = repositorio
        self._transmisor = transmisor
        self._observabilidad = observabilidad
        self._repositorio_trabajos = repositorio_trabajos
        self._reloj = reloj

    async def ejecutar(self, lote_id: int, actor: str) -> ResultadoRemitirLote:
        inicio = self._reloj.ahora()
        lote, contenido = await self._obtener_lote_verificado(lote_id)
        assert lote.nombre_s01 is not None  # ya lo verifico _obtener_lote_verificado

        resultado_transmision = await self._transmisor.transmitir(lote.nombre_s01, contenido)
        fin = self._reloj.ahora()

        acuse_id, cuenta_medica_ids = await self._repositorio.registrar_remision(
            lote_id=lote_id,
            documento_ids=lote.documento_ids,
            exitosa=resultado_transmision.exitosa,
            motivo=resultado_transmision.motivo,
            instante=fin,
        )
        await self._registrar_resultado(
            lote_id,
            actor,
            _IntentoRemision(
                lote=lote,
                resultado_transmision=resultado_transmision,
                acuse_id=acuse_id,
                inicio=inicio,
                fin=fin,
                cuenta_medica_ids=cuenta_medica_ids,
            ),
        )

        if resultado_transmision.exitosa:
            # Seccion 7.8, punto 6 / Seccion 8.3, punto 1: se inserta una
            # sola vez, en el momento de la remision exitosa. Reintentos
            # de esta misma remision (lote ya REMITIDO_IAFAS) nunca llegan
            # aqui de nuevo, porque el guard de estado del inicio de este
            # metodo ya lo impide.
            await encolar_monitoreo_respuesta(
                self._repositorio_trabajos, lote_id, actor, fin + INTERVALO_INICIAL_MONITOREO
            )

        return ResultadoRemitirLote(
            exitosa=resultado_transmision.exitosa,
            lote_id=lote_id,
            acuse_id=acuse_id,
            motivo=resultado_transmision.motivo,
        )

    async def _obtener_lote_verificado(self, lote_id: int) -> tuple[LoteParaRemitir, bytes]:
        lote = await self._repositorio.obtener_lote_para_remision(lote_id)
        if lote is None:
            raise ErrorLoteNoRemisible(f"No existe el lote {lote_id}.")
        if lote.estado != _ESTADO_VALIDADO:
            raise ErrorLoteNoRemisible(
                f"El lote {lote_id} esta en estado {lote.estado!r}; "
                f"solo se puede remitir un lote en estado {_ESTADO_VALIDADO!r}."
            )
        # Antes de transferir: no se envia un lote que ya no refleja sus cuentas.
        exigir_lote_vigente(await self._repositorio.vigencia_lote(lote_id))
        # Garantizado por RegistrarArchivoTransmision (Fase 16): ningun
        # lote llega a VALIDADO sin los tres datos del .S01 obtenido.
        assert lote.nombre_s01 is not None
        assert lote.sha256_s01 is not None
        assert lote.ruta_s01 is not None

        contenido = ruta_local_s01(lote.ruta_s01).read_bytes()
        huella_en_disco = huella_sha256(contenido)
        if huella_en_disco != lote.sha256_s01:
            # El archivo en disco no es el que devolvio el validador
            # (Regla 11 del plan v3): no se envia nada que no se pueda dar
            # por integro.
            raise ErrorLoteNoRemisible(
                f"La huella SHA-256 del archivo en disco ({huella_en_disco}) no "
                f"coincide con la registrada en el lote ({lote.sha256_s01})."
            )
        return lote, contenido

    async def _registrar_resultado(
        self, lote_id: int, actor: str, intento: _IntentoRemision
    ) -> None:
        exitosa = intento.resultado_transmision.exitosa
        await self._observabilidad.mediciones.registrar(
            MedicionPaso(
                paso="remision_lote",
                inicio=intento.inicio,
                fin=intento.fin,
                actor=actor,
                lote_id=lote_id,
                resultado="enviado" if exitosa else "error_transferencia",
                datos={"numero_lote": intento.lote.numero, "archivo": intento.lote.nombre_s01},
            )
        )
        await self._observabilidad.eventos.registrar(
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento="LOTE_REMITIDO" if exitosa else "LOTE_REMISION_FALLIDA",
                actor=actor,
                estado_previo=_ESTADO_VALIDADO,
                estado_nuevo=_ESTADO_REMITIDO_IAFAS if exitosa else _ESTADO_VALIDADO,
                datos={
                    "lote_id": lote_id,
                    "numero_lote": intento.lote.numero,
                    "acuse_id": intento.acuse_id,
                    "motivo": intento.resultado_transmision.motivo,
                },
            )
        )
        # T-03 (Seccion 5.2.4): la transicion es de cada cuenta, no solo del
        # lote (RF-16/RT-01). Sin este evento el historial de la cuenta no
        # mostraba su envio y el panel no podia medir la etapa "Enviada".
        for cuenta_medica_id in intento.cuenta_medica_ids:
            await self._observabilidad.eventos.registrar(
                Evento(
                    cuenta_medica_id=cuenta_medica_id,
                    tipo_evento="CUENTA_ENVIADA",
                    actor=actor,
                    estado_previo="FACTURADA",
                    estado_nuevo="ENVIADA",
                    datos={"lote_id": lote_id, "numero_lote": intento.lote.numero},
                )
            )
