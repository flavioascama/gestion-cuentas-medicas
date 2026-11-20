"""Adaptador de RepositorioComprobantePago (adenda de ingesta y
completitud, emision del comprobante de pago via el simulador PSE)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acreditacion.valores import es_acreditable
from app.dominio.pse.puertos import (
    ClienteComprobante,
    ComprobanteEmitido,
    DatosFacturacion,
    ErrorComprobanteYaExiste,
    ErrorCuentaNoEncontrada,
    RepositorioComprobantePago,
    RequisitosComprobante,
)
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.montos_comprobante_sql import (
    a_montos_comprobante,
    montos_facturados_de_cuenta,
)
from app.infraestructura.persistencia.repositorio_por_codificar_sql import (
    contar_por_codificar,
    tiene_carta_garantia,
)
from app.infraestructura.persistencia.revision_contingencia_sql import (
    acreditacion_vigente_no_conforme,
)


class RepositorioComprobantePagoSql(RepositorioComprobantePago):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_ipress_propia(self) -> tuple[str, str]:
        ipress = (await self._sesion.execute(sa.select(IpressModelo).limit(1))).scalar_one()
        return ipress.ruc, ipress.codigo_ipress

    async def requisitos_para_facturar(self, cuenta_id: int) -> RequisitosComprobante | None:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        if cuenta is None:
            return None
        condicion = await self._sesion.scalar(
            sa.select(AcreditacionModelo.condicion_cobertura)
            .where(AcreditacionModelo.cuenta_id == cuenta_id)
            .order_by(AcreditacionModelo.id.desc())  # la vigente
            .limit(1)
        )
        procedimientos = await self._sesion.scalar(
            sa.select(sa.func.count())
            .select_from(ProcedimientoFacturadoModelo)
            .where(ProcedimientoFacturadoModelo.cuenta_id == cuenta_id)
        )
        return RequisitosComprobante(
            acreditada=condicion is not None,
            con_diagnostico=bool(cuenta.diagnostico_principal_cie10),
            procedimientos=int(procedimientos or 0),
            acreditable=condicion is None or es_acreditable(condicion),
            por_codificar=await contar_por_codificar(self._sesion, cuenta_id),
            falta_carta_garantia=cuenta.tipo_atencion == "HOSPITALIZACION"
            and not await tiene_carta_garantia(self._sesion, cuenta_id),
            cobertura_no_conforme=await acreditacion_vigente_no_conforme(self._sesion, cuenta_id),
        )

    async def datos_para_facturar(
        self, cuenta_id: int, tipo_comprobante: str
    ) -> DatosFacturacion | None:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        if cuenta is None:
            return None
        iafas = await self._sesion.get(IafasModelo, cuenta.iafas_id)
        montos = await montos_facturados_de_cuenta(self._sesion, cuenta_id, tipo_comprobante)
        if iafas is None or montos is None:
            return None
        return DatosFacturacion(
            cliente=ClienteComprobante(codigo_iafas=iafas.codigo, razon_social=iafas.razon_social),
            montos=a_montos_comprobante(montos),
        )

    async def guardar_comprobante(self, cuenta_id: int, emitido: ComprobanteEmitido) -> int:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        if cuenta is None:
            raise ErrorCuentaNoEncontrada(cuenta_id)

        # Chequeo explicito antes del INSERT, no un `except IntegrityError`
        # generico: `documento_facturador` tiene DOS restricciones unique
        # distintas (cuenta_id, y el compuesto ipress_id+tipo+serie+numero,
        # Seccion 6.2) -- capturar cualquier IntegrityError y asumir
        # siempre "esta cuenta ya tiene comprobante" reportaria mal un
        # choque de numeracion contra OTRA cuenta como si fuera este caso.
        ya_existe = await self._sesion.scalar(
            sa.select(sa.literal(True))
            .select_from(DocumentoFacturadorModelo)
            .where(DocumentoFacturadorModelo.cuenta_id == cuenta_id)
            .limit(1)
        )
        if ya_existe:
            raise ErrorComprobanteYaExiste(cuenta_id)

        # Se guarda exactamente lo que se envio al PSE.
        comprobante = emitido.comprobante
        documento = DocumentoFacturadorModelo(
            cuenta_id=cuenta_id,
            ipress_id=cuenta.ipress_id,
            tipo_documento_pago=comprobante.tipo_documento_pago,
            serie=comprobante.serie,
            numero=comprobante.numero,
            fecha_emision=comprobante.fecha_emision,
            valor_venta=emitido.montos.valor_venta,
            igv=emitido.montos.igv,
            total=emitido.montos.total,
        )
        self._sesion.add(documento)
        await self._sesion.flush()
        await self._sesion.commit()
        return documento.id
