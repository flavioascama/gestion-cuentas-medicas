"""Pruebas unitarias de la adenda de ingesta y completitud, con repositorios
falsos en memoria (Seccion 12.1: no dependen de una base de datos)."""

from __future__ import annotations

from datetime import date, time

import pytest

from app.dominio.integracion.casos_uso_ingesta import (
    ConsultarCompletitudCuenta,
    RegistrarCuentaMedica,
)
from app.dominio.integracion.puertos_ingesta import (
    AseguradoRegistrado,
    DatosNuevaCuenta,
    ErrorIafasInexistente,
    EstadoPiezasCuenta,
    RepositorioCompletitudCuenta,
    RepositorioIngestaCuentas,
)
from app.dominio.puertos_comunes import Evento, RegistroEventos


class RepositorioIngestaFalso(RepositorioIngestaCuentas):
    def __init__(self, iafas_validas: set[int] | None = None) -> None:
        self.creada: DatosNuevaCuenta | None = None
        self._iafas_validas = iafas_validas if iafas_validas is not None else {1}

    async def crear_cuenta(self, datos: DatosNuevaCuenta) -> int:
        if datos.iafas_id not in self._iafas_validas:
            raise ErrorIafasInexistente(datos.iafas_id)
        self.creada = datos
        return 42

    async def buscar_asegurado(
        self, tipo_documento: str, numero_documento: str
    ) -> AseguradoRegistrado | None:
        return None


class RepositorioCompletitudFalso(RepositorioCompletitudCuenta):
    def __init__(self, estado: EstadoPiezasCuenta | None) -> None:
        self._estado = estado
        self.veces_marcada_facturada = 0

    async def obtener_estado_piezas(self, cuenta_id: int) -> EstadoPiezasCuenta | None:
        return self._estado

    async def marcar_facturada(self, cuenta_id: int) -> None:
        self.veces_marcada_facturada += 1
        assert self._estado is not None
        self._estado = EstadoPiezasCuenta(
            estado_cuenta="FACTURADA",
            tiene_acreditacion=self._estado.tiene_acreditacion,
            cantidad_procedimientos=self._estado.cantidad_procedimientos,
            tiene_comprobante=self._estado.tiene_comprobante,
        )


class RegistroEventosFalso(RegistroEventos):
    def __init__(self) -> None:
        self.eventos: list[Evento] = []

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


def _datos_cuenta(iafas_id: int = 1) -> DatosNuevaCuenta:
    return DatosNuevaCuenta(
        tipo_documento_asegurado="1",
        numero_documento_asegurado="12345678",
        nombres_asegurado="Ana",
        apellidos_asegurado="Perez",
        iafas_id=iafas_id,
        fecha_prestacion=date(2026, 9, 27),
        hora_prestacion=time(9, 0, 0),
        diagnostico_principal_cie10=None,
    )


async def prueba_registrar_cuenta_persiste_y_registra_evento() -> None:
    repositorio = RepositorioIngestaFalso()
    eventos = RegistroEventosFalso()
    caso_uso = RegistrarCuentaMedica(repositorio, eventos)

    cuenta_id = await caso_uso.ejecutar(_datos_cuenta(), "ana.analista")

    assert cuenta_id == 42
    assert repositorio.creada is not None
    assert len(eventos.eventos) == 1
    assert eventos.eventos[0].tipo_evento == "CUENTA_REGISTRADA"
    assert eventos.eventos[0].cuenta_medica_id == 42
    assert eventos.eventos[0].estado_nuevo == "REGISTRADA"


async def prueba_registrar_cuenta_con_iafas_inexistente_falla() -> None:
    repositorio = RepositorioIngestaFalso(iafas_validas=set())
    caso_uso = RegistrarCuentaMedica(repositorio, RegistroEventosFalso())

    with pytest.raises(ErrorIafasInexistente):
        await caso_uso.ejecutar(_datos_cuenta(iafas_id=999), "ana.analista")


async def prueba_completitud_de_cuenta_inexistente_devuelve_none() -> None:
    repositorio = RepositorioCompletitudFalso(None)
    caso_uso = ConsultarCompletitudCuenta(repositorio)

    assert await caso_uso.ejecutar(999) is None


async def prueba_completitud_reporta_piezas_faltantes_sin_transicionar() -> None:
    estado = EstadoPiezasCuenta(
        estado_cuenta="REGISTRADA",
        tiene_acreditacion=False,
        cantidad_procedimientos=0,
        tiene_comprobante=False,
    )
    repositorio = RepositorioCompletitudFalso(estado)
    caso_uso = ConsultarCompletitudCuenta(repositorio)

    resultado = await caso_uso.ejecutar(1)

    assert resultado is not None
    assert resultado.estado_cuenta == "REGISTRADA"
    assert resultado.completa is False
    assert repositorio.veces_marcada_facturada == 0
    pieza_cobertura = next(p for p in resultado.piezas if p.clave == "cobertura")
    assert pieza_cobertura.completa is False
    assert pieza_cobertura.accion == "verificar_cobertura"
    pieza_codificacion = next(p for p in resultado.piezas if p.clave == "codificacion")
    assert pieza_codificacion.accion == "codificar"
    pieza_comprobante = next(p for p in resultado.piezas if p.clave == "comprobante")
    assert pieza_comprobante.accion == "emitir_comprobante"


async def prueba_completitud_reporta_cobertura_incompleta_si_el_asegurado_no_es_acreditable() -> (
    None
):
    estado = EstadoPiezasCuenta(
        estado_cuenta="REGISTRADA",
        tiene_acreditacion=True,
        cantidad_procedimientos=2,
        tiene_comprobante=True,
        acreditable=False,
    )
    repositorio = RepositorioCompletitudFalso(estado)
    caso_uso = ConsultarCompletitudCuenta(repositorio)

    resultado = await caso_uso.ejecutar(1)

    assert resultado is not None
    assert resultado.estado_cuenta == "REGISTRADA"
    assert resultado.completa is False
    assert repositorio.veces_marcada_facturada == 0


async def prueba_completitud_de_una_cuenta_completa_solo_lee() -> None:
    """2026-11-19: consultar ya no factura. Una cuenta REGISTRADA con todas
    sus piezas (las que quedaron asi antes del cambio) se reporta completa
    y sigue REGISTRADA; la regulariza herramientas/facturar_cuentas_completas."""

    estado = EstadoPiezasCuenta(
        estado_cuenta="REGISTRADA",
        tiene_acreditacion=True,
        cantidad_procedimientos=2,
        tiene_comprobante=True,
    )
    repositorio = RepositorioCompletitudFalso(estado)
    caso_uso = ConsultarCompletitudCuenta(repositorio)

    resultado = await caso_uso.ejecutar(1)

    assert resultado is not None
    assert resultado.estado_cuenta == "REGISTRADA"
    assert resultado.completa is True
    assert repositorio.veces_marcada_facturada == 0


async def prueba_completitud_devuelve_el_estado_que_tiene_la_cuenta() -> None:
    estado = EstadoPiezasCuenta(
        estado_cuenta="FACTURADA",
        tiene_acreditacion=True,
        cantidad_procedimientos=1,
        tiene_comprobante=True,
    )
    repositorio = RepositorioCompletitudFalso(estado)
    caso_uso = ConsultarCompletitudCuenta(repositorio)

    resultado = await caso_uso.ejecutar(1)

    assert resultado is not None
    assert resultado.estado_cuenta == "FACTURADA"
    assert repositorio.veces_marcada_facturada == 0
    assert resultado.completa is True


@pytest.mark.parametrize(
    "cobertura_ok,codificacion_ok,comprobante_ok",
    [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),
        (True, False, True),
        (False, True, True),
        (True, True, True),
    ],
)
async def prueba_completitud_reporta_cada_combinacion_de_piezas_sin_transicionar(
    cobertura_ok: bool, codificacion_ok: bool, comprobante_ok: bool
) -> None:
    """Adenda, Seccion 6: 'una cuenta en cada combinacion de piezas
    presentes/ausentes' -- las 8 combinaciones de las tres piezas que
    pueden variar (paciente+IAFAS siempre esta completa, Seccion 6.1)."""

    estado = EstadoPiezasCuenta(
        estado_cuenta="REGISTRADA",
        tiene_acreditacion=cobertura_ok,
        cantidad_procedimientos=1 if codificacion_ok else 0,
        tiene_comprobante=comprobante_ok,
    )
    repositorio = RepositorioCompletitudFalso(estado)
    caso_uso = ConsultarCompletitudCuenta(repositorio)

    resultado = await caso_uso.ejecutar(1)

    assert resultado is not None
    todas_ok = cobertura_ok and codificacion_ok and comprobante_ok
    assert resultado.estado_cuenta == "REGISTRADA"
    assert resultado.completa is todas_ok
    assert repositorio.veces_marcada_facturada == 0

    pieza_cobertura = next(p for p in resultado.piezas if p.clave == "cobertura")
    assert pieza_cobertura.completa is cobertura_ok
    pieza_codificacion = next(p for p in resultado.piezas if p.clave == "codificacion")
    assert pieza_codificacion.completa is codificacion_ok
    pieza_comprobante = next(p for p in resultado.piezas if p.clave == "comprobante")
    assert pieza_comprobante.completa is comprobante_ok
