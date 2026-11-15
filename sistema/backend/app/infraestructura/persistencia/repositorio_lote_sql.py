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
from app.infraestructura.persistencia.modelos_documentos_pago import NotaDocumentoModelo
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.modelos_prevalidacion import (
    HallazgoPrevalidacionModelo,
    InformePrevalidacionModelo,
)
from app.infraestructura.tedef.carga_esquema import version_esquema
from app.infraestructura.tedef.carga_mapeo import version_mapeo

_DOS_DECIMALES = Decimal("0.01")


class RepositorioLoteFacturacionSql(RepositorioLoteFacturacion):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

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
    ) -> DocumentoLote:
        acreditacion = cuenta.acreditacion
        assert acreditacion is not None
        assert cuenta.documento is not None

        procedimientos_ordenados = sorted(cuenta.procedimientos, key=lambda p: p.id)
        procedimientos = tuple(
            self._a_procedimiento_lote(
                indice + 1, procedimiento, acreditacion, es_el_primero=indice == 0
            )
            for indice, procedimiento in enumerate(procedimientos_ordenados)
        )
        prestacion = PrestacionLote(
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
            productos=tuple(self._a_producto_lote(p) for p in productos),
        )
        return DocumentoLote(
            documento_id=cuenta.documento.id,
            cuenta_medica_id=cuenta.id,
            tipo_documento_pago=cuenta.documento.tipo_documento_pago,
            serie=cuenta.documento.serie,
            numero=cuenta.documento.numero,
            fecha_emision=cuenta.documento.fecha_emision,
            fecha_primer_envio=cuenta.documento.fecha_primer_envio,
            prestacion=prestacion,
            nota=nota,
        )

    @staticmethod
    def _a_procedimiento_lote(
        correlativo: int, procedimiento: object, acreditacion: object, es_el_primero: bool
    ) -> ProcedimientoLote:
        # Mapeo T3 campos 17 y 18 (configuracion/mapeo/mapeo_tedef.yaml):
        # el coaseguro se calcula por procedimiento; el copago fijo, al no
        # tener el anexo una regla de reparto, se aplica entero al primer
        # procedimiento de la prestacion. Marcado para confirmacion del
        # asesor junto con esas dos entradas del diccionario de mapeo.
        cantidad = procedimiento.cantidad  # type: ignore[attr-defined]
        monto_unitario = procedimiento.monto_unitario  # type: ignore[attr-defined]
        monto_presentado = (Decimal(cantidad) * monto_unitario).quantize(_DOS_DECIMALES)

        copago_variable = Decimal("0.00")
        if acreditacion.tipo_copago == "coaseguro" and acreditacion.porcentaje_coaseguro:  # type: ignore[attr-defined]
            copago_variable = (
                monto_presentado * Decimal(acreditacion.porcentaje_coaseguro) / Decimal(100)  # type: ignore[attr-defined]
            ).quantize(_DOS_DECIMALES)

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
        )

    @staticmethod
    def _a_producto_lote(producto: ProductoFacturadoModelo) -> ProductoLote:
        return ProductoLote(
            correlativo=producto.correlativo,
            tipo_producto=producto.tipo_producto,
            catalogo=producto.catalogo,
            codigo_producto=producto.codigo_producto,
            fecha_dispensacion=producto.fecha_dispensacion,
            cantidad_venta=producto.cantidad_venta,
            tipo_unidad_dispensacion=producto.tipo_unidad_dispensacion,
            monto_unitario=producto.monto_unitario_sin_impuesto,
            copago=producto.copago,
            monto_no_cubierto=producto.monto_no_cubierto,
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
