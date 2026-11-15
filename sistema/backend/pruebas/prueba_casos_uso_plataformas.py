"""Pruebas de SolicitarSesionPlataforma, ResponderCaptcha e
IniciarSesionPlataforma (Seccion 8.4) con dobles de prueba -- sin Postgres
ni Playwright: eso se verifica aparte, contra el simulador real en
Docker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pytest

from app.dominio.plataformas.casos_uso import (
    IniciarSesionPlataforma,
    ResponderCaptcha,
    SolicitarSesionPlataforma,
)
from app.dominio.plataformas.puertos import (
    ErrorPlataformaInvalida,
    ErrorSesionFallida,
    ErrorSesionNoEncontrada,
    ErrorSesionPlataforma,
)
from app.dominio.plataformas.valores import SesionPlataforma
from app.dominio.puertos_comunes import Evento, MedicionPaso, Observabilidad

_SESION_ACTIVA = SesionPlataforma(
    id=5,
    plataforma="acredita_salud",
    estado="ACTIVA",
    solicitada_por="analista",
    creada_en=datetime(2026, 9, 25, 9, 0, 0),
    imagen_captcha=None,
    respuesta_captcha=None,
    activa_desde=datetime(2026, 9, 25, 9, 1, 0),
    expira_en=datetime(2026, 9, 25, 9, 31, 0),
    intentos=0,
    motivo=None,
)

_SESION_ESPERANDO_CAPTCHA = SesionPlataforma(
    id=6,
    plataforma="acredita_salud",
    estado="ESPERANDO_CAPTCHA",
    solicitada_por="analista",
    creada_en=datetime(2026, 9, 25, 9, 0, 0),
    imagen_captcha=b"png-falso",
    respuesta_captcha=None,
    activa_desde=None,
    expira_en=None,
    intentos=0,
    motivo=None,
)


class _RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante


@dataclass
class _RepositorioSesionFalso:
    activa: SesionPlataforma | None = None
    por_id: dict[int, SesionPlataforma] = field(default_factory=dict)
    solicitudes: list[tuple[str, str]] = field(default_factory=list)
    respuestas: list[tuple[int, str]] = field(default_factory=list)

    async def crear_solicitud(self, plataforma: str, solicitada_por: str) -> int:
        self.solicitudes.append((plataforma, solicitada_por))
        return 42

    async def obtener(self, sesion_id: int) -> SesionPlataforma | None:
        return self.por_id.get(sesion_id)

    async def obtener_activa(self, plataforma: str) -> SesionPlataforma | None:
        return self.activa

    async def registrar_respuesta(self, sesion_id: int, respuesta: str) -> None:
        self.respuestas.append((sesion_id, respuesta))


@dataclass
class _RepositorioTrabajosFalso:
    encolados: list[dict[str, object]] = field(default_factory=list)
    reactivados: list[tuple[str, ...]] = field(default_factory=list)

    async def encolar(
        self, tipo: str, carga_util: dict[str, object], proximo_intento: datetime
    ) -> int:
        self.encolados.append({"tipo": tipo, "carga_util": carga_util})
        return len(self.encolados)

    async def reactivar_requieren_sesion(self, tipos: tuple[str, ...]) -> int:
        self.reactivados.append(tipos)
        return 3


@dataclass
class _AsistenteFalso:
    error: ErrorSesionFallida | None = None
    llamadas: list[tuple[int, str]] = field(default_factory=list)

    async def iniciar_sesion(self, sesion_id: int, plataforma: str) -> None:
        self.llamadas.append((sesion_id, plataforma))
        if self.error is not None:
            raise self.error


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


async def prueba_solicitar_sesion_rechaza_plataforma_invalida() -> None:
    caso_uso = SolicitarSesionPlataforma(
        repositorio=_RepositorioSesionFalso(),  # type: ignore[arg-type]
        repositorio_trabajos=_RepositorioTrabajosFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 25, 9, 0, 0)),
    )
    with pytest.raises(ErrorPlataformaInvalida):
        await caso_uso.ejecutar(plataforma="otra_cosa", solicitada_por="analista")


async def prueba_solicitar_sesion_crea_solicitud_y_encola_trabajo() -> None:
    repositorio = _RepositorioSesionFalso(activa=None)
    repositorio_trabajos = _RepositorioTrabajosFalso()
    caso_uso = SolicitarSesionPlataforma(
        repositorio=repositorio,  # type: ignore[arg-type]
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 25, 9, 0, 0)),
    )

    sesion_id = await caso_uso.ejecutar(plataforma="acredita_salud", solicitada_por="analista")

    assert sesion_id == 42
    assert repositorio.solicitudes == [("acredita_salud", "analista")]
    assert repositorio_trabajos.encolados == [
        {
            "tipo": "INICIAR_SESION_PLATAFORMA",
            "carga_util": {
                "sesion_id": 42,
                "plataforma": "acredita_salud",
                "usuario_origen": "analista",
            },
        }
    ]


async def prueba_solicitar_sesion_es_idempotente_si_ya_hay_una_activa() -> None:
    repositorio = _RepositorioSesionFalso(activa=_SESION_ACTIVA)
    repositorio_trabajos = _RepositorioTrabajosFalso()
    caso_uso = SolicitarSesionPlataforma(
        repositorio=repositorio,  # type: ignore[arg-type]
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 25, 9, 0, 0)),
    )

    sesion_id = await caso_uso.ejecutar(plataforma="acredita_salud", solicitada_por="analista")

    assert sesion_id == _SESION_ACTIVA.id
    assert repositorio.solicitudes == []
    assert repositorio_trabajos.encolados == []


async def prueba_responder_captcha_rechaza_sesion_inexistente() -> None:
    caso_uso = ResponderCaptcha(repositorio=_RepositorioSesionFalso())  # type: ignore[arg-type]
    with pytest.raises(ErrorSesionNoEncontrada):
        await caso_uso.ejecutar(sesion_id=99, respuesta="ABCDE")


async def prueba_responder_captcha_rechaza_sesion_en_otro_estado() -> None:
    repositorio = _RepositorioSesionFalso(por_id={_SESION_ACTIVA.id: _SESION_ACTIVA})
    caso_uso = ResponderCaptcha(repositorio=repositorio)  # type: ignore[arg-type]
    with pytest.raises(ErrorSesionPlataforma):
        await caso_uso.ejecutar(sesion_id=_SESION_ACTIVA.id, respuesta="ABCDE")


async def prueba_responder_captcha_registra_la_respuesta() -> None:
    repositorio = _RepositorioSesionFalso(
        por_id={_SESION_ESPERANDO_CAPTCHA.id: _SESION_ESPERANDO_CAPTCHA}
    )
    caso_uso = ResponderCaptcha(repositorio=repositorio)  # type: ignore[arg-type]

    await caso_uso.ejecutar(sesion_id=_SESION_ESPERANDO_CAPTCHA.id, respuesta="abcde")

    assert repositorio.respuestas == [(_SESION_ESPERANDO_CAPTCHA.id, "abcde")]


async def prueba_iniciar_sesion_reactiva_trabajos_y_registra_medicion() -> None:
    repositorio_trabajos = _RepositorioTrabajosFalso()
    registro_eventos = _RegistroEventosFalso()
    registro_mediciones = _RegistroMedicionesFalso()
    caso_uso = IniciarSesionPlataforma(
        repositorio=_RepositorioSesionFalso(),  # type: ignore[arg-type]
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        asistente=_AsistenteFalso(),  # type: ignore[arg-type]
        observabilidad=Observabilidad(eventos=registro_eventos, mediciones=registro_mediciones),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 25, 9, 0, 0)),
    )

    await caso_uso.ejecutar(
        sesion_id=7,
        plataforma="acredita_salud",
        actor="analista",
        tipos_trabajo_dependientes=("CONSULTAR_COBERTURA",),
        usuario_origen="ana.analista",
    )

    assert repositorio_trabajos.reactivados == [("CONSULTAR_COBERTURA",)]
    assert registro_eventos.eventos[0].tipo_evento == "SESION_PLATAFORMA_ACTIVA"
    # Control C-07 (Seccion 5.2.7).
    assert registro_eventos.eventos[0].usuario_origen == "ana.analista"
    assert registro_mediciones.mediciones[0].paso == "inicio_sesion_plataforma"
    assert registro_mediciones.mediciones[0].resultado == "activa"


async def prueba_iniciar_sesion_no_reactiva_nada_si_no_hay_tipos_dependientes() -> None:
    repositorio_trabajos = _RepositorioTrabajosFalso()
    caso_uso = IniciarSesionPlataforma(
        repositorio=_RepositorioSesionFalso(),  # type: ignore[arg-type]
        repositorio_trabajos=repositorio_trabajos,  # type: ignore[arg-type]
        asistente=_AsistenteFalso(),  # type: ignore[arg-type]
        observabilidad=Observabilidad(
            eventos=_RegistroEventosFalso(), mediciones=_RegistroMedicionesFalso()
        ),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 25, 9, 0, 0)),
    )

    await caso_uso.ejecutar(
        sesion_id=7, plataforma="tedef_web", actor="analista", tipos_trabajo_dependientes=()
    )

    assert repositorio_trabajos.reactivados == []


async def prueba_iniciar_sesion_registra_fallo_y_relanza() -> None:
    registro_eventos = _RegistroEventosFalso()
    registro_mediciones = _RegistroMedicionesFalso()
    asistente = _AsistenteFalso(error=ErrorSesionFallida("Se agotaron los intentos de CAPTCHA."))
    caso_uso = IniciarSesionPlataforma(
        repositorio=_RepositorioSesionFalso(),  # type: ignore[arg-type]
        repositorio_trabajos=_RepositorioTrabajosFalso(),  # type: ignore[arg-type]
        asistente=asistente,  # type: ignore[arg-type]
        observabilidad=Observabilidad(eventos=registro_eventos, mediciones=registro_mediciones),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 25, 9, 0, 0)),
    )

    with pytest.raises(ErrorSesionFallida):
        await caso_uso.ejecutar(
            sesion_id=7,
            plataforma="acredita_salud",
            actor="analista",
            tipos_trabajo_dependientes=(),
        )

    assert registro_eventos.eventos[0].tipo_evento == "SESION_PLATAFORMA_FALLIDA"
    assert registro_mediciones.mediciones[0].resultado == "fallida"
