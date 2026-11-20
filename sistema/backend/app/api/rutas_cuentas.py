"""Seccion 11: /cuentas. `GET /cuentas`, `GET /cuentas/{id}`, `GET
/cuentas/{id}/completitud` para analista, auditor, jefe y tesoreria
(Tabla 46, "consultar las cuentas y su detalle" -- tesoreria se agrego
en la Fase 30, al consolidar la matriz de permisos contra las fases del
OE2/OE3); `POST /cuentas` (adenda de ingesta), `POST
/cuentas/{id}/cobertura`, `POST /cuentas/{id}/comprobante` (adenda,
emision via el simulador PSE) solo para analista (Fase 18); `GET
/cuentas/{id}/acreditacion` para analista, auditor y jefe. `GET /iafas` para cualquier autenticado
(Fase 19: selector de IAFAS de la pantalla de generacion de lotes) -- sin
prefijo `/cuentas`, por eso vive en un `APIRouter` aparte dentro de este
mismo archivo."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencias import obtener_usuario_actual, requiere_rol
from app.api.dependencias_cuentas import (
    construir_buscar_asegurado,
    construir_buscar_cie10,
    construir_consultar_completitud,
    construir_emitir_comprobante_pago,
    construir_listar_cuentas,
    construir_listar_iafas,
    construir_obtener_acreditacion,
    construir_obtener_cuenta,
    construir_registrar_cuenta,
    construir_solicitar_verificacion_cobertura,
)
from app.api.esquemas_cuentas import (
    AcreditacionRespuesta,
    AseguradoRegistradoRespuesta,
    DetalleCuentaRespuesta,
    RespuestaCompletitudCuenta,
    RespuestaComprobantePago,
    RespuestaCuentaCreada,
    RespuestaDiagnostico,
    RespuestaTrabajoEncolado,
    ResumenCie10Respuesta,
    ResumenCuentaRespuesta,
    ResumenIafasRespuesta,
    SolicitudBuscarAsegurado,
    SolicitudDiagnostico,
    SolicitudNuevaCuenta,
)
from app.compartido.errores import ErrorAplicacion
from app.dominio.acceso.entidades import NombreRol
from app.dominio.acceso.puertos import CargaSesion
from app.dominio.acceso.valores import accede_a_datos_clinicos
from app.dominio.acreditacion.casos_uso import ObtenerAcreditacion, SolicitarVerificacionCobertura
from app.dominio.acreditacion.puertos import ErrorAcreditacion, ErrorCuentaNoEncontrada
from app.dominio.integracion.casos_uso_consulta import (
    BuscarCie10,
    ListarCuentas,
    ListarIafas,
    ObtenerCuenta,
)
from app.dominio.integracion.casos_uso_ingesta import (
    BuscarAseguradoRegistrado,
    ConsultarCompletitudCuenta,
    RegistrarCuentaMedica,
)
from app.dominio.integracion.diagnostico_cuenta import (
    ErrorCie10Inexistente,
    ErrorCuentaInexistenteDiagnostico,
    ErrorDiagnostico,
    RegistrarDiagnosticoPrincipal,
)
from app.dominio.integracion.puertos_ingesta import ErrorIafasInexistente
from app.dominio.orquestacion.valores import EtapaCiclo
from app.dominio.pse.casos_uso import EmitirComprobantePago, ErrorCuentaCerradaComprobante
from app.dominio.pse.puertos import ErrorComprobanteYaExiste, ErrorFaltaParaFacturar
from app.dominio.pse.puertos import ErrorCuentaNoEncontrada as ErrorCuentaNoEncontradaPse
from app.infraestructura.observabilidad.registro import obtener_registrador
from app.infraestructura.persistencia.base import obtener_sesion
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_diagnostico_cuenta_sql import (
    RepositorioDiagnosticoCuentaSql,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)

router = APIRouter(prefix="/cuentas", tags=["cuentas"])
router_iafas = APIRouter(tags=["cuentas"])
_registrador = obtener_registrador("api.cuentas")

_LECTURA = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE, NombreRol.TESORERIA)
_SOLO_ANALISTA = requiere_rol(NombreRol.ANALISTA)
_VE_ACREDITACION = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR, NombreRol.JEFE)
# El diagnostico lo registra la admision y lo confirma el auditor medico.
_REGISTRA_DIAGNOSTICO = requiere_rol(NombreRol.ANALISTA, NombreRol.AUDITOR)


@router_iafas.get("/iafas", response_model=list[ResumenIafasRespuesta])
async def listar_iafas(
    caso_uso: ListarIafas = Depends(construir_listar_iafas),
    _actor: CargaSesion = Depends(obtener_usuario_actual),
) -> list[ResumenIafasRespuesta]:
    iafas = await caso_uso.ejecutar()
    return [ResumenIafasRespuesta.desde_valor(i) for i in iafas]


@router_iafas.get("/cie10/buscar", response_model=list[ResumenCie10Respuesta])
async def buscar_cie10(
    q: str = "",
    caso_uso: BuscarCie10 = Depends(construir_buscar_cie10),
    _actor: CargaSesion = Depends(obtener_usuario_actual),
) -> list[ResumenCie10Respuesta]:
    resultados = await caso_uso.ejecutar(q)
    return [ResumenCie10Respuesta.desde_valor(r) for r in resultados]


@router.post("/asegurado/buscar", response_model=AseguradoRegistradoRespuesta | None)
async def buscar_asegurado(
    solicitud: SolicitudBuscarAsegurado,
    caso_uso: BuscarAseguradoRegistrado = Depends(construir_buscar_asegurado),
    _actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> AseguradoRegistradoRespuesta | None:
    """Al registrar una cuenta: nombres e IAFAS del asegurado, si la clinica
    ya lo atendio. `null` si es la primera vez."""
    asegurado = await caso_uso.ejecutar(solicitud.tipo_documento, solicitud.numero_documento)
    if asegurado is None:
        return None
    return AseguradoRegistradoRespuesta(
        nombres=asegurado.nombres, apellidos=asegurado.apellidos, iafas_id=asegurado.iafas_id
    )


@router.post("", response_model=RespuestaCuentaCreada, status_code=status.HTTP_201_CREATED)
async def registrar_cuenta(
    solicitud: SolicitudNuevaCuenta,
    caso_uso: RegistrarCuentaMedica = Depends(construir_registrar_cuenta),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaCuentaCreada:
    try:
        cuenta_id = await caso_uso.ejecutar(solicitud.a_valor(), actor.nombre_usuario)
    except ErrorIafasInexistente as error:
        raise ErrorAplicacion(
            "IAFAS_INEXISTENTE", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    return RespuestaCuentaCreada(cuenta_id=cuenta_id)


@router.get("", response_model=list[ResumenCuentaRespuesta])
async def listar_cuentas(
    estado: str | None = None,
    iafas_codigo: str | None = None,
    fecha_prestacion: date | None = None,
    etapa: EtapaCiclo | None = None,
    caso_uso: ListarCuentas = Depends(construir_listar_cuentas),
    _actor: CargaSesion = Depends(_LECTURA),
) -> list[ResumenCuentaRespuesta]:
    cuentas = await caso_uso.ejecutar(estado, iafas_codigo, fecha_prestacion, etapa)
    return [ResumenCuentaRespuesta.desde_valor(c) for c in cuentas]


@router.get("/{cuenta_id}", response_model=DetalleCuentaRespuesta)
async def obtener_cuenta(
    cuenta_id: int,
    caso_uso: ObtenerCuenta = Depends(construir_obtener_cuenta),
    actor: CargaSesion = Depends(_LECTURA),
) -> DetalleCuentaRespuesta:
    cuenta = await caso_uso.ejecutar(cuenta_id, accede_a_datos_clinicos(actor.roles))
    if cuenta is None:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA",
            f"No existe la cuenta medica {cuenta_id}.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return DetalleCuentaRespuesta.desde_valor(cuenta)


@router.post(
    "/{cuenta_id}/cobertura",
    response_model=RespuestaTrabajoEncolado,
    status_code=status.HTTP_202_ACCEPTED,
)
async def solicitar_verificacion_cobertura(
    cuenta_id: int,
    caso_uso: SolicitarVerificacionCobertura = Depends(construir_solicitar_verificacion_cobertura),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaTrabajoEncolado:
    try:
        # Control C-07 (Seccion 5.2.7): el robot ejecuta esto en otro
        # proceso; sin pasar el actor aqui, COBERTURA_VERIFICADA no tendria
        # como saber a que analista atribuirselo.
        trabajo_id = await caso_uso.ejecutar(cuenta_id, actor.nombre_usuario)
    except ErrorCuentaNoEncontrada as error:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorAcreditacion as error:
        raise ErrorAplicacion(
            "CUENTA_YA_ACREDITADA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaTrabajoEncolado(trabajo_id=trabajo_id)


@router.get("/{cuenta_id}/completitud", response_model=RespuestaCompletitudCuenta)
async def consultar_completitud_cuenta(
    cuenta_id: int,
    caso_uso: ConsultarCompletitudCuenta = Depends(construir_consultar_completitud),
    _actor: CargaSesion = Depends(_LECTURA),
) -> RespuestaCompletitudCuenta:
    resultado = await caso_uso.ejecutar(cuenta_id)
    if resultado is None:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA",
            f"No existe la cuenta medica {cuenta_id}.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return RespuestaCompletitudCuenta.desde_valor(resultado)


@router.post(
    "/{cuenta_id}/comprobante",
    response_model=RespuestaComprobantePago,
    status_code=status.HTTP_201_CREATED,
)
async def emitir_comprobante_pago(
    cuenta_id: int,
    caso_uso: EmitirComprobantePago = Depends(construir_emitir_comprobante_pago),
    actor: CargaSesion = Depends(_SOLO_ANALISTA),
) -> RespuestaComprobantePago:
    try:
        resultado = await caso_uso.ejecutar(cuenta_id, actor.nombre_usuario)
    except ErrorCuentaNoEncontradaPse as error:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorComprobanteYaExiste as error:
        raise ErrorAplicacion(
            "COMPROBANTE_YA_EXISTE", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorCuentaCerradaComprobante as error:
        raise ErrorAplicacion(
            "CUENTA_CERRADA", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    except ErrorFaltaParaFacturar as error:
        raise ErrorAplicacion(
            "FALTA_PARA_FACTURAR", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    return RespuestaComprobantePago.desde_valor(resultado)


@router.put("/{cuenta_id}/diagnostico", response_model=RespuestaDiagnostico)
async def registrar_diagnostico(
    cuenta_id: int,
    solicitud: SolicitudDiagnostico,
    sesion: AsyncSession = Depends(obtener_sesion),
    actor: CargaSesion = Depends(_REGISTRA_DIAGNOSTICO),
) -> RespuestaDiagnostico:
    """Completa el diagnostico principal de una cuenta ya registrada: sin
    el la cuenta no se factura ni puede entrar a un lote (T2, campo 18)."""
    caso_uso = RegistrarDiagnosticoPrincipal(
        RepositorioDiagnosticoCuentaSql(sesion),
        RegistroEventosSql(sesion),
        RepositorioEstadoCuentaSql(sesion),
    )
    try:
        codigo = await caso_uso.ejecutar(cuenta_id, solicitud.codigo_cie10, actor.nombre_usuario)
    except ErrorCuentaInexistenteDiagnostico as error:
        raise ErrorAplicacion(
            "CUENTA_NO_ENCONTRADA", str(error), estado_http=status.HTTP_404_NOT_FOUND
        ) from error
    except ErrorCie10Inexistente as error:
        raise ErrorAplicacion(
            "CIE10_INEXISTENTE", str(error), estado_http=status.HTTP_400_BAD_REQUEST
        ) from error
    except ErrorDiagnostico as error:
        raise ErrorAplicacion(
            "DIAGNOSTICO_NO_ADMITIDO", str(error), estado_http=status.HTTP_409_CONFLICT
        ) from error
    await sesion.commit()
    return RespuestaDiagnostico(codigo_cie10=codigo)


@router.get("/{cuenta_id}/acreditacion", response_model=AcreditacionRespuesta)
async def obtener_acreditacion(
    cuenta_id: int,
    caso_uso: ObtenerAcreditacion = Depends(construir_obtener_acreditacion),
    _actor: CargaSesion = Depends(_VE_ACREDITACION),
) -> AcreditacionRespuesta:
    acreditacion = await caso_uso.ejecutar(cuenta_id)
    if acreditacion is None:
        raise ErrorAplicacion(
            "ACREDITACION_NO_ENCONTRADA",
            f"La cuenta medica {cuenta_id} no tiene acreditacion registrada.",
            estado_http=status.HTTP_404_NOT_FOUND,
        )
    return AcreditacionRespuesta.desde_valor(acreditacion)
