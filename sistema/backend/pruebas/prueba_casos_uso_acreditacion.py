"""Pruebas de SolicitarVerificacionCobertura y VerificarCobertura (Seccion
8.1, CU-01) con dobles de prueba -- sin Postgres ni Playwright: eso se
verifica aparte, contra el simulador real en Docker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pytest

from app.dominio.acreditacion.casos_uso import (
    ErrorCuentaYaAcreditada,
    SolicitarVerificacionCobertura,
    VerificarCobertura,
)
from app.dominio.acreditacion.puertos import ErrorCuentaNoEncontrada
from app.dominio.acreditacion.valores import ContextoCuentaAcreditacion, ResultadoAcreditacion
from app.dominio.puertos_comunes import Evento, MedicionPaso

_CONTEXTO = ContextoCuentaAcreditacion(
    cuenta_medica_id=1, tipo_documento_paciente="1", numero_documento_paciente="81953443"
)

_RESULTADO = ResultadoAcreditacion(
    condicion_cobertura="ACREDITABLE",
    codigo_autorizacion="AUT0000001",
    tipo_documento_autorizacion="03",
    codigo_asegurado="AS81953443",
    tipo_afiliacion="1",
    plan="PLAN DE PRUEBA",
    vigente_desde=None,
    vigente_hasta=None,
    tipo_copago=None,
    monto_copago_fijo=None,
    porcentaje_coaseguro=None,
    preexistencias=[],
    ruta_evidencia="reportes/evidencia_acreditacion/1/",
)


class _RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante


@dataclass
class _RepositorioFalso:
    contexto: ContextoCuentaAcreditacion | None
    ya_acreditada: bool = False
    guardadas: list[dict[str, object]] = field(default_factory=list)

    async def obtener_contexto_cuenta(
        self, cuenta_medica_id: int
    ) -> ContextoCuentaAcreditacion | None:
        return self.contexto

    async def existe_acreditacion(self, cuenta_medica_id: int) -> bool:
        return self.ya_acreditada

    async def guardar_acreditacion(self, **kwargs: object) -> int:
        self.guardadas.append(kwargs)
        return len(self.guardadas)


@dataclass
class _RepositorioTrabajosFalso:
    encolados: list[dict[str, object]] = field(default_factory=list)

    async def encolar(
        self, tipo: str, carga_util: dict[str, object], proximo_intento: datetime
    ) -> int:
        self.encolados.append({"tipo": tipo, "carga_util": carga_util})
        return len(self.encolados)


@dataclass
class _AdaptadorFalso:
    resultado: ResultadoAcreditacion
    llamadas: list[tuple[ContextoCuentaAcreditacion, int]] = field(default_factory=list)

    async def verificar_cobertura(
        self, contexto: ContextoCuentaAcreditacion, trabajo_id: int
    ) -> ResultadoAcreditacion:
        self.llamadas.append((contexto, trabajo_id))
        return self.resultado


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


async def prueba_solicitar_verificacion_encola_un_trabajo() -> None:
    repositorio = _RepositorioFalso(contexto=_CONTEXTO)
    repositorio_trabajos = _RepositorioTrabajosFalso()
    caso_uso = SolicitarVerificacionCobertura(
        repositorio=repositorio,  # type: ignore[arg-type]
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 18, 10, 0, 0)),
    )

    await caso_uso.ejecutar(cuenta_medica_id=1, solicitado_por="ana.analista")

    assert repositorio_trabajos.encolados == [
        {
            "tipo": "CONSULTAR_COBERTURA",
            "carga_util": {"cuenta_medica_id": 1, "usuario_origen": "ana.analista"},
        }
    ]


async def prueba_solicitar_verificacion_rechaza_cuenta_inexistente() -> None:
    caso_uso = SolicitarVerificacionCobertura(
        repositorio=_RepositorioFalso(contexto=None),  # type: ignore[arg-type]
        repositorio_trabajos=_RepositorioTrabajosFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 18, 10, 0, 0)),
    )
    with pytest.raises(ErrorCuentaNoEncontrada):
        await caso_uso.ejecutar(cuenta_medica_id=99, solicitado_por="ana.analista")


async def prueba_solicitar_verificacion_rechaza_cuenta_ya_acreditada() -> None:
    caso_uso = SolicitarVerificacionCobertura(
        repositorio=_RepositorioFalso(contexto=_CONTEXTO, ya_acreditada=True),  # type: ignore[arg-type]
        repositorio_trabajos=_RepositorioTrabajosFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 18, 10, 0, 0)),
    )
    with pytest.raises(ErrorCuentaYaAcreditada):
        await caso_uso.ejecutar(cuenta_medica_id=1, solicitado_por="ana.analista")


async def prueba_verificar_cobertura_guarda_resultado_y_emite_evento() -> None:
    repositorio = _RepositorioFalso(contexto=_CONTEXTO)
    adaptador = _AdaptadorFalso(resultado=_RESULTADO)
    registro_eventos = _RegistroEventosFalso()
    registro_mediciones = _RegistroMedicionesFalso()
    caso_uso = VerificarCobertura(
        repositorio=repositorio,  # type: ignore[arg-type]
        adaptador=adaptador,  # type: ignore[arg-type]
        registro_eventos=registro_eventos,  # type: ignore[arg-type]
        registro_mediciones=registro_mediciones,  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 18, 10, 0, 0)),
    )

    acreditacion_id = await caso_uso.ejecutar(
        trabajo_id=7, cuenta_medica_id=1, actor="trabajador", usuario_origen="ana.analista"
    )

    assert acreditacion_id == 1
    assert adaptador.llamadas == [(_CONTEXTO, 7)]
    assert registro_eventos.eventos[0].tipo_evento == "COBERTURA_VERIFICADA"
    # Control C-07 (Seccion 5.2.7): el evento que registra el robot
    # ("trabajador") atribuye la solicitud al analista que la pidio.
    assert registro_eventos.eventos[0].usuario_origen == "ana.analista"
    assert registro_mediciones.mediciones[0].paso == "verificacion_cobertura"


async def prueba_verificar_cobertura_es_idempotente_si_ya_existe() -> None:
    repositorio = _RepositorioFalso(contexto=_CONTEXTO, ya_acreditada=True)
    adaptador = _AdaptadorFalso(resultado=_RESULTADO)
    caso_uso = VerificarCobertura(
        repositorio=repositorio,  # type: ignore[arg-type]
        adaptador=adaptador,  # type: ignore[arg-type]
        registro_eventos=_RegistroEventosFalso(),  # type: ignore[arg-type]
        registro_mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 18, 10, 0, 0)),
    )

    resultado = await caso_uso.ejecutar(trabajo_id=7, cuenta_medica_id=1, actor="trabajador")

    assert resultado is None
    assert adaptador.llamadas == []  # nunca vuelve a llamar al robot (Seccion 8.1: idempotencia)


async def prueba_verificar_cobertura_rechaza_cuenta_inexistente() -> None:
    caso_uso = VerificarCobertura(
        repositorio=_RepositorioFalso(contexto=None),  # type: ignore[arg-type]
        adaptador=_AdaptadorFalso(resultado=_RESULTADO),  # type: ignore[arg-type]
        registro_eventos=_RegistroEventosFalso(),  # type: ignore[arg-type]
        registro_mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 18, 10, 0, 0)),
    )
    with pytest.raises(ErrorCuentaNoEncontrada):
        await caso_uso.ejecutar(trabajo_id=7, cuenta_medica_id=99, actor="trabajador")
