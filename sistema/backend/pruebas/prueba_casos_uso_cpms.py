"""Pruebas de SugerirCodigoCpms y ConfirmarCodigoCpms (Seccion 8.2) con un
motor y un repositorio falsos -- sin scikit-learn ni Postgres, solo la
logica de orquestacion: cuando corresponde coincidencia exacta, cuando se
delega al motor, y que un codigo inexistente se rechace."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.dominio.cpms.casos_uso import (
    ConfirmacionCodigoCpms,
    ConfirmarCodigoCpms,
    ErrorCuentaNoCodificable,
    SugerirCodigoCpms,
)
from app.dominio.cpms.puertos import DatosConfirmacionCodigo, ErrorCodigoCpmsInexistente
from app.dominio.cpms.valores import CandidatoCpms, FiltrosSugerencia
from app.dominio.puertos_comunes import MedicionPaso

_VERSION_ID = 1
_VERSION_ETIQUETA = "2023-06-05"


def _candidato(codigo: str, posicion: int = 1, puntaje: float = 0.9) -> CandidatoCpms:
    return CandidatoCpms(
        codigo=codigo,
        denominacion=f"Procedimiento {codigo}",
        codigo_grupo="1",
        nombre_grupo="Grupo",
        codigo_seccion="10",
        nombre_seccion="Seccion",
        codigo_subseccion="100",
        nombre_subseccion="Subseccion",
        puntaje=puntaje,
        posicion=posicion,
    )


class _RelojFijo:
    def __init__(self, instante: datetime) -> None:
        self._instante = instante

    def ahora(self) -> datetime:
        return self._instante


@dataclass
class _RegistroMedicionesFalso:
    mediciones: list[MedicionPaso] = field(default_factory=list)

    async def registrar(self, medicion: MedicionPaso) -> None:
        self.mediciones.append(medicion)


@dataclass
class _MotorFalso:
    respuesta: tuple[CandidatoCpms, ...]
    llamadas: list[tuple[str, FiltrosSugerencia, int]] = field(default_factory=list)

    def sugerir(
        self, descripcion_normalizada: str, filtros: FiltrosSugerencia, maximo: int
    ) -> tuple[CandidatoCpms, ...]:
        self.llamadas.append((descripcion_normalizada, filtros, maximo))
        return self.respuesta


@dataclass
class _RepositorioFalso:
    codigos_existentes: dict[str, CandidatoCpms]
    confirmaciones: list[DatosConfirmacionCodigo] = field(default_factory=list)

    async def version_vigente(self) -> tuple[int, str]:
        return _VERSION_ID, _VERSION_ETIQUETA

    async def obtener_candidato(self, cpms_version_id: int, codigo: str) -> CandidatoCpms | None:
        return self.codigos_existentes.get(codigo)

    async def confirmar_codigo(self, datos: DatosConfirmacionCodigo) -> int:
        self.confirmaciones.append(datos)
        return len(self.confirmaciones)


async def prueba_sugerir_con_codigo_existente_no_consulta_al_motor() -> None:
    candidato = _candidato("00100")
    repositorio = _RepositorioFalso(codigos_existentes={"00100": candidato})
    motor = _MotorFalso(respuesta=())
    caso_uso = SugerirCodigoCpms(
        motor=motor,  # type: ignore[arg-type]
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 16, 10, 0, 0)),
    )

    resultado = await caso_uso.ejecutar(
        "00100", FiltrosSugerencia(), actor="prueba", cuenta_medica_id=1
    )

    assert resultado.coincidencia_exacta is True
    assert resultado.candidatos == (candidato,)
    assert motor.llamadas == []


async def prueba_sugerir_con_codigo_inexistente_delega_al_motor() -> None:
    candidatos_motor = (_candidato("00100"), _candidato("00120", posicion=2))
    repositorio = _RepositorioFalso(codigos_existentes={})
    motor = _MotorFalso(respuesta=candidatos_motor)
    caso_uso = SugerirCodigoCpms(
        motor=motor,  # type: ignore[arg-type]
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 16, 10, 0, 0)),
    )

    resultado = await caso_uso.ejecutar(
        "00999", FiltrosSugerencia(), actor="prueba", cuenta_medica_id=1
    )

    assert resultado.coincidencia_exacta is False
    assert resultado.candidatos == candidatos_motor
    assert len(motor.llamadas) == 1


async def prueba_sugerir_con_texto_libre_delega_al_motor() -> None:
    repositorio = _RepositorioFalso(codigos_existentes={})
    motor = _MotorFalso(respuesta=(_candidato("00100"),))
    caso_uso = SugerirCodigoCpms(
        motor=motor,  # type: ignore[arg-type]
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 16, 10, 0, 0)),
    )

    resultado = await caso_uso.ejecutar(
        "Anestesia para glandulas salivales",
        FiltrosSugerencia(),
        actor="prueba",
        cuenta_medica_id=1,
    )

    assert resultado.coincidencia_exacta is False
    assert len(motor.llamadas) == 1


async def prueba_sugerir_mide_el_paso_del_sistema() -> None:
    repositorio = _RepositorioFalso(codigos_existentes={"00100": _candidato("00100")})
    registro_mediciones = _RegistroMedicionesFalso()
    caso_uso = SugerirCodigoCpms(
        motor=_MotorFalso(respuesta=()),  # type: ignore[arg-type]
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=registro_mediciones,  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 16, 10, 0, 0)),
    )

    await caso_uso.ejecutar("00100", FiltrosSugerencia(), actor="prueba", cuenta_medica_id=7)

    assert len(registro_mediciones.mediciones) == 1
    assert registro_mediciones.mediciones[0].paso == "codificacion_sistema"
    assert registro_mediciones.mediciones[0].cuenta_medica_id == 7


async def prueba_confirmar_codigo_existente_persiste_y_mide_duracion_total() -> None:
    candidato = _candidato("00100")
    repositorio = _RepositorioFalso(codigos_existentes={"00100": candidato})
    registro_mediciones = _RegistroMedicionesFalso()
    reloj = _RelojFijo(datetime(2026, 9, 16, 10, 5, 0))
    caso_uso = ConfirmarCodigoCpms(
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=registro_mediciones,  # type: ignore[arg-type]
        reloj=reloj,
    )
    inicio_sugerencia = datetime(2026, 9, 16, 10, 0, 0)

    id_creado = await caso_uso.ejecutar(
        ConfirmacionCodigoCpms(
            cuenta_medica_id=7,
            descripcion_registrada="Anestesia para glandulas salivales",
            codigo_elegido="00100",
            posicion_aceptada=1,
            usuario_confirmo_id=3,
            cantidad=1,
            monto_unitario=Decimal("50.00"),
            fecha=date(2026, 9, 16),
        ),
        actor="prueba",
        inicio_sugerencia=inicio_sugerencia,
    )

    assert id_creado == 1
    assert repositorio.confirmaciones[0].codigo_asignado == "00100"
    assert repositorio.confirmaciones[0].posicion_aceptada == 1
    assert repositorio.confirmaciones[0].cpms_version_id == _VERSION_ID

    assert len(registro_mediciones.mediciones) == 1
    medicion = registro_mediciones.mediciones[0]
    assert medicion.paso == "codificacion_total"
    assert medicion.inicio == inicio_sugerencia  # la duracion total incluye la espera humana
    assert medicion.fin == reloj.ahora()


async def prueba_confirmar_codigo_inexistente_se_rechaza_sin_persistir() -> None:
    repositorio = _RepositorioFalso(codigos_existentes={})
    caso_uso = ConfirmarCodigoCpms(
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 16, 10, 5, 0)),
    )

    with pytest.raises(ErrorCodigoCpmsInexistente):
        await caso_uso.ejecutar(
            ConfirmacionCodigoCpms(
                cuenta_medica_id=7,
                descripcion_registrada="codigo que no existe",
                codigo_elegido="99999",
                posicion_aceptada=None,
                usuario_confirmo_id=3,
                cantidad=1,
                monto_unitario=Decimal("1.00"),
                fecha=date(2026, 9, 16),
            ),
            actor="prueba",
            inicio_sugerencia=datetime(2026, 9, 16, 10, 0, 0),
        )
    assert repositorio.confirmaciones == []


class _EstadoCuentaFijo:
    def __init__(self, estado: str) -> None:
        self._estado = estado

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self._estado

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        raise AssertionError("no se usa")


@pytest.mark.parametrize("estado", ["FACTURADA", "ENVIADA", "CERRADA", "ANULADA"])
async def prueba_no_se_codifica_una_cuenta_fuera_de_los_estados_codificables(
    estado: str,
) -> None:
    """Tabla 69: nada despues de CERRADA o ANULADA, ni sobre una cuenta ya
    facturada o en manos de la IAFAS."""
    repositorio = _RepositorioFalso(codigos_existentes={})
    caso_uso = ConfirmarCodigoCpms(
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=_RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=_RelojFijo(datetime(2026, 9, 16, 10, 5, 0)),
        estado_cuenta=_EstadoCuentaFijo(estado),
    )
    with pytest.raises(ErrorCuentaNoCodificable):
        await caso_uso.ejecutar(
            ConfirmacionCodigoCpms(
                cuenta_medica_id=7,
                descripcion_registrada="consulta",
                codigo_elegido="99201",
                posicion_aceptada=None,
                usuario_confirmo_id=3,
                cantidad=1,
                monto_unitario=Decimal("1.00"),
                fecha=date(2026, 9, 16),
            ),
            actor="prueba",
            inicio_sugerencia=datetime(2026, 9, 16, 10, 0, 0),
        )
    assert repositorio.confirmaciones == []
