"""Pruebas de los casos de uso del flujo de validacion oficial (Seccion
8.3, Fase 16) con dobles de prueba -- sin Postgres ni Playwright: eso se
verifica aparte, contra el simulador real en Docker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pytest

from app.dominio.integracion.casos_uso_validacion import (
    DatosArchivoTransmision,
    DatosValidacionEtapa,
    EnviarLoteSusalud,
    LoteEnvioSusalud,
    RegistrarArchivoTransmision,
    RegistrarResultadoValidador,
    SolicitarCargaEnValidador,
    SolicitarEnvioSusalud,
)
from app.dominio.integracion.puertos_validacion import (
    ArchivoLote,
    DatosRegistrarValidacion,
    ErrorLoteNoCargable,
    IdentidadLoteTedef,
    LoteParaEnvioSusalud,
    ObservacionLectura,
    ResultadoEtapaValidador,
)
from app.dominio.puertos_comunes import Evento, MedicionPaso, Observabilidad

_INSTANTE = datetime(2026, 9, 26, 9, 0, 0)


class _RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante


@dataclass
class _RepositorioValidacionFalso:
    estado_lote: str | None = "GENERADO"
    lotes_para_envio: tuple[LoteParaEnvioSusalud, ...] = ()
    validaciones: list[dict[str, object]] = field(default_factory=list)
    archivos_transmision: list[dict[str, object]] = field(default_factory=list)
    enviados_susalud: list[tuple[int, ...]] = field(default_factory=list)

    async def obtener_estado_lote(self, lote_id: int) -> str | None:
        return self.estado_lote

    async def registrar_validacion(self, datos: DatosRegistrarValidacion) -> int:
        self.validaciones.append(
            {
                "lote_id": datos.lote_id,
                "etapa": datos.etapa,
                "resultado": datos.resultado,
                "ruta": datos.ruta_reporte,
            }
        )
        return len(self.validaciones)

    async def registrar_archivo_transmision(
        self, lote_id: int, archivo: ArchivoLote, ruta_s01: str, sha256_s01: str, instante: datetime
    ) -> None:
        self.archivos_transmision.append(
            {"lote_id": lote_id, "nombre": archivo.nombre, "sha256": sha256_s01}
        )

    async def obtener_lotes_para_envio_susalud(
        self, periodo: str
    ) -> tuple[LoteParaEnvioSusalud, ...]:
        return self.lotes_para_envio

    async def marcar_enviados_susalud(self, lote_ids: tuple[int, ...], instante: datetime) -> None:
        self.enviados_susalud.append(lote_ids)


@dataclass
class _RepositorioTrabajosFalso:
    encolados: list[dict[str, object]] = field(default_factory=list)

    async def encolar(
        self, tipo: str, carga_util: dict[str, object], proximo_intento: datetime
    ) -> int:
        self.encolados.append({"tipo": tipo, "carga_util": carga_util})
        return len(self.encolados)


@dataclass
class _ValidadorFalso:
    llamadas_susalud: list[tuple[IdentidadLoteTedef, ...]] = field(default_factory=list)

    async def enviar_a_susalud(self, lotes: tuple[IdentidadLoteTedef, ...]) -> None:
        self.llamadas_susalud.append(lotes)


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@dataclass
class _RegistroMedicionesFalso:
    mediciones: list[MedicionPaso] = field(default_factory=list)

    async def registrar(self, medicion: MedicionPaso) -> None:
        self.mediciones.append(medicion)


def _observabilidad() -> tuple[Observabilidad, _RegistroEventosFalso, _RegistroMedicionesFalso]:
    eventos = _RegistroEventosFalso()
    mediciones = _RegistroMedicionesFalso()
    observabilidad = Observabilidad(  # type: ignore[arg-type]
        eventos=eventos, mediciones=mediciones
    )
    return observabilidad, eventos, mediciones


async def prueba_solicitar_carga_rechaza_lote_inexistente() -> None:
    repositorio = _RepositorioValidacionFalso(estado_lote=None)
    caso_uso = SolicitarCargaEnValidador(
        repositorio=repositorio,  # type: ignore[arg-type]
        repositorio_trabajos=_RepositorioTrabajosFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(_INSTANTE),
    )
    with pytest.raises(ErrorLoteNoCargable):
        await caso_uso.ejecutar(lote_id=99, actor="analista")


async def prueba_solicitar_carga_rechaza_lote_no_generado() -> None:
    repositorio = _RepositorioValidacionFalso(estado_lote="VALIDADO")
    caso_uso = SolicitarCargaEnValidador(
        repositorio=repositorio,  # type: ignore[arg-type]
        repositorio_trabajos=_RepositorioTrabajosFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(_INSTANTE),
    )
    with pytest.raises(ErrorLoteNoCargable):
        await caso_uso.ejecutar(lote_id=1, actor="analista")


async def prueba_solicitar_carga_encola_trabajo() -> None:
    repositorio_trabajos = _RepositorioTrabajosFalso()
    caso_uso = SolicitarCargaEnValidador(
        repositorio=_RepositorioValidacionFalso(estado_lote="GENERADO"),  # type: ignore[arg-type]
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        reloj=_RelojFijo(_INSTANTE),
    )

    trabajo_id = await caso_uso.ejecutar(lote_id=5, actor="analista")

    assert trabajo_id == 1
    assert repositorio_trabajos.encolados == [
        {
            "tipo": "CARGAR_LOTE_VALIDADOR",
            "carga_util": {"lote_id": 5, "usuario_origen": "analista"},
        }
    ]


async def prueba_registrar_resultado_forma_conforme_pone_cargado_validador() -> None:
    repositorio = _RepositorioValidacionFalso()
    observabilidad, eventos, mediciones = _observabilidad()
    caso_uso = RegistrarResultadoValidador(  # type: ignore[arg-type]
        repositorio=repositorio, observabilidad=observabilidad
    )

    await caso_uso.ejecutar(
        DatosValidacionEtapa(
            lote_id=5,
            trabajo_id=10,
            etapa="FORMA",
            estado_previo="GENERADO",
            resultado=ResultadoEtapaValidador(conforme=True, estado_informado="Registrado"),
            ruta_reporte=None,
            sha256_reporte=None,
            inicio=_INSTANTE,
            fin=_INSTANTE,
            usuario_origen="ana.analista",
        ),
        actor="trabajador_automatizacion",
    )

    assert eventos.eventos[0].tipo_evento == "LOTE_CARGADO_VALIDADOR"
    assert eventos.eventos[0].estado_nuevo == "CARGADO_VALIDADOR"
    # Control C-07 (Seccion 5.2.7).
    assert eventos.eventos[0].usuario_origen == "ana.analista"
    assert mediciones.mediciones[0].resultado == "conforme"


async def prueba_registrar_resultado_observado_pone_observado_validador() -> None:
    repositorio = _RepositorioValidacionFalso()
    observabilidad, eventos, _mediciones = _observabilidad()
    caso_uso = RegistrarResultadoValidador(  # type: ignore[arg-type]
        repositorio=repositorio, observabilidad=observabilidad
    )
    observaciones = (
        ObservacionLectura(
            tabla="T1",
            numero_linea=None,
            campo_clave=None,
            campo=None,
            valor_observado=None,
            codigo_error="SIM-001",
            descripcion="Codigo de IPRESS no asignado al usuario.",
        ),
    )

    await caso_uso.ejecutar(
        DatosValidacionEtapa(
            lote_id=5,
            trabajo_id=10,
            etapa="FORMA",
            estado_previo="GENERADO",
            resultado=ResultadoEtapaValidador(
                conforme=False, estado_informado="Observado", observaciones=observaciones
            ),
            ruta_reporte="/reportes/validacion_oficial/5_forma.xlsx",
            sha256_reporte="abc123",
            inicio=_INSTANTE,
            fin=_INSTANTE,
        ),
        actor="trabajador_automatizacion",
    )

    assert eventos.eventos[0].tipo_evento == "LOTE_OBSERVADO_VALIDADOR"
    assert eventos.eventos[0].estado_nuevo == "OBSERVADO_VALIDADOR"
    assert repositorio.validaciones[0]["ruta"] == "/reportes/validacion_oficial/5_forma.xlsx"


async def prueba_registrar_resultado_detallada_conforme_no_registra_evento() -> None:
    repositorio = _RepositorioValidacionFalso()
    observabilidad, eventos, mediciones = _observabilidad()
    caso_uso = RegistrarResultadoValidador(  # type: ignore[arg-type]
        repositorio=repositorio, observabilidad=observabilidad
    )

    await caso_uso.ejecutar(
        DatosValidacionEtapa(
            lote_id=5,
            trabajo_id=10,
            etapa="DETALLADA",
            estado_previo="CARGADO_VALIDADOR",
            resultado=ResultadoEtapaValidador(conforme=True, estado_informado="VALIDADO"),
            ruta_reporte=None,
            sha256_reporte=None,
            inicio=_INSTANTE,
            fin=_INSTANTE,
        ),
        actor="trabajador_automatizacion",
    )

    assert eventos.eventos == []
    assert mediciones.mediciones[0].resultado == "conforme"


async def prueba_registrar_archivo_transmision_persiste_y_registra_evento() -> None:
    repositorio = _RepositorioValidacionFalso()
    observabilidad, eventos, mediciones = _observabilidad()
    caso_uso = RegistrarArchivoTransmision(  # type: ignore[arg-type]
        repositorio=repositorio, observabilidad=observabilidad
    )

    await caso_uso.ejecutar(
        DatosArchivoTransmision(
            lote_id=5,
            archivo_s01=ArchivoLote(nombre="937_...S01", contenido=b"cifrado"),
            ruta_s01="/artefactos_s01/937_...S01",
            sha256_s01="deadbeef",
            inicio=_INSTANTE,
            fin=_INSTANTE,
            usuario_origen="ana.analista",
        ),
        actor="trabajador_automatizacion",
    )

    assert repositorio.archivos_transmision == [
        {"lote_id": 5, "nombre": "937_...S01", "sha256": "deadbeef"}
    ]
    assert eventos.eventos[0].tipo_evento == "LOTE_VALIDADO"
    # Control C-07 (Seccion 5.2.7).
    assert eventos.eventos[0].usuario_origen == "ana.analista"
    assert mediciones.mediciones[0].paso == "obtencion_s01"


async def prueba_solicitar_envio_susalud_sin_lotes_no_encola() -> None:
    repositorio = _RepositorioValidacionFalso(lotes_para_envio=())
    repositorio_trabajos = _RepositorioTrabajosFalso()
    caso_uso = SolicitarEnvioSusalud(
        repositorio=repositorio,  # type: ignore[arg-type]
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        reloj=_RelojFijo(_INSTANTE),
    )

    resultado = await caso_uso.ejecutar(periodo="202609", actor="analista")

    assert resultado is None
    assert repositorio_trabajos.encolados == []


async def prueba_solicitar_envio_susalud_encola_con_todos_los_lotes() -> None:
    lotes = (
        LoteParaEnvioSusalud(lote_id=1, numero="0000001", periodo="202609"),
        LoteParaEnvioSusalud(lote_id=2, numero="0000002", periodo="202609"),
    )
    repositorio = _RepositorioValidacionFalso(lotes_para_envio=lotes)
    repositorio_trabajos = _RepositorioTrabajosFalso()
    caso_uso = SolicitarEnvioSusalud(
        repositorio=repositorio,  # type: ignore[arg-type]
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        reloj=_RelojFijo(_INSTANTE),
    )

    trabajo_id = await caso_uso.ejecutar(periodo="202609", actor="analista")

    assert trabajo_id == 1
    carga_util = repositorio_trabajos.encolados[0]["carga_util"]
    assert carga_util == {  # type: ignore[comparison-overlap]
        "periodo": "202609",
        "lotes": [
            {"lote_id": 1, "numero": "0000001", "periodo": "202609"},
            {"lote_id": 2, "numero": "0000002", "periodo": "202609"},
        ],
        "usuario_origen": "analista",
    }


async def prueba_enviar_lote_susalud_marca_enviados_y_registra_eventos() -> None:
    repositorio = _RepositorioValidacionFalso()
    validador = _ValidadorFalso()
    observabilidad, eventos, mediciones = _observabilidad()
    caso_uso = EnviarLoteSusalud(
        repositorio=repositorio,  # type: ignore[arg-type]
        validador=validador,  # type: ignore[arg-type]
        observabilidad=observabilidad,
        reloj=_RelojFijo(_INSTANTE),
    )
    lotes = (
        LoteEnvioSusalud(lote_id=1, numero="0000001", periodo="202609"),
        LoteEnvioSusalud(lote_id=2, numero="0000002", periodo="202609"),
    )

    await caso_uso.ejecutar(
        lotes=lotes, periodo="202609", actor="analista", usuario_origen="ana.analista"
    )

    assert validador.llamadas_susalud == [
        (
            IdentidadLoteTedef(numero="0000001", periodo="202609"),
            IdentidadLoteTedef(numero="0000002", periodo="202609"),
        )
    ]
    assert repositorio.enviados_susalud == [(1, 2)]
    assert len(eventos.eventos) == 2
    assert {e.tipo_evento for e in eventos.eventos} == {"LOTE_ENVIADO_SUSALUD"}
    # Control C-07 (Seccion 5.2.7).
    assert {e.usuario_origen for e in eventos.eventos} == {"ana.analista"}
    assert mediciones.mediciones[0].paso == "envio_susalud"
