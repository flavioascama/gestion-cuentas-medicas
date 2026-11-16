"""Pruebas del registro de los correos de la IAFAS (2026-11-15): que todo
correo del buzon quede en el sistema -- tambien el que no trae el formato de
la aseguradora --, que solo se aplique sola la comunicacion de un remitente
registrado, que los adjuntos se limiten y se guarden cifrados con su huella,
y que cada consulta, descarga, vinculacion y descarte quede en la bitacora."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.avisos.valores import (
    TIPO_AVISO_CORREO_POR_REVISAR,
    EventoAviso,
    clave_agrupacion,
)
from app.dominio.comunicaciones.casos_uso import ComunicacionIafas, ComunicacionRegistrada
from app.dominio.comunicaciones.correos import (
    MAXIMO_ADJUNTOS,
    TAMANO_MAXIMO_ADJUNTO,
    AdjuntoRecibido,
    AdjuntoRegistrado,
    ConsultarCorreoIafas,
    ContenidoAdjunto,
    CorreoPorRegistrar,
    CorreoRecibido,
    CorreoRegistrado,
    DescargarAdjuntoCorreo,
    DescartarCorreoIafas,
    ErrorCorreoInexistente,
    ErrorCorreoRemitenteInvalido,
    ErrorCorreos,
    ErrorCorreoYaResuelto,
    ErrorCuentaDesconocida,
    ErrorMotivoRequerido,
    EstadoCorreo,
    MotivoOmision,
    MotivoRevision,
    RegistrarCorreoIafas,
    Resolucion,
    Solicitante,
    VincularCorreoIafas,
    comunicacion_autorizada,
    evaluar_adjuntos,
    huella_de,
    remitente_coincide,
    validar_remitentes,
)
from app.dominio.puertos_comunes import Evento
from app.infraestructura.comunicaciones.fuentes import interpretar_correo
from app.infraestructura.persistencia.modelos_integracion import IafasModelo
from app.infraestructura.persistencia.repositorio_avisos_sql import RepositorioAvisosSql
from app.infraestructura.persistencia.repositorio_correos_sql import RepositorioCorreosSql

_AHORA = datetime(2026, 11, 15, 10, 0, 0)
_REMITENTE = "auditoria@iafas.test"
_REMITENTES = {"96969": _REMITENTE}
_PDF = b"%PDF-1.4 contenido del documento"
_SOLICITANTE = Solicitante(usuario_id=7, nombre_usuario="analista.prueba")


class _RelojFijo:
    def ahora(self) -> datetime:
        return _AHORA


@dataclass
class _RegistroEventosFalso:
    eventos: list[Evento] = field(default_factory=list)

    async def registrar(self, evento: Evento) -> None:
        self.eventos.append(evento)


def _comunicacion(codigo_iafas: str = "96969") -> ComunicacionIafas:
    return ComunicacionIafas(
        codigo="COM-000001",
        canal="CORREO",
        tipo="LIQUIDACION",
        codigo_iafas=codigo_iafas,
        codigo_ipress="15995250",
        documento="F00100000001",
        datos={"monto_liquidado": "150.00"},
        emitida_en="2026-11-15T09:00:00",
    )


def _correo(
    comunicacion: ComunicacionIafas | None = None,
    remitente: str = _REMITENTE,
    adjuntos: tuple[AdjuntoRecibido, ...] = (),
) -> CorreoRecibido:
    return CorreoRecibido(
        huella=huella_de(f"{remitente}-{comunicacion}-{len(adjuntos)}".encode()),
        remitente=remitente,
        asunto="Solicitud de documentación adicional",
        fecha=_AHORA,
        texto="Necesitamos el informe médico del paciente.",
        adjuntos=adjuntos,
        comunicacion=comunicacion,
    )


@dataclass
class _ComunicacionesFalsas:
    cuenta_de_la_comunicacion: int | None = None
    registrada: bool = True

    async def obtener(self, codigo: str) -> ComunicacionRegistrada | None:
        if not self.registrada:
            return None
        base = _comunicacion()
        return ComunicacionRegistrada(
            codigo=codigo,
            canal=base.canal,
            tipo=base.tipo,
            codigo_iafas=base.codigo_iafas,
            codigo_ipress=base.codigo_ipress,
            documento=base.documento,
            datos=base.datos,
            emitida_en=base.emitida_en,
            cuenta_medica_id=self.cuenta_de_la_comunicacion,
            resultado="APLICADA" if self.cuenta_de_la_comunicacion else "NO_APLICADA",
            detalle=None,
            observacion_id=None,
            recibida_en=_AHORA,
            respuesta_remitida_en=None,
        )


@dataclass
class _CorreosFalsos:
    remitentes: dict[str, str] = field(default_factory=lambda: dict(_REMITENTES))
    registrados: list[CorreoPorRegistrar] = field(default_factory=list)
    guardado: CorreoRegistrado | None = None
    adjunto: ContenidoAdjunto | None = None
    cuentas: dict[str, int] = field(default_factory=dict)
    resoluciones: list[Resolucion] = field(default_factory=list)

    async def ya_registrado(self, huella: str) -> bool:
        return any(c.correo.huella == huella for c in self.registrados)

    async def remitentes_por_iafas(self) -> dict[str, str]:
        return self.remitentes

    async def registrar(self, correo: CorreoPorRegistrar, recibido_en: datetime) -> int:
        self.registrados.append(correo)
        return len(self.registrados)

    async def obtener(self, correo_id: int) -> CorreoRegistrado | None:
        return self.guardado

    async def listar(
        self, estado: str | None, cuenta_medica_id: int | None, limite: int = 200
    ) -> list[CorreoRegistrado]:
        return [self.guardado] if self.guardado else []

    async def contenido_adjunto(self, correo_id: int, adjunto_id: int) -> ContenidoAdjunto | None:
        return self.adjunto

    async def resolver(self, correo_id: int, resolucion: Resolucion) -> None:
        self.resoluciones.append(resolucion)

    async def cuenta_por_identificacion(self, identificacion_interna: str) -> int | None:
        return self.cuentas.get(identificacion_interna)


def _guardado(estado: EstadoCorreo = EstadoCorreo.POR_REVISAR) -> CorreoRegistrado:
    return CorreoRegistrado(
        id=1,
        remitente=_REMITENTE,
        codigo_iafas="96969",
        asunto="Asunto",
        fecha=_AHORA,
        recibido_en=_AHORA,
        estado=estado.value,
        motivo_revision=MotivoRevision.SIN_FORMATO.value,
        comunicacion_codigo=None,
        cuenta_medica_id=None,
        identificacion_interna=None,
        huella="a" * 64,
        resuelto_por=None,
        resuelto_en=None,
        nota_resolucion=None,
        cantidad_adjuntos=1,
        texto="Texto",
        adjuntos=(AdjuntoRegistrado(1, "doc.pdf", "application/pdf", 10, "b" * 64, True, None),),
    )


# --- Adjuntos y remitentes -------------------------------------------------


def prueba_adjunto_permitido_se_almacena_con_su_huella() -> None:
    (evaluado,) = evaluar_adjuntos((AdjuntoRecibido("informe.pdf", "application/pdf", _PDF),))
    assert evaluado.contenido == _PDF
    assert evaluado.motivo_omision is None
    assert evaluado.huella == huella_de(_PDF)
    assert evaluado.tamano == len(_PDF)


@pytest.mark.parametrize("nombre", ["programa.exe", "macro.xlsm", "pagina.html", "sin_extension"])
def prueba_adjunto_de_tipo_no_permitido_no_se_almacena(nombre: str) -> None:
    (evaluado,) = evaluar_adjuntos((AdjuntoRecibido(nombre, "application/octet-stream", b"x"),))
    assert evaluado.contenido is None
    assert evaluado.motivo_omision is MotivoOmision.TIPO_NO_PERMITIDO
    assert evaluado.huella == huella_de(b"x")


def prueba_adjunto_que_excede_el_tamano_no_se_almacena() -> None:
    grande = b"0" * (TAMANO_MAXIMO_ADJUNTO + 1)
    (evaluado,) = evaluar_adjuntos((AdjuntoRecibido("grande.pdf", "application/pdf", grande),))
    assert evaluado.contenido is None
    assert evaluado.motivo_omision is MotivoOmision.EXCEDE_TAMANO


def prueba_adjuntos_por_encima_de_la_cantidad_no_se_almacenan() -> None:
    adjuntos = tuple(
        AdjuntoRecibido(f"doc{i}.pdf", "application/pdf", _PDF) for i in range(MAXIMO_ADJUNTOS + 1)
    )
    evaluados = evaluar_adjuntos(adjuntos)
    assert all(a.motivo_omision is None for a in evaluados[:MAXIMO_ADJUNTOS])
    assert evaluados[-1].motivo_omision is MotivoOmision.EXCEDE_CANTIDAD


@pytest.mark.parametrize(
    "remitente,registrados,esperado",
    [
        ("auditoria@iafas.test", "auditoria@iafas.test", True),
        ("Auditoria@IAFAS.test", "auditoria@iafas.test", True),
        ("glosas@iafas.test", "@iafas.test", True),
        ("glosas@iafas.test", "auditoria@iafas.test, glosas@iafas.test", True),
        ("auditoria@iafas.test.atacante.com", "@iafas.test", False),
        ("otro@correo.com", "auditoria@iafas.test", False),
        ("auditoria@iafas.test", None, False),
    ],
)
def prueba_coincidencia_del_remitente(
    remitente: str, registrados: str | None, esperado: bool
) -> None:
    assert remitente_coincide(remitente, registrados) is esperado


def prueba_validar_remitentes_normaliza_y_rechaza_lo_que_no_es_un_correo() -> None:
    assert validar_remitentes(" Auditoria@Iafas.test , @iafas.test ") == (
        "auditoria@iafas.test, @iafas.test"
    )
    assert validar_remitentes("  ") is None
    for invalido in ("auditoria", "auditoria@iafas", "a b@iafas.test", "a@b@iafas.test"):
        with pytest.raises(ErrorCorreoRemitenteInvalido):
            validar_remitentes(invalido)


# --- Lectura del buzon -----------------------------------------------------


def _mensaje(con_comunicacion: bool, contenido_json: bytes | None = None) -> bytes:
    mensaje = EmailMessage()
    mensaje["Subject"] = "Solicitud de documentación"
    mensaje["From"] = "Auditoría IAFAS <Auditoria@IAFAS.test>"
    mensaje["To"] = "cuentasmedicas@clinica.test"
    mensaje["Date"] = "Sun, 15 Nov 2026 09:30:00 -0500"
    mensaje.set_content("Estimados: adjuntamos el pedido.")
    mensaje.add_attachment(_PDF, maintype="application", subtype="pdf", filename="pedido.pdf")
    if con_comunicacion:
        adjunto = (
            contenido_json
            or json.dumps(
                {
                    "codigo": "COM-000009",
                    "tipo": "PAGO",
                    "codigo_iafas": "96969",
                    "codigo_ipress": "15995250",
                    "documento": "F00100000001",
                    "datos": {"monto_pagado": "10.00"},
                    "emitida_en": "2026-11-15T09:00:00",
                }
            ).encode()
        )
        mensaje.add_attachment(
            adjunto, maintype="application", subtype="json", filename="comunicacion.json"
        )
    return mensaje.as_bytes()


def prueba_correo_libre_se_interpreta_con_remitente_texto_y_adjuntos() -> None:
    crudo = _mensaje(con_comunicacion=False)
    correo = interpretar_correo(crudo)
    assert correo.huella == huella_de(crudo)
    assert correo.remitente == "auditoria@iafas.test"
    assert correo.asunto == "Solicitud de documentación"
    assert correo.texto == "Estimados: adjuntamos el pedido."
    assert correo.fecha is not None and correo.fecha.tzinfo is not None
    assert [(a.nombre, a.contenido) for a in correo.adjuntos] == [("pedido.pdf", _PDF)]
    assert correo.comunicacion is None


def prueba_correo_con_el_formato_de_la_iafas_trae_su_comunicacion() -> None:
    correo = interpretar_correo(_mensaje(con_comunicacion=True))
    assert correo.comunicacion is not None
    assert correo.comunicacion.codigo == "COM-000009"
    assert correo.comunicacion.canal == "CORREO"
    assert len(correo.adjuntos) == 2


@pytest.mark.parametrize("ilegible", [b"esto no es json", b'{"codigo": "COM-1"}', b"[1, 2]"])
def prueba_comunicacion_ilegible_no_detiene_la_lectura(ilegible: bytes) -> None:
    correo = interpretar_correo(_mensaje(con_comunicacion=True, contenido_json=ilegible))
    assert correo.comunicacion is None
    assert len(correo.adjuntos) == 2


# --- Registro del correo ---------------------------------------------------


async def prueba_correo_sin_formato_de_remitente_registrado_queda_por_revisar() -> None:
    correos = _CorreosFalsos()
    adjuntos = (AdjuntoRecibido("pedido.pdf", "application/pdf", _PDF),)
    estado = await RegistrarCorreoIafas(correos, _ComunicacionesFalsas(), _RelojFijo()).ejecutar(
        _correo(adjuntos=adjuntos)
    )
    assert estado is EstadoCorreo.POR_REVISAR
    (registrado,) = correos.registrados
    assert registrado.motivo_revision is MotivoRevision.SIN_FORMATO
    assert registrado.codigo_iafas == "96969"
    assert registrado.cuenta_medica_id is None
    assert registrado.adjuntos[0].contenido == _PDF


async def prueba_correo_de_remitente_no_registrado_queda_por_revisar() -> None:
    correos = _CorreosFalsos()
    estado = await RegistrarCorreoIafas(correos, _ComunicacionesFalsas(), _RelojFijo()).ejecutar(
        _correo(remitente="desconocido@otro.com")
    )
    assert estado is EstadoCorreo.POR_REVISAR
    assert correos.registrados[0].motivo_revision is MotivoRevision.REMITENTE_NO_REGISTRADO
    assert correos.registrados[0].codigo_iafas is None


async def prueba_comunicacion_de_remitente_no_registrado_no_se_aplica_sola() -> None:
    # Un correo con el formato de la IAFAS enviado desde otro buzon (una
    # suplantacion) no debe registrar una liquidacion ni un pago.
    suplantado = _correo(_comunicacion(), remitente="auditoria@iafas-falsa.com")
    assert comunicacion_autorizada(suplantado, _REMITENTES) is False
    correos = _CorreosFalsos()
    estado = await RegistrarCorreoIafas(
        correos, _ComunicacionesFalsas(cuenta_de_la_comunicacion=5), _RelojFijo()
    ).ejecutar(suplantado)
    assert estado is EstadoCorreo.POR_REVISAR
    (registrado,) = correos.registrados
    assert registrado.motivo_revision is MotivoRevision.REMITENTE_NO_REGISTRADO
    assert registrado.comunicacion_codigo is None
    assert registrado.cuenta_medica_id is None


async def prueba_comunicacion_de_otra_iafas_no_se_aplica_sola() -> None:
    # El remitente esta registrado para la 96969, no para la 05292.
    ajena = _correo(_comunicacion(codigo_iafas="05292"))
    assert comunicacion_autorizada(ajena, _REMITENTES) is False


async def prueba_comunicacion_autorizada_y_aplicada_deja_el_correo_procesado() -> None:
    correo = _correo(_comunicacion())
    assert comunicacion_autorizada(correo, _REMITENTES) is True
    correos = _CorreosFalsos()
    estado = await RegistrarCorreoIafas(
        correos, _ComunicacionesFalsas(cuenta_de_la_comunicacion=5), _RelojFijo()
    ).ejecutar(correo)
    assert estado is EstadoCorreo.PROCESADO
    (registrado,) = correos.registrados
    assert registrado.motivo_revision is None
    assert registrado.comunicacion_codigo == "COM-000001"
    assert registrado.cuenta_medica_id == 5


async def prueba_comprobante_desconocido_deja_el_correo_por_revisar() -> None:
    correos = _CorreosFalsos()
    estado = await RegistrarCorreoIafas(
        correos, _ComunicacionesFalsas(cuenta_de_la_comunicacion=None), _RelojFijo()
    ).ejecutar(_correo(_comunicacion()))
    assert estado is EstadoCorreo.POR_REVISAR
    assert correos.registrados[0].motivo_revision is MotivoRevision.COMPROBANTE_DESCONOCIDO
    assert correos.registrados[0].comunicacion_codigo == "COM-000001"


async def prueba_el_mismo_correo_no_se_registra_dos_veces() -> None:
    correos = _CorreosFalsos()
    caso_uso = RegistrarCorreoIafas(correos, _ComunicacionesFalsas(), _RelojFijo())
    assert await caso_uso.ejecutar(_correo()) is EstadoCorreo.POR_REVISAR
    assert await caso_uso.ejecutar(_correo()) is None
    assert len(correos.registrados) == 1


# --- Consulta, descarga, vinculacion y descarte ---------------------------


async def prueba_consultar_un_correo_queda_en_la_bitacora() -> None:
    eventos = _RegistroEventosFalso()
    correo = await ConsultarCorreoIafas(_CorreosFalsos(guardado=_guardado()), eventos).ejecutar(
        1, _SOLICITANTE
    )
    assert correo.texto == "Texto"
    (evento,) = eventos.eventos
    assert evento.tipo_evento == "CORREO_IAFAS_CONSULTADO"
    assert evento.sesion_usuario_id == 7
    assert evento.actor == "analista.prueba"
    assert evento.datos == {"correo_id": 1}


async def prueba_consultar_un_correo_inexistente_no_registra_nada() -> None:
    eventos = _RegistroEventosFalso()
    with pytest.raises(ErrorCorreoInexistente):
        await ConsultarCorreoIafas(_CorreosFalsos(), eventos).ejecutar(99, _SOLICITANTE)
    assert eventos.eventos == []


async def prueba_descargar_un_adjunto_verifica_la_huella_y_queda_en_la_bitacora() -> None:
    eventos = _RegistroEventosFalso()
    adjunto = ContenidoAdjunto("doc.pdf", "application/pdf", huella_de(_PDF), _PDF)
    descargado = await DescargarAdjuntoCorreo(_CorreosFalsos(adjunto=adjunto), eventos).ejecutar(
        1, 3, _SOLICITANTE
    )
    assert descargado.contenido == _PDF
    (evento,) = eventos.eventos
    assert evento.tipo_evento == "ADJUNTO_CORREO_IAFAS_DESCARGADO"
    assert evento.datos == {"correo_id": 1, "adjunto_id": 3, "huella": huella_de(_PDF)}


async def prueba_adjunto_alterado_no_se_entrega() -> None:
    eventos = _RegistroEventosFalso()
    alterado = ContenidoAdjunto("doc.pdf", "application/pdf", huella_de(_PDF), b"otro contenido")
    with pytest.raises(ErrorCorreos):
        await DescargarAdjuntoCorreo(_CorreosFalsos(adjunto=alterado), eventos).ejecutar(
            1, 3, _SOLICITANTE
        )
    assert eventos.eventos == []


async def prueba_adjunto_no_almacenado_no_se_puede_descargar() -> None:
    with pytest.raises(ErrorCorreoInexistente):
        await DescargarAdjuntoCorreo(_CorreosFalsos(), _RegistroEventosFalso()).ejecutar(
            1, 3, _SOLICITANTE
        )


async def prueba_vincular_un_correo_lo_registra_en_el_historial_de_la_cuenta() -> None:
    eventos = _RegistroEventosFalso()
    correos = _CorreosFalsos(guardado=_guardado(), cuentas={"CM-0000042": 42})
    await VincularCorreoIafas(correos, eventos, _RelojFijo()).ejecutar(
        1, " CM-0000042 ", _SOLICITANTE
    )
    (resolucion,) = correos.resoluciones
    assert resolucion.estado is EstadoCorreo.VINCULADO
    assert resolucion.cuenta_medica_id == 42
    assert resolucion.usuario == "analista.prueba"
    (evento,) = eventos.eventos
    assert evento.tipo_evento == "CORREO_IAFAS_VINCULADO"
    assert evento.cuenta_medica_id == 42
    assert evento.datos == {"correo_id": 1, "huella": "a" * 64}


async def prueba_vincular_a_una_cuenta_que_no_existe_no_cambia_el_correo() -> None:
    eventos = _RegistroEventosFalso()
    correos = _CorreosFalsos(guardado=_guardado())
    with pytest.raises(ErrorCuentaDesconocida):
        await VincularCorreoIafas(correos, eventos, _RelojFijo()).ejecutar(
            1, "CM-9999999", _SOLICITANTE
        )
    assert correos.resoluciones == [] and eventos.eventos == []


@pytest.mark.parametrize("estado", [EstadoCorreo.VINCULADO, EstadoCorreo.DESCARTADO])
async def prueba_un_correo_ya_revisado_no_se_vuelve_a_resolver(estado: EstadoCorreo) -> None:
    correos = _CorreosFalsos(guardado=_guardado(estado), cuentas={"CM-0000042": 42})
    with pytest.raises(ErrorCorreoYaResuelto):
        await VincularCorreoIafas(correos, _RegistroEventosFalso(), _RelojFijo()).ejecutar(
            1, "CM-0000042", _SOLICITANTE
        )
    with pytest.raises(ErrorCorreoYaResuelto):
        await DescartarCorreoIafas(correos, _RegistroEventosFalso(), _RelojFijo()).ejecutar(
            1, "No corresponde a la clínica", _SOLICITANTE
        )
    assert correos.resoluciones == []


async def prueba_descartar_exige_un_motivo_y_queda_en_la_bitacora() -> None:
    eventos = _RegistroEventosFalso()
    correos = _CorreosFalsos(guardado=_guardado())
    caso_uso = DescartarCorreoIafas(correos, eventos, _RelojFijo())
    with pytest.raises(ErrorMotivoRequerido):
        await caso_uso.ejecutar(1, "  no ", _SOLICITANTE)
    assert correos.resoluciones == []
    await caso_uso.ejecutar(1, "Publicidad de un proveedor", _SOLICITANTE)
    (resolucion,) = correos.resoluciones
    assert resolucion.estado is EstadoCorreo.DESCARTADO
    assert resolucion.nota == "Publicidad de un proveedor"
    (evento,) = eventos.eventos
    assert evento.tipo_evento == "CORREO_IAFAS_DESCARTADO"
    assert evento.sesion_usuario_id == 7
    assert evento.datos["motivo"] == "Publicidad de un proveedor"


# --- Persistencia ----------------------------------------------------------


async def _registrar_en_base(sesion: AsyncSession) -> tuple[int, str]:
    sesion.add(
        IafasModelo(
            codigo="96969",
            razon_social="IAFAS de prueba",
            periodicidad_remision_dias=30,
            ventana_monitoreo_horas=72,
            correo_remitente=_REMITENTE,
        )
    )
    await sesion.commit()
    adjuntos = (
        AdjuntoRecibido("informe del paciente.pdf", "application/pdf", _PDF),
        AdjuntoRecibido("programa.exe", "application/octet-stream", b"MZ"),
    )
    correo = _correo(adjuntos=adjuntos)
    repositorio = RepositorioCorreosSql(sesion)
    assert await repositorio.remitentes_por_iafas() == _REMITENTES
    correo_id = await repositorio.registrar(
        CorreoPorRegistrar(
            correo=correo,
            codigo_iafas="96969",
            estado=EstadoCorreo.POR_REVISAR,
            motivo_revision=MotivoRevision.SIN_FORMATO,
            comunicacion_codigo=None,
            cuenta_medica_id=None,
            adjuntos=evaluar_adjuntos(adjuntos),
        ),
        _AHORA,
    )
    return correo_id, correo.huella


async def prueba_repositorio_registra_lista_y_entrega_el_correo(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        correo_id, huella = await _registrar_en_base(sesion)
        repositorio = RepositorioCorreosSql(sesion)
        assert await repositorio.ya_registrado(huella)
        assert not await repositorio.ya_registrado("0" * 64)
        (resumen,) = await repositorio.listar(EstadoCorreo.POR_REVISAR.value, None)
        assert resumen.id == correo_id
        assert resumen.cantidad_adjuntos == 2
        assert resumen.texto is None
        assert await repositorio.listar(EstadoCorreo.PROCESADO.value, None) == []
        detalle = await repositorio.obtener(correo_id)
        assert detalle is not None
        assert detalle.texto == "Necesitamos el informe médico del paciente."
        almacenado, omitido = detalle.adjuntos
        assert almacenado.nombre == "informe del paciente.pdf" and almacenado.almacenado
        assert omitido.almacenado is False
        assert omitido.motivo_omision == MotivoOmision.TIPO_NO_PERMITIDO.value
        contenido = await repositorio.contenido_adjunto(correo_id, almacenado.id)
        assert contenido is not None and contenido.contenido == _PDF
        assert await repositorio.contenido_adjunto(correo_id, omitido.id) is None
        assert await repositorio.contenido_adjunto(correo_id + 1, almacenado.id) is None
        assert await repositorio.cuenta_por_identificacion("CM-9999999") is None


async def prueba_el_correo_y_sus_adjuntos_se_guardan_cifrados(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        await _registrar_en_base(sesion)
        asunto, texto = (
            await sesion.execute(sa.text("SELECT asunto, texto FROM correo_iafas"))
        ).one()
        assert "documentación" not in asunto and "Solicitud" not in asunto
        assert "informe" not in texto and "paciente" not in texto
        filas = (
            await sesion.execute(
                sa.text("SELECT nombre, contenido FROM adjunto_correo_iafas ORDER BY id")
            )
        ).all()
        assert "informe" not in filas[0][0] and "paciente" not in filas[0][0]
        assert filas[0][1] is not None and b"%PDF" not in bytes(filas[0][1])
        # El contenido de un adjunto no permitido nunca entra a la base.
        assert filas[1][1] is None


async def prueba_correo_por_revisar_es_un_aviso_hasta_que_se_resuelve(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        correo_id, _ = await _registrar_en_base(sesion)
        avisos = RepositorioAvisosSql(sesion)
        (aviso,) = await avisos.listar([TIPO_AVISO_CORREO_POR_REVISAR], 50)
        assert aviso.evento_id == f"correo-{correo_id}"
        assert aviso.datos["correo_id"] == correo_id
        assert aviso.datos["motivo"] == MotivoRevision.SIN_FORMATO.value
        (evaluado,) = await avisos.evaluar_atencion([aviso])
        assert evaluado.atendido is False

        repositorio = RepositorioCorreosSql(sesion)
        await repositorio.resolver(
            correo_id,
            Resolucion(EstadoCorreo.DESCARTADO, None, "jefe.prueba", _AHORA, "No corresponde"),
        )
        await sesion.commit()
        assert await avisos.listar([TIPO_AVISO_CORREO_POR_REVISAR], 50) == []
        resuelto = await repositorio.obtener(correo_id)
        assert resuelto is not None
        assert resuelto.estado == EstadoCorreo.DESCARTADO.value
        assert resuelto.motivo_revision is None
        assert resuelto.resuelto_por == "jefe.prueba"
        assert resuelto.nota_resolucion == "No corresponde"


def prueba_cada_correo_por_revisar_es_un_aviso_propio() -> None:
    def aviso(correo_id: int) -> EventoAviso:
        return EventoAviso(
            evento_id=f"correo-{correo_id}",
            tipo_evento=TIPO_AVISO_CORREO_POR_REVISAR,
            ocurrido_en=_AHORA,
            datos={"correo_id": correo_id},
            cuenta_medica_id=None,
            identificacion_interna=None,
            lote_id=None,
            numero_lote=None,
        )

    assert clave_agrupacion(aviso(1)) != clave_agrupacion(aviso(2))
