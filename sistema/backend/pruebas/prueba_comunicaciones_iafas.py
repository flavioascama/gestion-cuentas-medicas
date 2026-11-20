"""Pruebas de la ingesta de comunicaciones de la IAFAS (portal o correo) con
dobles de prueba: que cada comunicacion se aplique una sola vez con el caso
de uso que usaria la persona, y que lo que no se puede aplicar quede
registrado sin perderse. El recorrido real contra los simuladores se
verifica en pruebas_integracion/."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from app.dominio.comunicaciones.casos_uso import (
    ACTOR_ROBOT_COMUNICACIONES,
    TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS,
    TIPO_TRABAJO_MONITOREAR_COMUNICACIONES,
    Aplicacion,
    CasosUsoComunicaciones,
    ComunicacionIafas,
    ComunicacionRegistrada,
    EncolarRespuestaIafas,
    ProcesarComunicacionIafas,
    RegistrarRemisionRespuesta,
    RemisionRespuesta,
    ResultadoComunicacion,
    SolicitarRevisionComunicaciones,
)
from app.dominio.observaciones.valores import DatosRegistroObservacion
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
from app.dominio.pse.documentos import (
    ComprobanteReemplazado,
    ComprobanteVigente,
    DocumentosPagoCuenta,
    NotaDocumento,
)
from app.dominio.puertos_comunes import Evento

_AHORA = datetime(2026, 11, 13, 9, 0, 0)


class _RelojFijo:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@dataclass
class _RepositorioFalso:
    documentos: dict[str, int] = field(default_factory=dict)
    registradas: list[Aplicacion] = field(default_factory=list)
    descartes: int = 0
    origen: ComunicacionRegistrada | None = None
    pendiente: int | None = None
    remitidas: list[str] = field(default_factory=list)

    async def ya_registrada(self, codigo: str) -> bool:
        return any(a.comunicacion.codigo == codigo for a in self.registradas)

    async def registrar(self, aplicacion: Aplicacion, recibida_en: datetime) -> None:
        self.registradas.append(aplicacion)

    async def descartar_cambios_pendientes(self) -> None:
        self.descartes += 1

    async def codigos_ipress(self) -> list[str]:
        return ["15995250"]

    async def cuenta_de_documento(self, documento: str) -> int | None:
        return self.documentos.get(documento)

    async def origen_de_observacion(self, observacion_id: int) -> ComunicacionRegistrada | None:
        return self.origen

    async def marcar_respuesta_remitida(self, codigo: str, instante: datetime) -> None:
        self.remitidas.append(codigo)

    async def obtener(self, codigo: str) -> ComunicacionRegistrada | None:
        return self.origen

    async def revision_pendiente(self) -> int | None:
        return self.pendiente

    async def listar(
        self, cuenta_medica_id: int | None = None, limite: int = 200
    ) -> list[ComunicacionRegistrada]:
        return []


@dataclass(frozen=True)
class _ResultadoObservacion:
    observacion_id: int


@dataclass
class _CasoUsoFalso:
    """Registra con que se llamo; opcionalmente falla como lo haria el real."""

    error: Exception | None = None
    llamadas: list[tuple[Any, ...]] = field(default_factory=list)

    async def ejecutar(self, *argumentos: Any) -> Any:
        self.llamadas.append(argumentos)
        if self.error is not None:
            raise self.error
        return _ResultadoObservacion(observacion_id=77)


@dataclass
class _Casos:
    conformidad: _CasoUsoFalso = field(default_factory=_CasoUsoFalso)
    observacion: _CasoUsoFalso = field(default_factory=_CasoUsoFalso)
    liquidacion: _CasoUsoFalso = field(default_factory=_CasoUsoFalso)
    pago: _CasoUsoFalso = field(default_factory=_CasoUsoFalso)

    def como_parametros(self) -> CasosUsoComunicaciones:
        return CasosUsoComunicaciones(
            conformidad=self.conformidad,  # type: ignore[arg-type]
            observacion=self.observacion,  # type: ignore[arg-type]
            liquidacion=self.liquidacion,  # type: ignore[arg-type]
            pago=self.pago,  # type: ignore[arg-type]
        )


@dataclass
class _TrabajosFalso:
    encolados: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    async def encolar(
        self, tipo: str, carga_util: dict[str, Any], proximo_intento: datetime
    ) -> int:
        self.encolados.append((tipo, carga_util))
        return len(self.encolados)


def _comunicacion(tipo: str, datos: dict[str, Any], canal: str = "CORREO") -> ComunicacionIafas:
    return ComunicacionIafas(
        codigo="COM-00000001",
        canal=canal,
        tipo=tipo,
        codigo_iafas="20001",
        codigo_ipress="15995250",
        documento="F00100000123",
        datos=datos,
        emitida_en="2026-11-13T08:00:00+00:00",
    )


def _armar(
    repositorio: _RepositorioFalso, casos: _Casos
) -> tuple[ProcesarComunicacionIafas, _RegistroEventosFalso]:
    eventos = _RegistroEventosFalso()
    caso_uso = ProcesarComunicacionIafas(
        repositorio, casos.como_parametros(), eventos, _RelojFijo()
    )
    return caso_uso, eventos


async def prueba_observacion_por_correo_se_registra_con_el_caso_de_uso_cu08() -> None:
    repositorio = _RepositorioFalso(documentos={"F00100000123": 5})
    casos = _Casos()
    caso_uso, eventos = _armar(repositorio, casos)
    datos = {
        "motivo_codigo": "ADM-01",
        "es_parcial": True,
        "monto_glosado": "40.00",
        "detalle": "x",
    }

    resultado = await caso_uso.ejecutar(_comunicacion("OBSERVACION", datos))

    assert resultado is ResultadoComunicacion.APLICADA
    (argumentos,) = casos.observacion.llamadas
    assert replace(argumentos[0], monto_observado=None) == DatosRegistroObservacion(
        cuenta_medica_id=5,
        motivo_codigo="ADM-01",
        es_parcial=True,
        detalle_campo_objetado="x",
        actor=ACTOR_ROBOT_COMUNICACIONES,
    )
    assert [e.tipo_evento for e in eventos.eventos] == ["COMUNICACION_IAFAS_RECIBIDA"]
    assert eventos.eventos[0].datos["canal"] == "CORREO"
    (aplicacion,) = repositorio.registradas
    assert (aplicacion.cuenta_medica_id, aplicacion.observacion_id) == (5, 77)


async def prueba_la_misma_comunicacion_no_se_aplica_dos_veces() -> None:
    repositorio = _RepositorioFalso(documentos={"F00100000123": 5})
    casos = _Casos()
    caso_uso, _ = _armar(repositorio, casos)
    comunicacion = _comunicacion("LIQUIDACION", {"monto_liquidado": "100.00"})

    await caso_uso.ejecutar(comunicacion)
    segunda = await caso_uso.ejecutar(comunicacion)

    assert segunda is ResultadoComunicacion.DUPLICADA
    assert casos.liquidacion.llamadas == [(5, Decimal("100.00"), ACTOR_ROBOT_COMUNICACIONES)]


async def prueba_conformidad_y_pago_usan_cu07_y_cu12() -> None:
    repositorio = _RepositorioFalso(documentos={"F00100000123": 5})
    casos = _Casos()
    caso_uso, _ = _armar(repositorio, casos)

    await caso_uso.ejecutar(_comunicacion("AUDITORIA_CONFORME", {}, canal="PORTAL"))
    pago = replace(_comunicacion("PAGO", {"monto_pagado": "90.50"}), codigo="COM-00000002")
    await caso_uso.ejecutar(pago)

    assert casos.conformidad.llamadas == [(5, ACTOR_ROBOT_COMUNICACIONES)]
    assert casos.pago.llamadas == [(5, Decimal("90.50"), ACTOR_ROBOT_COMUNICACIONES)]


async def prueba_comprobante_desconocido_queda_no_aplicada_sin_cuenta() -> None:
    repositorio = _RepositorioFalso()
    caso_uso, eventos = _armar(repositorio, _Casos())

    resultado = await caso_uso.ejecutar(_comunicacion("PAGO", {"monto_pagado": "1"}))

    assert resultado is ResultadoComunicacion.NO_APLICADA
    assert eventos.eventos == []
    (aplicacion,) = repositorio.registradas
    assert aplicacion.cuenta_medica_id is None
    assert aplicacion.detalle == "Comprobante desconocido."


async def prueba_rechazo_del_negocio_descarta_cambios_y_avisa() -> None:
    repositorio = _RepositorioFalso(documentos={"F00100000123": 5})
    casos = _Casos(liquidacion=_CasoUsoFalso(error=ErrorTransicionNoDefinida("no definida")))
    caso_uso, eventos = _armar(repositorio, casos)

    resultado = await caso_uso.ejecutar(_comunicacion("LIQUIDACION", {"monto_liquidado": "5"}))

    assert resultado is ResultadoComunicacion.NO_APLICADA
    assert repositorio.descartes == 1
    assert [e.tipo_evento for e in eventos.eventos] == [
        "COMUNICACION_IAFAS_RECIBIDA",
        "COMUNICACION_IAFAS_NO_APLICADA",
    ]
    assert eventos.eventos[1].datos["detalle"] == "no definida"
    assert repositorio.registradas[0].resultado is ResultadoComunicacion.NO_APLICADA


async def prueba_monto_ilegible_queda_no_aplicada() -> None:
    repositorio = _RepositorioFalso(documentos={"F00100000123": 5})
    casos = _Casos()
    caso_uso, _ = _armar(repositorio, casos)

    resultado = await caso_uso.ejecutar(_comunicacion("PAGO", {"monto_pagado": "abc"}))

    assert resultado is ResultadoComunicacion.NO_APLICADA
    assert casos.pago.llamadas == []


async def prueba_una_falla_que_no_es_del_negocio_se_propaga_para_reintentar() -> None:
    repositorio = _RepositorioFalso(documentos={"F00100000123": 5})
    casos = _Casos(pago=_CasoUsoFalso(error=RuntimeError("base caida")))
    caso_uso, _ = _armar(repositorio, casos)

    with pytest.raises(RuntimeError):
        await caso_uso.ejecutar(_comunicacion("PAGO", {"monto_pagado": "1"}))
    assert repositorio.registradas == []


def _registrada(remitida: datetime | None = None) -> ComunicacionRegistrada:
    return ComunicacionRegistrada(
        codigo="COM-00000001",
        canal="CORREO",
        tipo="OBSERVACION",
        codigo_iafas="20001",
        codigo_ipress="15995250",
        documento="F00100000123",
        datos={},
        emitida_en="2026-11-13T08:00:00+00:00",
        cuenta_medica_id=5,
        resultado="APLICADA",
        detalle=None,
        observacion_id=77,
        recibida_en=_AHORA,
        respuesta_remitida_en=remitida,
    )


async def prueba_respuesta_a_observacion_de_la_iafas_se_encola_para_su_portal() -> None:
    trabajos = _TrabajosFalso()
    repositorio = _RepositorioFalso(origen=_registrada())

    trabajo_id = await EncolarRespuestaIafas(repositorio, trabajos, _RelojFijo()).ejecutar(
        77, "Se adjunta sustento.", None, "analista.uno"
    )

    assert trabajo_id == 1
    ((tipo, carga),) = trabajos.encolados
    assert tipo == TIPO_TRABAJO_ENVIAR_RESPUESTA_IAFAS
    assert carga["codigo"] == "COM-00000001"
    assert carga["codigo_ipress"] == "15995250"
    assert carga["usuario_origen"] == "analista.uno"


_VIGENTE = ComprobanteVigente(1, "01", "F001", "00000200", date(2026, 11, 14))
_REEMPLAZADO = ComprobanteReemplazado(
    "01", "F001", "00000123", date(2026, 11, 1), _AHORA, "analista.uno", "Refacturacion"
)
_NOTA = NotaDocumento(
    "C", "FC01", "00000007", Decimal("150.00"), date(2026, 11, 14), "D", _AHORA, "analista.uno"
)


@dataclass
class _DocumentosFalso:
    documentos_cuenta: DocumentosPagoCuenta | None

    async def documentos(self, cuenta_medica_id: int) -> DocumentosPagoCuenta | None:
        return self.documentos_cuenta


async def _sustento_encolado(
    documentos: DocumentosPagoCuenta | None, sustento: str | None
) -> str | None:
    trabajos = _TrabajosFalso()
    encolar = EncolarRespuestaIafas(
        _RepositorioFalso(origen=_registrada()),
        trabajos,
        _RelojFijo(),
        _DocumentosFalso(documentos),  # type: ignore[arg-type]
    )
    await encolar.ejecutar(77, "Se refacturo.", sustento, "analista.uno")
    ((_, carga),) = trabajos.encolados
    return carga["sustento"]


async def prueba_respuesta_con_reemplazo_informa_el_comprobante_vigente() -> None:
    sustento = await _sustento_encolado(
        DocumentosPagoCuenta(_VIGENTE, None, [_REEMPLAZADO]), "Historia clinica."
    )

    assert sustento == "Historia clinica.\nComprobante vigente: F001-00000200."


async def prueba_respuesta_con_nota_informa_la_nota_y_recorta_lo_escrito() -> None:
    sustento = await _sustento_encolado(DocumentosPagoCuenta(_VIGENTE, _NOTA), "x" * 600)
    assert sustento is not None
    assert len(sustento) == 500
    assert sustento.endswith(
        "Comprobante vigente: F001-00000200. Nota de crédito: FC01-00000007 por 150.00."
    )
    assert sustento.startswith("xxx")


async def prueba_respuesta_sin_refacturar_entrega_el_sustento_igual() -> None:
    assert await _sustento_encolado(DocumentosPagoCuenta(_VIGENTE, None), None) is None


async def prueba_observacion_registrada_a_mano_no_se_remite() -> None:
    trabajos = _TrabajosFalso()

    trabajo_id = await EncolarRespuestaIafas(_RepositorioFalso(), trabajos, _RelojFijo()).ejecutar(
        77, "texto", None, "analista.uno"
    )

    assert trabajo_id is None
    assert trabajos.encolados == []


async def prueba_revision_no_se_duplica_si_ya_hay_una_pendiente() -> None:
    trabajos = _TrabajosFalso()
    con_pendiente = SolicitarRevisionComunicaciones(
        _RepositorioFalso(pendiente=40), trabajos, _RelojFijo()
    )
    sin_pendiente = SolicitarRevisionComunicaciones(_RepositorioFalso(), trabajos, _RelojFijo())

    assert await con_pendiente.ejecutar("temporizador") == 40
    assert await sin_pendiente.ejecutar("jefe.uno") == 1
    assert trabajos.encolados == [
        (TIPO_TRABAJO_MONITOREAR_COMUNICACIONES, {"usuario_origen": "jefe.uno"})
    ]


async def prueba_remision_registra_evento_y_fecha() -> None:
    repositorio = _RepositorioFalso(origen=_registrada())
    eventos = _RegistroEventosFalso()
    caso_uso = RegistrarRemisionRespuesta(repositorio, eventos, _RelojFijo())

    assert not await caso_uso.ya_remitida("COM-00000001")
    await caso_uso.ejecutar(RemisionRespuesta("COM-00000001", 5, 77, "analista.uno"))

    assert repositorio.remitidas == ["COM-00000001"]
    (evento,) = eventos.eventos
    assert evento.tipo_evento == "RESPUESTA_IAFAS_REMITIDA"
    assert evento.usuario_origen == "analista.uno"
    repositorio.origen = _registrada(remitida=_AHORA)
    assert await caso_uso.ya_remitida("COM-00000001")
