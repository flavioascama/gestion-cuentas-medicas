"""Adaptador de RepositorioLoteFacturacion (Seccion 7.6)."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dominio.integracion.lote import (
    DocumentoLote,
    NotaLote,
    PrestacionLote,
    ProcedimientoLote,
    ProductoLote,
)
from app.dominio.integracion.puertos import (
    DatosLoteConforme,
    ErrorRepositorioLote,
    RepositorioLoteFacturacion,
)
from app.dominio.pse.puertos import MontosComprobante
from app.infraestructura.persistencia.areas_procedimiento_sql import areas_de_procedimientos
from app.infraestructura.persistencia.modelos_carta_garantia import CartaGarantiaModelo
from app.infraestructura.persistencia.modelos_documentos_pago import NotaDocumentoModelo
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.modelos_prevalidacion import (
    HallazgoPrevalidacionModelo,
    InformePrevalidacionModelo,
)
from app.infraestructura.persistencia.vigencia_lote_sql import cuentas_en_lotes_vigentes
from app.infraestructura.tedef.carga_esquema import version_esquema
from app.infraestructura.tedef.carga_mapeo import version_mapeo

_DOS_DECIMALES = Decimal("0.01")
_CERO = Decimal("0.00")


def _coaseguro(monto: Decimal, acreditacion: object) -> Decimal:
    """Lo que asume el asegurado por coaseguro sobre `monto`; 0.00 si su
    acreditacion no fija un porcentaje."""
    porcentaje = acreditacion.porcentaje_coaseguro  # type: ignore[attr-defined]
    if acreditacion.tipo_copago != "coaseguro" or not porcentaje:  # type: ignore[attr-defined]
        return _CERO
    return (monto * Decimal(porcentaje) / Decimal(100)).quantize(_DOS_DECIMALES)


def montos_guardados(documento: DocumentoFacturadorModelo) -> MontosComprobante | None:
    """Lo que guardo el comprobante al emitirse; None si es anterior al
    2026-11-18 y no guardo montos."""
    if documento.valor_venta is None or documento.igv is None or documento.total is None:
        return None
    return MontosComprobante(
        valor_venta=documento.valor_venta, igv=documento.igv, total=documento.total
    )


class RepositorioLoteFacturacionSql(RepositorioLoteFacturacion):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion
        # Area de cada procedimiento del lote en armado (Codigo Rubro, T3-23).
        self._areas: dict[int, str] = {}

    async def obtener_ipress_propia(self) -> tuple[str, str]:
        resultado = await self._sesion.execute(sa.select(IpressModelo).limit(2))
        filas = resultado.scalars().all()
        if len(filas) != 1:
            raise ErrorRepositorioLote(
                f"Se esperaba exactamente 1 fila en ipress (la clinica propia); hay {len(filas)}."
            )
        return filas[0].ruc, filas[0].codigo_ipress

    async def obtener_codigo_iafas(self, iafas_id: int) -> str:
        iafas = await self._sesion.get(IafasModelo, iafas_id)
        if iafas is None:
            raise ErrorRepositorioLote(f"No existe la IAFAS {iafas_id}.")
        return iafas.codigo

    async def obtener_documentos_facturados(
        self, iafas_id: int, cuenta_ids: list[int]
    ) -> list[DocumentoLote]:
        # Una cuenta que ya esta en un lote en curso y vigente no entra en otro.
        ocupadas = await cuentas_en_lotes_vigentes(self._sesion)
        libres = [cuenta_id for cuenta_id in cuenta_ids if cuenta_id not in ocupadas]
        if cuenta_ids and not libres:
            raise ErrorRepositorioLote("Las cuentas elegidas ya están en un lote en curso.")
        cuenta_ids = libres
        consulta = (
            sa.select(CuentaMedicaModelo)
            .where(
                CuentaMedicaModelo.iafas_id == iafas_id,
                CuentaMedicaModelo.estado == "FACTURADA",
                CuentaMedicaModelo.id.in_(cuenta_ids),
            )
            .options(
                selectinload(CuentaMedicaModelo.documento),
                selectinload(CuentaMedicaModelo.acreditacion),
                selectinload(CuentaMedicaModelo.procedimientos),
                selectinload(CuentaMedicaModelo.asegurado),
            )
            .order_by(CuentaMedicaModelo.id)
        )
        cuentas = (await self._sesion.execute(consulta)).scalars().all()
        productos_por_cuenta = await self._obtener_productos_por_cuenta([c.id for c in cuentas])
        notas = await self._obtener_notas([c.documento.id for c in cuentas if c.documento])
        cartas = await self._obtener_cartas([c.id for c in cuentas])
        self._areas = await areas_de_procedimientos(
            self._sesion, [p.id for c in cuentas for p in c.procedimientos]
        )

        documentos = []
        for cuenta in cuentas:
            if cuenta.documento is None or cuenta.acreditacion is None:
                raise ErrorRepositorioLote(
                    f"La cuenta {cuenta.id} no tiene documento_facturador o acreditacion; "
                    "no puede incluirse en un lote."
                )
            documentos.append(
                self._a_documento_lote(
                    cuenta,
                    productos_por_cuenta.get(cuenta.id, ()),
                    notas.get(cuenta.documento.id),
                    cartas.get(cuenta.id),
                )
            )
        return documentos

    async def _obtener_productos_por_cuenta(
        self, cuenta_ids: list[int]
    ) -> dict[int, tuple[ProductoFacturadoModelo, ...]]:
        """T4 (Seccion 8.1, Fase 17): sin relationship() de vuelta desde
        CuentaMedicaModelo (mismo patron que procedimiento_facturado con
        cpms_version, Fase 4: la llave foranea basta, sin bidireccional).
        Consulta aparte en vez de selectinload."""

        if not cuenta_ids:
            return {}
        resultado = await self._sesion.execute(
            sa.select(ProductoFacturadoModelo)
            .where(ProductoFacturadoModelo.cuenta_medica_id.in_(cuenta_ids))
            .order_by(ProductoFacturadoModelo.cuenta_medica_id, ProductoFacturadoModelo.correlativo)
        )
        agrupados: dict[int, list[ProductoFacturadoModelo]] = {}
        for producto in resultado.scalars().all():
            agrupados.setdefault(producto.cuenta_medica_id, []).append(producto)
        return {cuenta_id: tuple(productos) for cuenta_id, productos in agrupados.items()}

    async def _obtener_cartas(self, cuenta_ids: list[int]) -> dict[int, str]:
        """Numero de la carta de garantia de cada cuenta que la tiene (una
        sola consulta para todo el lote)."""

        if not cuenta_ids:
            return {}
        filas = await self._sesion.execute(
            sa.select(CartaGarantiaModelo.cuenta_medica_id, CartaGarantiaModelo.numero).where(
                CartaGarantiaModelo.cuenta_medica_id.in_(cuenta_ids)
            )
        )
        return {cuenta_id: numero for cuenta_id, numero in filas.all()}

    async def _obtener_notas(self, documento_ids: list[int]) -> dict[int, NotaLote]:
        """T1 campos 25 a 29 (RI-11): la nota de cada comprobante, si tiene."""

        if not documento_ids:
            return {}
        filas = await self._sesion.execute(
            sa.select(NotaDocumentoModelo).where(
                NotaDocumentoModelo.documento_facturador_id.in_(documento_ids)
            )
        )
        return {
            nota.documento_facturador_id: NotaLote(
                tipo=nota.tipo,
                serie=nota.serie,
                numero=nota.numero,
                monto=nota.monto,
                fecha=nota.fecha,
                motivo=nota.motivo,
            )
            for nota in filas.scalars().all()
        }

    def _a_documento_lote(
        self,
        cuenta: CuentaMedicaModelo,
        productos: tuple[ProductoFacturadoModelo, ...],
        nota: NotaLote | None = None,
        numero_carta_garantia: str | None = None,
    ) -> DocumentoLote:
        assert cuenta.documento is not None
        return DocumentoLote(
            documento_id=cuenta.documento.id,
            cuenta_medica_id=cuenta.id,
            tipo_documento_pago=cuenta.documento.tipo_documento_pago,
            serie=cuenta.documento.serie,
            numero=cuenta.documento.numero,
            fecha_emision=cuenta.documento.fecha_emision,
            fecha_primer_envio=cuenta.documento.fecha_primer_envio,
            prestacion=self._a_prestacion_lote(cuenta, productos, numero_carta_garantia),
            nota=nota,
            montos_comprobante=montos_guardados(cuenta.documento),
        )

    def _a_prestacion_lote(
        self,
        cuenta: CuentaMedicaModelo,
        productos: tuple[ProductoFacturadoModelo, ...],
        numero_carta_garantia: str | None,
    ) -> PrestacionLote:
        acreditacion = cuenta.acreditacion
        assert acreditacion is not None
        procedimientos_ordenados = sorted(cuenta.procedimientos, key=lambda p: p.id)
        procedimientos = tuple(
            self._a_procedimiento_lote(
                indice + 1,
                procedimiento,
                acreditacion,
                es_el_primero=indice == 0,
                area=self._areas.get(procedimiento.id, "PROCEDIMIENTO"),
            )
            for indice, procedimiento in enumerate(procedimientos_ordenados)
        )
        return PrestacionLote(
            codigo_prestacion_interno=cuenta.identificacion_interna,
            numero_historia_clinica=cuenta.numero_historia_clinica,
            tipo_documento_paciente=cuenta.asegurado.tipo_documento,
            numero_documento_paciente=cuenta.asegurado.numero_documento,
            codigo_asegurado=acreditacion.codigo_asegurado,
            tipo_afiliacion=acreditacion.tipo_afiliacion,
            codigo_autorizacion=acreditacion.codigo_autorizacion,
            tipo_documento_autorizacion=acreditacion.tipo_documento_autorizacion,
            fecha_prestacion=cuenta.fecha_prestacion,
            hora_prestacion=cuenta.hora_prestacion,
            diagnostico_principal_cie10=cuenta.diagnostico_principal_cie10,
            procedimientos=procedimientos,
            productos=tuple(self._a_producto_lote(p, acreditacion) for p in productos),
            numero_carta_garantia=numero_carta_garantia,
            tipo_atencion=cuenta.tipo_atencion,
            colegiatura_medico=cuenta.colegiatura_medico,
            diagnosticos_secundarios_cie10=tuple(
                filter(None, (cuenta.diagnosticos_secundarios_cie10 or "").split(","))
            ),
            fecha_ingreso_hospitalario=cuenta.fecha_ingreso_hospitalario,
            fecha_alta_hospitalaria=cuenta.fecha_alta_hospitalaria,
        )

    @staticmethod
    def _a_procedimiento_lote(
        correlativo: int,
        procedimiento: object,
        acreditacion: object,
        es_el_primero: bool,
        area: str = "PROCEDIMIENTO",
    ) -> ProcedimientoLote:
        # Mapeo T3 campos 17 y 18 (configuracion/mapeo/mapeo_tedef.yaml):
        # el coaseguro se calcula por procedimiento; el copago fijo, al no
        # tener el anexo una regla de reparto, se aplica entero al primer
        # procedimiento de la prestacion. Marcado para confirmacion del
        # asesor junto con esas dos entradas del diccionario de mapeo.
        cantidad = procedimiento.cantidad  # type: ignore[attr-defined]
        monto_unitario = procedimiento.monto_unitario  # type: ignore[attr-defined]
        monto_presentado = (Decimal(cantidad) * monto_unitario).quantize(_DOS_DECIMALES)

        copago_variable = _coaseguro(monto_presentado, acreditacion)

        copago_fijo = Decimal("0.00")
        if (
            es_el_primero
            and acreditacion.tipo_copago == "fijo"  # type: ignore[attr-defined]
            and acreditacion.monto_copago_fijo is not None  # type: ignore[attr-defined]
        ):
            copago_fijo = acreditacion.monto_copago_fijo  # type: ignore[attr-defined]

        return ProcedimientoLote(
            correlativo=correlativo,
            codigo_cpms=procedimiento.codigo_asignado,  # type: ignore[attr-defined]
            descripcion=procedimiento.descripcion_registrada,  # type: ignore[attr-defined]
            fecha=procedimiento.fecha,  # type: ignore[attr-defined]
            cantidad=cantidad,
            monto_unitario=monto_unitario,
            copago_variable=copago_variable,
            copago_fijo=copago_fijo,
            area=area,
        )

    @staticmethod
    def _a_producto_lote(producto: ProductoFacturadoModelo, acreditacion: object) -> ProductoLote:
        # Misma regla que un procedimiento (T3 campos 17 y 20): el copago
        # (T4 campo 14) es el coaseguro de la acreditacion sobre lo presentado
        # menos la exclusion registrada del producto, y lo no cubierto (T4
        # campo 16) es esa exclusion mas el copago. El copago fijo ya va
        # entero en el primer procedimiento.
        exclusion = producto.monto_no_cubierto
        copago = _coaseguro(producto.monto_presentado - exclusion, acreditacion)
        return ProductoLote(
            correlativo=producto.correlativo,
            tipo_producto=producto.tipo_producto,
            catalogo=producto.catalogo,
            codigo_producto=producto.codigo_producto,
            fecha_dispensacion=producto.fecha_dispensacion,
            cantidad_venta=producto.cantidad_venta,
            tipo_unidad_dispensacion=producto.tipo_unidad_dispensacion,
            monto_unitario=producto.monto_unitario_sin_impuesto,
            copago=copago,
            monto_no_cubierto=exclusion + copago,
            diagnostico_asociado_cie10=producto.diagnostico_asociado_cie10,
            exento_igv=producto.exento_igv,
            guia_farmacia=producto.guia_farmacia,
            cantidad_prescrita=producto.cantidad_prescrita,
        )

    async def siguiente_numero_lote(self, iafas_id: int) -> str:
        resultado = await self._sesion.execute(
            sa.select(LoteFacturacionModelo.numero)
            .where(LoteFacturacionModelo.iafas_id == iafas_id)
            .with_for_update()
        )
        numeros = [int(fila[0]) for fila in resultado.all()]
        siguiente = (max(numeros) if numeros else 0) + 1
        return str(siguiente).zfill(7)

    async def guardar_lote_conforme(self, datos: DatosLoteConforme) -> int:
        lote = LoteFacturacionModelo(
            numero=datos.numero,
            iafas_id=datos.iafas_id,
            periodo=datos.periodo,
            generado_en=datos.generado_en,
            estado="GENERADO",
            version_esquema_tedef=version_esquema(),
            version_mapeo=version_mapeo(),
        )
        self._sesion.add(lote)
        await self._sesion.flush()
        self._sesion.add_all(
            LoteDocumentoModelo(lote_id=lote.id, documento_id=documento_id)
            for documento_id in datos.documento_ids
        )
        informe = InformePrevalidacionModelo(
            lote_id=lote.id, conforme=True, generado_en=datos.generado_en
        )
        self._sesion.add(informe)
        await self._sesion.flush()
        self._sesion.add_all(
            HallazgoPrevalidacionModelo(
                informe_id=informe.id,
                severidad=h.severidad,
                tabla=h.tabla,
                campo_numero=h.campo_numero,
                campo_nombre=h.campo_nombre,
                criterio_id=h.criterio_id,
                criterio_texto=h.criterio_texto,
                valor=h.valor,
                mensaje=h.mensaje,
            )
            for h in datos.hallazgos
        )
        await self._sesion.commit()
        return lote.id
