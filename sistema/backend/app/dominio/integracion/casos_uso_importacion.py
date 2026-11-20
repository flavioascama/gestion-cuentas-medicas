"""Importar la atencion cerrada desde el sistema hospitalario (2026-11-19).
Un solo caso de uso para las dos vias: la consulta al sistema hospitalario
y el archivo exportado por el. La cuenta manual ("Nueva cuenta") no cambia."""

from __future__ import annotations

from decimal import Decimal

from app.dominio.farmacia.dispensacion import (
    DatosProductoDispensado,
    ErrorProductoInvalido,
    validar_dispensacion,
)
from app.dominio.integracion.atencion_hospitalaria import (
    AREAS_PROCEDIMIENTO,
    TIPO_HOSPITALIZACION,
    TIPOS_ATENCION,
    VIA_CONSULTA,
    AtencionHospitalaria,
    CuentaImportada,
    ErrorAtencionInvalida,
    ErrorAtencionNoEncontrada,
    ErrorAtencionYaImportada,
    FuenteAtenciones,
    ProcedimientoAtencion,
    ProductoAtencion,
    ProductoImportado,
    RepositorioImportacionAtencion,
    ResumenAtencionHospitalaria,
)
from app.dominio.orquestacion.motor import validar_transicion
from app.dominio.orquestacion.valores import TipoTransicion
from app.dominio.puertos_comunes import Evento, RegistroEventos

# Anchos del Anexo 1: T2 campo 11 (historia clinica), T2 campo 24
# (colegiatura), T2 campo 34 (dias de estancia) y T3 campo 9 en la tabla.
_LONGITUD_HISTORIA_CLINICA = 8
_LONGITUD_COLEGIATURA = 6
_MAXIMO_DIAS_ESTANCIA = 999
_LONGITUD_DESCRIPCION = 500
# El producto llega sin exclusion ni exoneracion: se toma lo no exonerado
# (T4 campo 18 = 'A') sin monto no cubierto, igual que el valor por defecto
# del registro manual.
_SIN_EXONERACION = "A"
_CERO = Decimal("0.00")


def _invalida(codigo: str, mensaje: str) -> ErrorAtencionInvalida:
    return ErrorAtencionInvalida(codigo, mensaje)


def _validar_cabecera(atencion: AtencionHospitalaria) -> None:
    if atencion.tipo_atencion not in TIPOS_ATENCION:
        raise _invalida("TIPO_ATENCION_INVALIDO", f"Tipo de atencion {atencion.tipo_atencion!r}.")
    historia = atencion.numero_historia_clinica.strip()
    if not historia or len(historia) > _LONGITUD_HISTORIA_CLINICA:
        raise _invalida(
            "HISTORIA_CLINICA_INVALIDA",
            f"La historia clinica debe tener de 1 a {_LONGITUD_HISTORIA_CLINICA} caracteres.",
        )
    colegiatura = atencion.profesional.numero_colegiatura.strip()
    if not colegiatura.isdigit() or len(colegiatura) > _LONGITUD_COLEGIATURA:
        raise _invalida(
            "PROFESIONAL_INVALIDO",
            f"La colegiatura del medico debe tener de 1 a {_LONGITUD_COLEGIATURA} digitos.",
        )
    if not atencion.diagnostico_principal_cie10.strip():
        raise _invalida("CIE10_DESCONOCIDO", "La atencion no trae el diagnostico principal.")


def _validar_hospitalizacion(atencion: AtencionHospitalaria) -> None:
    hospitalizacion = atencion.hospitalizacion
    if atencion.tipo_atencion != TIPO_HOSPITALIZACION:
        if hospitalizacion is not None:
            raise _invalida(
                "HOSPITALIZACION_INVALIDA",
                "Solo una atencion de hospitalizacion trae fechas de hospitalizacion.",
            )
        return
    if hospitalizacion is None or None in (
        hospitalizacion.fecha_ingreso,
        hospitalizacion.fecha_alta,
    ):
        raise _invalida(
            "HOSPITALIZACION_INVALIDA", "La hospitalizacion no trae la fecha de ingreso y de alta."
        )
    ingreso, alta = hospitalizacion.fecha_ingreso, hospitalizacion.fecha_alta
    assert ingreso is not None and alta is not None
    # T2 campos 31 y 32, criterio C1 de cada uno.
    if ingreso < atencion.fecha_prestacion or alta < ingreso:
        raise _invalida(
            "HOSPITALIZACION_INVALIDA",
            "Las fechas de hospitalizacion no son coherentes: el ingreso no puede ser anterior "
            "a la prestacion ni el alta anterior al ingreso.",
        )
    if (alta - ingreso).days > _MAXIMO_DIAS_ESTANCIA:
        raise _invalida("HOSPITALIZACION_INVALIDA", "La estancia supera los 999 dias.")


def _validar_procedimiento(
    procedimiento: ProcedimientoAtencion, atencion: AtencionHospitalaria
) -> None:
    descripcion = procedimiento.descripcion.strip()
    if not descripcion or len(descripcion) > _LONGITUD_DESCRIPCION:
        raise _invalida("PROCEDIMIENTO_INVALIDO", "Un procedimiento no trae descripcion valida.")
    if procedimiento.area not in AREAS_PROCEDIMIENTO:
        raise _invalida("PROCEDIMIENTO_INVALIDO", f"Area {procedimiento.area!r} desconocida.")
    if procedimiento.cantidad <= 0 or procedimiento.monto_unitario <= 0:
        raise _invalida(
            "PROCEDIMIENTO_INVALIDO",
            f"El procedimiento {descripcion!r} debe tener cantidad y monto mayores que cero.",
        )
    # T3 campo 10, criterio C2: no anterior a la prestacion.
    if procedimiento.fecha < atencion.fecha_prestacion:
        raise _invalida(
            "PROCEDIMIENTO_INVALIDO",
            f"El procedimiento {descripcion!r} tiene fecha anterior a la prestacion.",
        )


def validar_atencion(atencion: AtencionHospitalaria) -> None:
    """Todo lo que se valida sin consultar la base. Lanza ErrorAtencionInvalida."""
    _validar_cabecera(atencion)
    _validar_hospitalizacion(atencion)
    if not atencion.procedimientos:
        raise _invalida("ATENCION_SIN_PROCEDIMIENTOS", "La atencion no trae procedimientos.")
    for procedimiento in atencion.procedimientos:
        _validar_procedimiento(procedimiento, atencion)
    copago = atencion.copago_cobrado
    if copago is not None and (copago.monto <= 0 or not copago.referencia.strip()):
        raise _invalida("COPAGO_INVALIDO", "El copago cobrado debe tener monto y referencia.")


class ImportarAtencion:
    def __init__(
        self, repositorio: RepositorioImportacionAtencion, registro_eventos: RegistroEventos
    ) -> None:
        self._repositorio = repositorio
        self._registro_eventos = registro_eventos

    async def ejecutar(self, atencion: AtencionHospitalaria, via: str, actor: str) -> int:
        existente = await self._repositorio.cuenta_de_atencion(atencion.atencion_id)
        if existente is not None:
            raise ErrorAtencionYaImportada(atencion.atencion_id, existente)
        validar_atencion(atencion)
        iafas_id = await self._repositorio.iafas_por_codigo(atencion.iafas_codigo)
        if iafas_id is None:
            raise _invalida(
                "IAFAS_DESCONOCIDA", f"La aseguradora {atencion.iafas_codigo!r} no esta registrada."
            )
        await self._exigir_cie10(atencion)
        productos = tuple([await self._producto(p, atencion) for p in atencion.farmacia])
        # T-01 (Tabla 58) validada por el motor, igual que la cuenta manual.
        estado_inicial = validar_transicion(None, TipoTransicion.REGISTRO)
        cuenta_id = await self._repositorio.crear_cuenta_importada(
            CuentaImportada(atencion, iafas_id, productos, actor)
        )
        await self._registrar_eventos(cuenta_id, atencion, (via, actor, estado_inicial, iafas_id))
        return cuenta_id

    async def _exigir_cie10(self, atencion: AtencionHospitalaria) -> None:
        codigos = (atencion.diagnostico_principal_cie10, *atencion.diagnosticos_secundarios_cie10)
        desconocidos = await self._repositorio.cie10_desconocidos(codigos)
        if desconocidos:
            raise _invalida(
                "CIE10_DESCONOCIDO",
                "Diagnosticos que no estan en el catalogo CIE-10: " + ", ".join(desconocidos) + ".",
            )

    async def _producto(
        self, producto: ProductoAtencion, atencion: AtencionHospitalaria
    ) -> ProductoImportado:
        datos = DatosProductoDispensado(
            codigo_producto=producto.codigo_producto,
            fecha_dispensacion=producto.fecha_dispensacion,
            cantidad_venta=producto.cantidad,
            tipo_unidad_dispensacion=producto.tipo_unidad_dispensacion,
            monto_unitario=producto.monto_unitario,
            monto_no_cubierto=_CERO,
            exento_igv=_SIN_EXONERACION,
        )
        try:
            monto_presentado = validar_dispensacion(datos, atencion.fecha_prestacion)
        except ErrorProductoInvalido as error:
            raise _invalida(
                "PRODUCTO_INVALIDO", f"Producto {producto.codigo_producto}: {error}"
            ) from error
        catalogo = await self._repositorio.producto_vigente(producto.codigo_producto)
        if catalogo is None:
            raise _invalida(
                "PRODUCTO_FUERA_DE_CATALOGO",
                f"El producto {producto.codigo_producto} no esta en el catalogo GTIN vigente.",
            )
        return ProductoImportado(catalogo, datos, monto_presentado)

    async def _registrar_eventos(
        self, cuenta_id: int, atencion: AtencionHospitalaria, contexto: tuple[str, str, str, int]
    ) -> None:
        via, actor, estado_inicial, iafas_id = contexto
        # El primer evento confirma la transaccion con la cuenta completa.
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="CUENTA_REGISTRADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=estado_inicial,
                datos={"iafas_id": iafas_id},
            )
        )
        await self._registro_eventos.registrar(
            Evento(
                cuenta_medica_id=cuenta_id,
                tipo_evento="ATENCION_IMPORTADA",
                actor=actor,
                estado_previo=None,
                estado_nuevo=None,
                datos={
                    "atencion_id": atencion.atencion_id,
                    "via": via,
                    "procedimientos": len(atencion.procedimientos),
                    "productos": len(atencion.farmacia),
                },
            )
        )


class ImportarAtencionDelSistema:
    """Via consulta: trae la atencion del sistema hospitalario y la importa."""

    def __init__(self, fuente: FuenteAtenciones, importar: ImportarAtencion) -> None:
        self._fuente = fuente
        self._importar = importar

    async def ejecutar(self, atencion_id: str, actor: str) -> int:
        atencion = await self._fuente.obtener(atencion_id)
        if atencion is None:
            raise ErrorAtencionNoEncontrada(atencion_id)
        return await self._importar.ejecutar(atencion, VIA_CONSULTA, actor)


class ListarAtencionesHospitalarias:
    """Las atenciones del sistema hospitalario que aun no se importaron."""

    def __init__(
        self, fuente: FuenteAtenciones, repositorio: RepositorioImportacionAtencion
    ) -> None:
        self._fuente = fuente
        self._repositorio = repositorio

    async def ejecutar(self, documento: str | None) -> list[ResumenAtencionHospitalaria]:
        atenciones = await self._fuente.listar(documento.strip() if documento else None)
        importadas = await self._repositorio.atenciones_importadas(
            [a.atencion_id for a in atenciones]
        )
        return [a for a in atenciones if a.atencion_id not in importadas]
