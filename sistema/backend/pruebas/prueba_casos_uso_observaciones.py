"""Pruebas de los casos de uso de observaciones/glosas (CU-08 a CU-10,
Seccion 5.2.4.2) con dobles de prueba -- sin Postgres real: eso se
verifica aparte (pruebas/prueba_repositorio_observaciones.py y, para el
flujo completo, pruebas_integracion/)."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

import pytest

from app.dominio.acceso.entidades import NombreRol
from app.dominio.observaciones.casos_uso import (
    AsignarResponsableObservacion,
    RegistrarObservacion,
    ResponderObservacion,
)
from app.dominio.observaciones.errores import (
    ErrorMotivoInexistente,
    ErrorObservacionInexistente,
    ErrorObservacionYaRespondida,
)
from app.dominio.observaciones.valores import (
    DatosNuevaObservacion,
    DatosRegistroObservacion,
    MotivoObservacion,
    Naturaleza,
    Observacion,
    ResultadoObservacion,
)
from app.dominio.orquestacion.errores import ErrorTransicionNoDefinida
from app.dominio.puertos_comunes import Evento, Observabilidad

_AHORA = datetime(2026, 11, 8, 10, 0, 0)


class _RelojFijo:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


@dataclass
class _CatalogoMotivosFalso:
    motivos: dict[str, MotivoObservacion]

    async def obtener(self, codigo: str) -> MotivoObservacion | None:
        return self.motivos.get(codigo)

    async def listar(self) -> list[MotivoObservacion]:
        return list(self.motivos.values())


_MOTIVO_ADMINISTRATIVA = MotivoObservacion("OBS-01", "Datos incompletos", Naturaleza.ADMINISTRATIVA)
_MOTIVO_TECNICA = MotivoObservacion("OBS-04", "Prestacion no reconocida", Naturaleza.TECNICA)


@dataclass
class _EstadoCuentaFalso:
    estados: dict[int, str]

    async def obtener_estado(self, cuenta_medica_id: int) -> str | None:
        return self.estados.get(cuenta_medica_id)

    async def fijar_estado(self, cuenta_medica_id: int, estado_nuevo: str) -> None:
        self.estados[cuenta_medica_id] = estado_nuevo


@dataclass
class _ObservacionesFalso:
    siguiente_id: int = 1
    filas: dict[int, Observacion] = field(default_factory=dict)

    async def crear(self, datos: DatosNuevaObservacion) -> int:
        id_nuevo = self.siguiente_id
        self.siguiente_id += 1
        self.filas[id_nuevo] = Observacion(
            id=id_nuevo,
            cuenta_medica_id=datos.cuenta_medica_id,
            motivo_codigo=datos.motivo_codigo,
            naturaleza=datos.naturaleza,
            es_parcial=datos.es_parcial,
            detalle_campo_objetado=datos.detalle_campo_objetado,
            responsable_rol=datos.responsable_rol,
            responsable_usuario_id=None,
            estado="ABIERTA",
            respuesta_texto=None,
            respuesta_sustento=None,
            registrado_en=datos.registrado_en,
            respondido_en=None,
        )
        return id_nuevo

    async def obtener(self, observacion_id: int) -> Observacion | None:
        return self.filas.get(observacion_id)

    async def listar_por_cuenta(self, cuenta_medica_id: int) -> list[Observacion]:
        return [o for o in self.filas.values() if o.cuenta_medica_id == cuenta_medica_id]

    async def reasignar(
        self,
        observacion_id: int,
        naturaleza: Naturaleza,
        responsable_rol: NombreRol,
        responsable_usuario_id: int | None,
    ) -> None:
        actual = self.filas[observacion_id]
        self.filas[observacion_id] = Observacion(
            id=actual.id,
            cuenta_medica_id=actual.cuenta_medica_id,
            motivo_codigo=actual.motivo_codigo,
            naturaleza=naturaleza,
            es_parcial=actual.es_parcial,
            detalle_campo_objetado=actual.detalle_campo_objetado,
            responsable_rol=responsable_rol,
            responsable_usuario_id=responsable_usuario_id,
            estado=actual.estado,
            respuesta_texto=actual.respuesta_texto,
            respuesta_sustento=actual.respuesta_sustento,
            registrado_en=actual.registrado_en,
            respondido_en=actual.respondido_en,
        )

    async def responder(
        self,
        observacion_id: int,
        respuesta_texto: str,
        respuesta_sustento: str | None,
        respondido_en: datetime,
    ) -> None:
        actual = self.filas[observacion_id]
        self.filas[observacion_id] = Observacion(
            id=actual.id,
            cuenta_medica_id=actual.cuenta_medica_id,
            motivo_codigo=actual.motivo_codigo,
            naturaleza=actual.naturaleza,
            es_parcial=actual.es_parcial,
            detalle_campo_objetado=actual.detalle_campo_objetado,
            responsable_rol=actual.responsable_rol,
            responsable_usuario_id=actual.responsable_usuario_id,
            estado="RESPONDIDA",
            respuesta_texto=respuesta_texto,
            respuesta_sustento=respuesta_sustento,
            registrado_en=actual.registrado_en,
            respondido_en=respondido_en,
        )

    async def fijar_resultado(
        self, cuenta_medica_id: int, resultado: ResultadoObservacion, instante: datetime
    ) -> list[int]:
        ids = [
            o.id
            for o in self.filas.values()
            if o.cuenta_medica_id == cuenta_medica_id
            and o.estado == "RESPONDIDA"
            and o.resultado is None
        ]
        for i in ids:
            self.filas[i] = replace(self.filas[i], resultado=resultado.value, resultado_en=instante)
        return ids


def _observabilidad(registro_eventos: _RegistroEventosFalso) -> Observabilidad:
    class _MedicionesFalso:
        async def registrar(self, medicion: object) -> None:
            pass

    return Observabilidad(eventos=registro_eventos, mediciones=_MedicionesFalso())


# --- RegistrarObservacion (CU-08) ----------------------------------------


async def prueba_registrar_con_motivo_inexistente_es_rechazado() -> None:
    caso_uso = RegistrarObservacion(
        repositorio=_ObservacionesFalso(),
        catalogo=_CatalogoMotivosFalso({}),
        estado_cuenta=_EstadoCuentaFalso({1: "EN_AUDITORIA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorMotivoInexistente):
        await caso_uso.ejecutar(
            DatosRegistroObservacion(
                cuenta_medica_id=1,
                motivo_codigo="NO-EXISTE",
                es_parcial=False,
                detalle_campo_objetado=None,
                actor="ana.analista",
            )
        )


async def prueba_registrar_observacion_administrativa_total_desde_en_auditoria() -> None:
    registro_eventos = _RegistroEventosFalso()
    estado_cuenta = _EstadoCuentaFalso({1: "EN_AUDITORIA"})
    caso_uso = RegistrarObservacion(
        repositorio=_ObservacionesFalso(),
        catalogo=_CatalogoMotivosFalso({"OBS-01": _MOTIVO_ADMINISTRATIVA}),
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    resultado = await caso_uso.ejecutar(
        DatosRegistroObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-01",
            es_parcial=False,
            detalle_campo_objetado="Numero de historia clinica en blanco",
            actor="ana.analista",
            usuario_origen=None,
        )
    )
    assert resultado.naturaleza == Naturaleza.ADMINISTRATIVA
    assert resultado.responsable_rol == NombreRol.ANALISTA
    assert resultado.estado_cuenta == "GLOSADA"
    assert estado_cuenta.estados[1] == "GLOSADA"
    assert registro_eventos.eventos[0].tipo_evento == "GLOSA"
    assert registro_eventos.eventos[0].estado_previo == "EN_AUDITORIA"
    assert registro_eventos.eventos[0].estado_nuevo == "GLOSADA"
    assert registro_eventos.eventos[0].datos["naturaleza"] == "ADMINISTRATIVA"


async def prueba_registrar_observacion_tecnica_parcial_asigna_al_auditor() -> None:
    estado_cuenta = _EstadoCuentaFalso({1: "EN_AUDITORIA"})
    caso_uso = RegistrarObservacion(
        repositorio=_ObservacionesFalso(),
        catalogo=_CatalogoMotivosFalso({"OBS-04": _MOTIVO_TECNICA}),
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    resultado = await caso_uso.ejecutar(
        DatosRegistroObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-04",
            es_parcial=True,
            detalle_campo_objetado=None,
            actor="ana.analista",
        )
    )
    assert resultado.responsable_rol == NombreRol.AUDITOR
    assert resultado.estado_cuenta == "GLOSADA_PARCIAL"
    assert estado_cuenta.estados[1] == "GLOSADA_PARCIAL"


async def prueba_registrar_nueva_observacion_desde_subsanada_vuelve_a_glosada() -> None:
    """T-09 (Seccion 5.2.4.1): la aseguradora mantiene la objecion tras
    la respuesta remitida."""

    estado_cuenta = _EstadoCuentaFalso({1: "SUBSANADA"})
    registro_eventos = _RegistroEventosFalso()
    caso_uso = RegistrarObservacion(
        repositorio=_ObservacionesFalso(),
        catalogo=_CatalogoMotivosFalso({"OBS-01": _MOTIVO_ADMINISTRATIVA}),
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    resultado = await caso_uso.ejecutar(
        DatosRegistroObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-01",
            es_parcial=False,
            detalle_campo_objetado=None,
            actor="ana.analista",
        )
    )
    assert resultado.estado_cuenta == "GLOSADA"
    assert registro_eventos.eventos[0].tipo_evento == "NUEVA_OBSERVACION"


async def prueba_registrar_observacion_desde_estado_invalido_es_rechazado() -> None:
    caso_uso = RegistrarObservacion(
        repositorio=_ObservacionesFalso(),
        catalogo=_CatalogoMotivosFalso({"OBS-01": _MOTIVO_ADMINISTRATIVA}),
        estado_cuenta=_EstadoCuentaFalso({1: "REGISTRADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorTransicionNoDefinida):
        await caso_uso.ejecutar(
            DatosRegistroObservacion(
                cuenta_medica_id=1,
                motivo_codigo="OBS-01",
                es_parcial=False,
                detalle_campo_objetado=None,
                actor="ana.analista",
            )
        )


# --- AsignarResponsableObservacion (CU-09) -------------------------------


async def prueba_asignar_responsable_de_observacion_inexistente_es_rechazado() -> None:
    caso_uso = AsignarResponsableObservacion(
        repositorio=_ObservacionesFalso(), observabilidad=_observabilidad(_RegistroEventosFalso())
    )
    with pytest.raises(ErrorObservacionInexistente):
        await caso_uso.ejecutar(999, actor="jefa.prueba", responsable_usuario_id=7)


async def prueba_confirmar_asignacion_sin_corregir_naturaleza_mantiene_el_rol() -> None:
    repositorio = _ObservacionesFalso()
    observacion_id = await repositorio.crear(
        DatosNuevaObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-01",
            naturaleza=Naturaleza.ADMINISTRATIVA,
            es_parcial=False,
            detalle_campo_objetado=None,
            responsable_rol=NombreRol.ANALISTA,
            registrado_en=_AHORA,
        )
    )
    registro_eventos = _RegistroEventosFalso()
    caso_uso = AsignarResponsableObservacion(
        repositorio=repositorio, observabilidad=_observabilidad(registro_eventos)
    )
    await caso_uso.ejecutar(observacion_id, actor="jefa.prueba", responsable_usuario_id=7)

    observacion = await repositorio.obtener(observacion_id)
    assert observacion is not None
    assert observacion.responsable_rol == NombreRol.ANALISTA
    assert observacion.responsable_usuario_id == 7
    assert registro_eventos.eventos[0].tipo_evento == "OBSERVACION_REASIGNADA"
    assert registro_eventos.eventos[0].datos["naturaleza_anterior"] == "ADMINISTRATIVA"
    assert registro_eventos.eventos[0].datos["naturaleza_nueva"] == "ADMINISTRATIVA"


async def prueba_corregir_naturaleza_recalcula_el_responsable() -> None:
    repositorio = _ObservacionesFalso()
    observacion_id = await repositorio.crear(
        DatosNuevaObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-01",
            naturaleza=Naturaleza.ADMINISTRATIVA,
            es_parcial=False,
            detalle_campo_objetado=None,
            responsable_rol=NombreRol.ANALISTA,
            registrado_en=_AHORA,
        )
    )
    caso_uso = AsignarResponsableObservacion(
        repositorio=repositorio, observabilidad=_observabilidad(_RegistroEventosFalso())
    )
    await caso_uso.ejecutar(
        observacion_id,
        actor="jefa.prueba",
        responsable_usuario_id=None,
        naturaleza_corregida=Naturaleza.TECNICA,
    )
    observacion = await repositorio.obtener(observacion_id)
    assert observacion is not None
    assert observacion.naturaleza == Naturaleza.TECNICA
    assert observacion.responsable_rol == NombreRol.AUDITOR


# --- ResponderObservacion (CU-10) ----------------------------------------


async def prueba_responder_observacion_inexistente_es_rechazado() -> None:
    caso_uso = ResponderObservacion(
        repositorio=_ObservacionesFalso(),
        estado_cuenta=_EstadoCuentaFalso({}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorObservacionInexistente):
        await caso_uso.ejecutar(999, "sustento", None, actor="auditor.prueba")


async def prueba_responder_observacion_ya_respondida_es_rechazado() -> None:
    repositorio = _ObservacionesFalso()
    observacion_id = await repositorio.crear(
        DatosNuevaObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-01",
            naturaleza=Naturaleza.ADMINISTRATIVA,
            es_parcial=False,
            detalle_campo_objetado=None,
            responsable_rol=NombreRol.ANALISTA,
            registrado_en=_AHORA,
        )
    )
    await repositorio.responder(observacion_id, "ya respondida antes", None, _AHORA)
    caso_uso = ResponderObservacion(
        repositorio=repositorio,
        estado_cuenta=_EstadoCuentaFalso({1: "GLOSADA"}),
        observabilidad=_observabilidad(_RegistroEventosFalso()),
        reloj=_RelojFijo(),
    )
    with pytest.raises(ErrorObservacionYaRespondida):
        await caso_uso.ejecutar(observacion_id, "de nuevo", None, actor="ana.analista")


async def prueba_responder_observacion_total_lleva_la_cuenta_a_subsanada() -> None:
    repositorio = _ObservacionesFalso()
    observacion_id = await repositorio.crear(
        DatosNuevaObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-01",
            naturaleza=Naturaleza.ADMINISTRATIVA,
            es_parcial=False,
            detalle_campo_objetado=None,
            responsable_rol=NombreRol.ANALISTA,
            registrado_en=_AHORA,
        )
    )
    estado_cuenta = _EstadoCuentaFalso({1: "GLOSADA"})
    registro_eventos = _RegistroEventosFalso()
    caso_uso = ResponderObservacion(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    await caso_uso.ejecutar(
        observacion_id,
        "Se adjunta la historia clinica completa.",
        "historia_clinica.pdf",
        actor="ana.analista",
    )

    observacion = await repositorio.obtener(observacion_id)
    assert observacion is not None
    assert observacion.estado == "RESPONDIDA"
    assert observacion.respuesta_texto == "Se adjunta la historia clinica completa."
    assert estado_cuenta.estados[1] == "SUBSANADA"
    assert registro_eventos.eventos[0].tipo_evento == "OBSERVACION_RESPONDIDA"
    assert registro_eventos.eventos[0].estado_previo == "GLOSADA"
    assert registro_eventos.eventos[0].estado_nuevo == "SUBSANADA"


async def prueba_responder_observacion_parcial_no_mueve_la_cuenta() -> None:
    """Tabla 58/65/66: no hay una fila GLOSADA_PARCIAL -> SUBSANADA; la
    glosa parcial sigue directo a LIQUIDADA_PARCIAL (T-10, CU-12, a
    cargo de tesoreria) cuando corresponda."""

    repositorio = _ObservacionesFalso()
    observacion_id = await repositorio.crear(
        DatosNuevaObservacion(
            cuenta_medica_id=1,
            motivo_codigo="OBS-04",
            naturaleza=Naturaleza.TECNICA,
            es_parcial=True,
            detalle_campo_objetado=None,
            responsable_rol=NombreRol.AUDITOR,
            registrado_en=_AHORA,
        )
    )
    estado_cuenta = _EstadoCuentaFalso({1: "GLOSADA_PARCIAL"})
    registro_eventos = _RegistroEventosFalso()
    caso_uso = ResponderObservacion(
        repositorio=repositorio,
        estado_cuenta=estado_cuenta,
        observabilidad=_observabilidad(registro_eventos),
        reloj=_RelojFijo(),
    )
    await caso_uso.ejecutar(observacion_id, "Codificacion corregida.", None, actor="auditor.prueba")

    assert estado_cuenta.estados[1] == "GLOSADA_PARCIAL"  # sin cambios
    assert registro_eventos.eventos[0].estado_previo is None
    assert registro_eventos.eventos[0].estado_nuevo is None
