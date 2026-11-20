"""Pruebas unitarias de la importacion de la atencion del sistema
hospitalario (2026-11-19), con dobles en memoria."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, time
from decimal import Decimal

import pytest

from app.dominio.farmacia.dispensacion import ProductoCatalogo
from app.dominio.integracion.atencion_hospitalaria import (
    AtencionHospitalaria,
    CopagoAtencion,
    CuentaImportada,
    ErrorAtencionInvalida,
    ErrorAtencionNoEncontrada,
    ErrorAtencionYaImportada,
    ErrorSistemaHospitalarioNoDisponible,
    HospitalizacionAtencion,
    PacienteAtencion,
    ProcedimientoAtencion,
    ProductoAtencion,
    ProfesionalAtencion,
    ResumenAtencionHospitalaria,
)
from app.dominio.integracion.casos_uso_importacion import (
    ImportarAtencion,
    ImportarAtencionDelSistema,
    ListarAtencionesHospitalarias,
)
from app.dominio.puertos_comunes import Evento

GTIN = "7750000000017"


def atencion_de_prueba(**cambios: object) -> AtencionHospitalaria:
    base = AtencionHospitalaria(
        atencion_id="AT-2026-000123",
        tipo_atencion="AMBULATORIA",
        fecha_prestacion=date(2026, 11, 18),
        hora_prestacion=time(10, 30),
        numero_historia_clinica="00045871",
        paciente=PacienteAtencion("1", "81953443", "Elvira", "Ochoa Canas"),
        iafas_codigo="20001",
        profesional=ProfesionalAtencion("045871", "Luis Paredes Soto"),
        diagnostico_principal_cie10="A072",
        diagnosticos_secundarios_cie10=("E119",),
        hospitalizacion=None,
        procedimientos=(
            ProcedimientoAtencion(
                "hemograma completo", "LABORATORIO", 1, Decimal("35.00"), date(2026, 11, 18)
            ),
            ProcedimientoAtencion(
                "consulta medica", "PROCEDIMIENTO", 1, Decimal("80.00"), date(2026, 11, 18)
            ),
        ),
        farmacia=(ProductoAtencion(GTIN, Decimal("2"), "1", Decimal("12.50"), date(2026, 11, 18)),),
        copago_cobrado=CopagoAtencion(Decimal("20.00"), "REC-001", date(2026, 11, 18)),
    )
    return replace(base, **cambios)  # type: ignore[arg-type]


class RepositorioFalso:
    def __init__(self) -> None:
        self.importadas: dict[str, int] = {}
        self.creada: CuentaImportada | None = None

    async def cuenta_de_atencion(self, atencion_id: str) -> int | None:
        return self.importadas.get(atencion_id)

    async def atenciones_importadas(self, atencion_ids: list[str]) -> set[str]:
        return {a for a in atencion_ids if a in self.importadas}

    async def iafas_por_codigo(self, codigo: str) -> int | None:
        return 7 if codigo == "20001" else None

    async def cie10_desconocidos(self, codigos: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(c for c in codigos if c not in {"A072", "E119", "J189"})

    async def producto_vigente(self, codigo: str) -> ProductoCatalogo | None:
        if codigo != GTIN:
            return None
        return ProductoCatalogo(codigo, "M", "Paracetamol", "paracetamol", None, None, 1)

    async def crear_cuenta_importada(self, cuenta: CuentaImportada) -> int:
        self.creada = cuenta
        self.importadas[cuenta.atencion.atencion_id] = 99
        return 99


class EventosFalsos:
    def __init__(self) -> None:
        self.eventos: list[Evento] = []

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


class FuenteFalsa:
    def __init__(self, atencion: AtencionHospitalaria | None, caida: bool = False) -> None:
        self._atencion = atencion
        self._caida = caida

    async def listar(self, documento: str | None) -> list[ResumenAtencionHospitalaria]:
        if self._caida:
            raise ErrorSistemaHospitalarioNoDisponible("no responde")
        return [
            ResumenAtencionHospitalaria(a, "AMBULATORIA", date(2026, 11, 18), _PACIENTE, "20001")
            for a in ("AT-1", "AT-2")
        ]

    async def obtener(self, atencion_id: str) -> AtencionHospitalaria | None:
        if self._caida:
            raise ErrorSistemaHospitalarioNoDisponible("no responde")
        return self._atencion


_PACIENTE = PacienteAtencion("1", "81953443", "Elvira", "Ochoa")


def _caso() -> tuple[ImportarAtencion, RepositorioFalso, EventosFalsos]:
    repositorio, eventos = RepositorioFalso(), EventosFalsos()
    return ImportarAtencion(repositorio, eventos), repositorio, eventos  # type: ignore[arg-type]


async def prueba_importa_la_atencion_por_archivo_con_eventos_sin_datos_clinicos() -> None:
    caso, repositorio, eventos = _caso()

    cuenta_id = await caso.ejecutar(atencion_de_prueba(), "archivo", "analista.prueba")

    assert cuenta_id == 99
    assert repositorio.creada is not None
    assert repositorio.creada.iafas_id == 7
    assert repositorio.creada.productos[0].monto_presentado == Decimal("25.00")
    assert repositorio.creada.productos[0].datos.exento_igv == "A"
    assert [e.tipo_evento for e in eventos.eventos] == ["CUENTA_REGISTRADA", "ATENCION_IMPORTADA"]
    assert eventos.eventos[0].estado_nuevo == "REGISTRADA"
    assert eventos.eventos[1].datos == {
        "atencion_id": "AT-2026-000123",
        "via": "archivo",
        "procedimientos": 2,
        "productos": 1,
    }


async def prueba_importa_por_consulta_desde_el_sistema_hospitalario() -> None:
    caso, _, eventos = _caso()
    via_consulta = ImportarAtencionDelSistema(FuenteFalsa(atencion_de_prueba()), caso)  # type: ignore[arg-type]

    assert await via_consulta.ejecutar("AT-2026-000123", "analista.prueba") == 99
    assert eventos.eventos[1].datos["via"] == "consulta"


async def prueba_atencion_inexistente_en_el_sistema_hospitalario() -> None:
    caso, _, _ = _caso()
    via_consulta = ImportarAtencionDelSistema(FuenteFalsa(None), caso)  # type: ignore[arg-type]

    with pytest.raises(ErrorAtencionNoEncontrada):
        await via_consulta.ejecutar("AT-X", "analista.prueba")


async def prueba_sistema_hospitalario_caido() -> None:
    caso, repositorio, _ = _caso()
    fuente = FuenteFalsa(None, caida=True)

    with pytest.raises(ErrorSistemaHospitalarioNoDisponible):
        await ImportarAtencionDelSistema(fuente, caso).ejecutar("AT-1", "a")  # type: ignore[arg-type]
    with pytest.raises(ErrorSistemaHospitalarioNoDisponible):
        await ListarAtencionesHospitalarias(fuente, repositorio).ejecutar(None)  # type: ignore[arg-type]


async def prueba_atencion_repetida_devuelve_la_cuenta_existente() -> None:
    caso, repositorio, eventos = _caso()
    await caso.ejecutar(atencion_de_prueba(), "archivo", "analista.prueba")

    with pytest.raises(ErrorAtencionYaImportada) as error:
        await caso.ejecutar(atencion_de_prueba(), "consulta", "analista.prueba")

    assert error.value.cuenta_id == 99
    assert len(eventos.eventos) == 2


async def prueba_la_lista_quita_las_atenciones_ya_importadas() -> None:
    repositorio = RepositorioFalso()
    repositorio.importadas["AT-1"] = 5

    atenciones = await ListarAtencionesHospitalarias(FuenteFalsa(None), repositorio).ejecutar(  # type: ignore[arg-type]
        " 81953443 "
    )

    assert [a.atencion_id for a in atenciones] == ["AT-2"]


_HOSPITALIZACION = HospitalizacionAtencion(date(2026, 11, 18), date(2026, 11, 21))
_PROCEDIMIENTO = ProcedimientoAtencion(
    "cama", "PROCEDIMIENTO", 1, Decimal("10"), date(2026, 11, 18)
)


@pytest.mark.parametrize(
    ("cambios", "codigo"),
    [
        ({"iafas_codigo": "99999"}, "IAFAS_DESCONOCIDA"),
        ({"diagnostico_principal_cie10": "Z999"}, "CIE10_DESCONOCIDO"),
        ({"diagnosticos_secundarios_cie10": ("X000",)}, "CIE10_DESCONOCIDO"),
        (
            {
                "farmacia": (
                    ProductoAtencion("1", Decimal("1"), "1", Decimal("1"), date(2026, 11, 18)),
                )
            },
            "PRODUCTO_FUERA_DE_CATALOGO",
        ),
        (
            {
                "farmacia": (
                    ProductoAtencion(GTIN, Decimal("1"), "1", Decimal("1"), date(2026, 11, 1)),
                )
            },
            "PRODUCTO_INVALIDO",
        ),
        ({"tipo_atencion": "HOSPITALIZACION"}, "HOSPITALIZACION_INVALIDA"),
        (
            {
                "tipo_atencion": "HOSPITALIZACION",
                "hospitalizacion": HospitalizacionAtencion(date(2026, 11, 18), None),
            },
            "HOSPITALIZACION_INVALIDA",
        ),
        (
            {
                "tipo_atencion": "HOSPITALIZACION",
                "hospitalizacion": HospitalizacionAtencion(date(2026, 11, 20), date(2026, 11, 19)),
            },
            "HOSPITALIZACION_INVALIDA",
        ),
        (
            {
                "tipo_atencion": "HOSPITALIZACION",
                "hospitalizacion": HospitalizacionAtencion(date(2026, 11, 17), date(2026, 11, 19)),
            },
            "HOSPITALIZACION_INVALIDA",
        ),
        ({"hospitalizacion": _HOSPITALIZACION}, "HOSPITALIZACION_INVALIDA"),
        ({"procedimientos": ()}, "ATENCION_SIN_PROCEDIMIENTOS"),
        ({"procedimientos": (replace(_PROCEDIMIENTO, cantidad=0),)}, "PROCEDIMIENTO_INVALIDO"),
        (
            {"procedimientos": (replace(_PROCEDIMIENTO, monto_unitario=Decimal("0")),)},
            "PROCEDIMIENTO_INVALIDO",
        ),
        ({"procedimientos": (replace(_PROCEDIMIENTO, area="FARMACIA"),)}, "PROCEDIMIENTO_INVALIDO"),
        ({"tipo_atencion": "DOMICILIARIA"}, "TIPO_ATENCION_INVALIDO"),
        ({"numero_historia_clinica": "123456789"}, "HISTORIA_CLINICA_INVALIDA"),
        ({"profesional": ProfesionalAtencion("CMP-1", "X")}, "PROFESIONAL_INVALIDO"),
        (
            {"copago_cobrado": CopagoAtencion(Decimal("0"), "R", date(2026, 11, 18))},
            "COPAGO_INVALIDO",
        ),
    ],
)
async def prueba_cada_validacion_rechaza_sin_crear_nada(
    cambios: dict[str, object], codigo: str
) -> None:
    caso, repositorio, eventos = _caso()

    with pytest.raises(ErrorAtencionInvalida) as error:
        await caso.ejecutar(atencion_de_prueba(**cambios), "archivo", "analista.prueba")

    assert error.value.codigo == codigo
    assert repositorio.creada is None
    assert eventos.eventos == []


async def prueba_hospitalizacion_coherente_se_importa() -> None:
    caso, repositorio, _ = _caso()

    await caso.ejecutar(
        atencion_de_prueba(tipo_atencion="HOSPITALIZACION", hospitalizacion=_HOSPITALIZACION),
        "archivo",
        "analista.prueba",
    )

    assert repositorio.creada is not None
    assert repositorio.creada.atencion.hospitalizacion == _HOSPITALIZACION
