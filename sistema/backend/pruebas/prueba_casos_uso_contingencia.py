"""Pruebas del modo de contingencia (RF-23, AD-13, C-18) con dobles de
prueba. C-18 (Tabla 29) pide "prueba automatizada del registro en modo de
contingencia, con y sin sustento, y de su revision por el jefe de cuentas
medicas": eso es exactamente lo que cubre este archivo, mas la regla de
habilitacion (solo tras agotar los reintentos de la plataforma)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from app.dominio.acreditacion.valores import ContextoCuentaAcreditacion, ResultadoAcreditacion
from app.dominio.contingencia.casos_uso import (
    ConsultarDisponibilidadContingencia,
    ConsultarUltimaConsultaCobertura,
    ListarRegistrosContingencia,
    RegistrarCoberturaContingencia,
    RevisarRegistroContingencia,
)
from app.dominio.contingencia.errores import (
    ErrorArchivoS01Invalido,
    ErrorContingenciaNoHabilitada,
    ErrorRegistroContingenciaYaRevisado,
    ErrorSustentoInsuficiente,
)
from app.dominio.contingencia.valores import (
    EstadoRevision,
    RegistroContingencia,
    ResultadoConsulta,
    ResultadoValidacionManual,
    ResumenTrabajo,
    TipoOperacion,
    clasificar_consulta,
)
from app.dominio.integracion.puertos_validacion import ArchivoLote
from app.dominio.puertos_comunes import Evento, Observabilidad
from app.infraestructura.tedef.registrar_validacion_contingencia import (
    RegistrarValidacionContingencia,
    RepositoriosValidacionContingencia,
)

_AHORA = datetime(2026, 11, 12, 10, 0, 0)
_SUSTENTO = "Constancia telefonica de la IAFAS, operador de turno"
_RESULTADO = ResultadoAcreditacion(
    condicion_cobertura="ACREDITABLE",
    codigo_autorizacion="AUT-0001",
    tipo_documento_autorizacion="03",
    codigo_asegurado="000123",
    tipo_afiliacion="1",
    plan=None,
    vigente_desde=None,
    vigente_hasta=None,
    tipo_copago=None,
    monto_copago_fijo=None,
    porcentaje_coaseguro=None,
)


class _Reloj:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _Eventos:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


class _Mediciones:
    async def registrar(self, medicion: object) -> None:
        pass


@dataclass
class _Contingencia:
    agotado: bool = True
    error: str | None = "ACREDITA SALUD no responde"
    estado_lote: str | None = "GENERADO"
    registros: list[RegistroContingencia] = field(default_factory=list)
    observados: list[int] = field(default_factory=list)

    async def ultimo_trabajo(
        self, tipo_trabajo: str, clave: str, valor: int
    ) -> ResumenTrabajo | None:
        return ResumenTrabajo(
            estado="AGOTADO" if self.agotado else "COMPLETADO",
            error=self.error,
            intentos=5,
            creado_en=_AHORA,
            actualizado_en=_AHORA,
        )

    async def obtener_estado_lote(self, lote_id: int) -> str | None:
        return self.estado_lote

    async def marcar_lote_observado(self, lote_id: int) -> None:
        self.observados.append(lote_id)

    async def listar_registros(self) -> list[RegistroContingencia]:
        return self.registros


@dataclass
class _Acreditaciones:
    existe: bool = False
    guardadas: list[tuple[int, str]] = field(default_factory=list)

    async def obtener_contexto_cuenta(self, cuenta_medica_id: int) -> object:
        return object()

    async def existe_acreditacion(self, cuenta_medica_id: int) -> bool:
        return self.existe

    async def guardar_acreditacion(self, **kwargs: object) -> int:
        self.guardadas.append(
            (int(str(kwargs["cuenta_medica_id"])), str(kwargs["componente_ejecutor"]))
        )
        return 99


@dataclass
class _Validacion:
    archivos: list[tuple[int, str, str]] = field(default_factory=list)

    async def registrar_archivo_transmision(self, **kwargs: object) -> None:
        archivo = kwargs["archivo"]
        assert isinstance(archivo, ArchivoLote)
        self.archivos.append((int(str(kwargs["lote_id"])), archivo.nombre, str(kwargs["ruta_s01"])))


def _observabilidad(eventos: _Eventos) -> Observabilidad:
    return Observabilidad(eventos=eventos, mediciones=_Mediciones())  # type: ignore[arg-type]


def _cobertura(
    contingencia: _Contingencia, acreditaciones: _Acreditaciones, eventos: _Eventos
) -> RegistrarCoberturaContingencia:
    disponibilidad = ConsultarDisponibilidadContingencia(contingencia, acreditaciones)  # type: ignore[arg-type]
    return RegistrarCoberturaContingencia(
        disponibilidad,
        acreditaciones,
        _observabilidad(eventos),
        _Reloj(),  # type: ignore[arg-type]
    )


async def prueba_cobertura_con_sustento_queda_marcada_como_registro_manual() -> None:
    acreditaciones, eventos = _Acreditaciones(), _Eventos()
    caso_uso = _cobertura(_Contingencia(), acreditaciones, eventos)

    assert await caso_uso.ejecutar(5, _RESULTADO, _SUSTENTO, "ana") == 99

    assert acreditaciones.guardadas == [(5, "registro_manual_contingencia")]
    (evento,) = eventos.eventos
    assert evento.tipo_evento == "CONTINGENCIA_COBERTURA_REGISTRADA"
    assert evento.datos["modo"] == "contingencia"
    assert evento.datos["sustento"] == _SUSTENTO
    assert evento.datos["codigo_autorizacion"] == "AUT-0001"
    # C-11: el codigo del asegurado no se copia al almacen de eventos.
    assert "codigo_asegurado" not in evento.datos


@pytest.mark.parametrize("sustento", ["", "   ", "ok"])
async def prueba_cobertura_sin_sustento_es_rechazada(sustento: str) -> None:
    acreditaciones, eventos = _Acreditaciones(), _Eventos()
    with pytest.raises(ErrorSustentoInsuficiente):
        await _cobertura(_Contingencia(), acreditaciones, eventos).ejecutar(
            5, _RESULTADO, sustento, "ana"
        )
    assert acreditaciones.guardadas == [] and eventos.eventos == []


async def prueba_cobertura_no_se_habilita_si_la_plataforma_no_agoto_reintentos() -> None:
    with pytest.raises(ErrorContingenciaNoHabilitada):
        await _cobertura(_Contingencia(agotado=False), _Acreditaciones(), _Eventos()).ejecutar(
            5, _RESULTADO, _SUSTENTO, "ana"
        )


async def prueba_cobertura_no_se_habilita_si_ya_hay_acreditacion() -> None:
    with pytest.raises(ErrorContingenciaNoHabilitada):
        await _cobertura(_Contingencia(), _Acreditaciones(existe=True), _Eventos()).ejecutar(
            5, _RESULTADO, _SUSTENTO, "ana"
        )


def _validacion(
    contingencia: _Contingencia, validacion: _Validacion, eventos: _Eventos, tmp_path: Path
) -> RegistrarValidacionContingencia:
    disponibilidad = ConsultarDisponibilidadContingencia(contingencia, _Acreditaciones())  # type: ignore[arg-type]
    return RegistrarValidacionContingencia(
        disponibilidad,
        RepositoriosValidacionContingencia(contingencia, validacion),  # type: ignore[arg-type]
        _observabilidad(eventos),
        _Reloj(),
        tmp_path,
    )


async def prueba_validacion_validado_guarda_el_s01_y_deja_el_lote_listo(tmp_path: Path) -> None:
    validacion, eventos = _Validacion(), _Eventos()
    caso_uso = _validacion(_Contingencia(), validacion, eventos, tmp_path)
    archivo = ArchivoLote(nombre="937_LOTE_0000007.S01", contenido=b"contenido")

    estado = await caso_uso.ejecutar(
        7, ResultadoValidacionManual.VALIDADO, _SUSTENTO, archivo, "ana"
    )

    assert estado == "VALIDADO"
    assert (tmp_path / "937_LOTE_0000007.S01").read_bytes() == b"contenido"
    assert validacion.archivos[0][:2] == (7, "937_LOTE_0000007.S01")
    (evento,) = eventos.eventos
    assert (evento.tipo_evento, evento.estado_previo, evento.estado_nuevo) == (
        "CONTINGENCIA_VALIDACION_REGISTRADA",
        "GENERADO",
        "VALIDADO",
    )
    assert evento.datos["sha256_s01"] and evento.datos["sustento"] == _SUSTENTO


async def prueba_validacion_validado_sin_s01_es_rechazada(tmp_path: Path) -> None:
    validacion, eventos = _Validacion(), _Eventos()
    with pytest.raises(ErrorArchivoS01Invalido):
        await _validacion(_Contingencia(), validacion, eventos, tmp_path).ejecutar(
            7, ResultadoValidacionManual.VALIDADO, _SUSTENTO, None, "ana"
        )
    assert validacion.archivos == [] and eventos.eventos == []


async def prueba_validacion_observado_marca_el_lote(tmp_path: Path) -> None:
    contingencia, eventos = _Contingencia(estado_lote="CARGADO_VALIDADOR"), _Eventos()
    estado = await _validacion(contingencia, _Validacion(), eventos, tmp_path).ejecutar(
        7, ResultadoValidacionManual.OBSERVADO, _SUSTENTO, None, "ana"
    )
    assert estado == "OBSERVADO_VALIDADOR"
    assert contingencia.observados == [7]


async def prueba_validacion_no_se_habilita_con_el_lote_ya_validado(tmp_path: Path) -> None:
    with pytest.raises(ErrorContingenciaNoHabilitada):
        await _validacion(
            _Contingencia(estado_lote="VALIDADO"), _Validacion(), _Eventos(), tmp_path
        ).ejecutar(7, ResultadoValidacionManual.OBSERVADO, _SUSTENTO, None, "ana")


def _registro(estado: EstadoRevision) -> RegistroContingencia:
    return RegistroContingencia(
        evento_id="e-1",
        tipo_operacion=TipoOperacion.COBERTURA,
        cuenta_medica_id=5,
        identificacion_interna="CTA-000005",
        lote_id=None,
        numero_lote=None,
        resumen="Cobertura ACREDITABLE",
        sustento=_SUSTENTO,
        registrado_por="ana",
        registrado_en=_AHORA,
        estado_revision=estado,
    )


async def prueba_el_jefe_revisa_un_registro_pendiente() -> None:
    eventos = _Eventos()
    contingencia = _Contingencia(registros=[_registro(EstadoRevision.PENDIENTE)])
    await RevisarRegistroContingencia(contingencia, _observabilidad(eventos)).ejecutar(  # type: ignore[arg-type]
        "e-1", True, " constancia verificada ", "jefe"
    )
    (evento,) = eventos.eventos
    assert evento.tipo_evento == "CONTINGENCIA_REVISADA"
    assert evento.cuenta_medica_id == 5
    assert evento.datos == {
        "registro_evento_id": "e-1",
        "conforme": True,
        "comentario": "constancia verificada",
    }


async def prueba_un_registro_ya_revisado_no_se_revisa_dos_veces() -> None:
    contingencia = _Contingencia(registros=[_registro(EstadoRevision.CONFORME)])
    with pytest.raises(ErrorRegistroContingenciaYaRevisado):
        await RevisarRegistroContingencia(contingencia, _observabilidad(_Eventos())).ejecutar(  # type: ignore[arg-type]
            "e-1", False, "", "jefe"
        )


async def prueba_listar_solo_pendientes() -> None:
    contingencia = _Contingencia(
        registros=[_registro(EstadoRevision.PENDIENTE), _registro(EstadoRevision.CONFORME)]
    )
    pendientes = await ListarRegistrosContingencia(contingencia).ejecutar(solo_pendientes=True)  # type: ignore[arg-type]
    assert [r.estado_revision for r in pendientes] == [EstadoRevision.PENDIENTE]


async def prueba_un_asegurado_no_encontrado_no_habilita_la_contingencia() -> None:
    """Un asegurado no encontrado es una respuesta de ACREDITA SALUD, no una
    plataforma caida: la contingencia (RF-23) no aplica. Incluye el texto
    que dejaban los trabajos anteriores al estado SIN_RESULTADO."""
    contingencia = _Contingencia(error="El simulador no encontro al asegurado 1 73457855.")
    disponibilidad = ConsultarDisponibilidadContingencia(contingencia, _Acreditaciones())  # type: ignore[arg-type]
    assert await disponibilidad.cobertura(5) is False


def prueba_clasificar_la_ultima_consulta_de_cobertura() -> None:
    def resumen(estado: str, error: str | None = None) -> ResumenTrabajo:
        return ResumenTrabajo(estado, error, 1, _AHORA, _AHORA)

    assert clasificar_consulta(resumen("SIN_RESULTADO")) is ResultadoConsulta.SIN_RESULTADO
    assert clasificar_consulta(resumen("AGOTADO", "timeout")) is ResultadoConsulta.SIN_RESPUESTA
    assert clasificar_consulta(resumen("REQUIERE_SESION")) is ResultadoConsulta.REQUIERE_SESION
    assert clasificar_consulta(resumen("PENDIENTE")) is ResultadoConsulta.EN_CURSO
    assert clasificar_consulta(resumen("COMPLETADO")) is ResultadoConsulta.COMPLETADA


async def prueba_la_ultima_consulta_dice_el_mensaje_clinico() -> None:
    @dataclass
    class _ConContexto(_Acreditaciones):
        async def obtener_contexto_cuenta(self, cuenta_medica_id: int) -> object:
            return ContextoCuentaAcreditacion(cuenta_medica_id, "1", "73457855")

    contingencia = _Contingencia(error="El simulador no encontro al asegurado 1 73457855.")
    ultima = await ConsultarUltimaConsultaCobertura(contingencia, _ConContexto()).ejecutar(5)  # type: ignore[arg-type]
    assert ultima is not None
    assert ultima.resultado is ResultadoConsulta.SIN_RESULTADO
    assert ultima.mensaje == "ACREDITA SALUD no encontró al asegurado con DNI 73457855."
