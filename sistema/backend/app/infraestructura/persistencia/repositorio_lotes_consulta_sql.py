"""Adaptador de RepositorioLotesConsulta (Fase 18, Seccion 11)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.dominio.integracion.casos_uso import TIPO_EVENTO_MONITOREO_EXCEDIDO
from app.dominio.integracion.hallazgos import Hallazgo
from app.dominio.integracion.puertos_consulta import (
    CuentaDelLote,
    DetalleLote,
    InformePrevalidacionLote,
    ObservacionOficial,
    RepositorioLotesConsulta,
    ResultadoValidacionOficial,
    ResumenAcuse,
    ResumenLote,
)
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AcuseTransmisionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    EventoModelo,
    IafasModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.modelos_plataformas import (
    ObservacionValidadorModelo,
    ValidacionOficialModelo,
)
from app.infraestructura.persistencia.modelos_prevalidacion import (
    HallazgoPrevalidacionModelo,
    InformePrevalidacionModelo,
)


@dataclass(frozen=True, slots=True)
class _AgregadoLote:
    cantidad_documentos: int = 0
    monto_total: Decimal = Decimal("0.00")


class RepositorioLotesConsultaSql(RepositorioLotesConsulta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def listar(
        self,
        periodo: str | None,
        estado: str | None = None,
        iafas_id: int | None = None,
    ) -> list[ResumenLote]:
        consulta = (
            sa.select(LoteFacturacionModelo)
            .join(IafasModelo)
            .options(contains_eager(LoteFacturacionModelo.iafas))
            .order_by(LoteFacturacionModelo.generado_en.desc())
        )
        if periodo is not None:
            consulta = consulta.where(LoteFacturacionModelo.periodo == periodo)
        if estado is not None:
            consulta = consulta.where(LoteFacturacionModelo.estado == estado)
        if iafas_id is not None:
            consulta = consulta.where(LoteFacturacionModelo.iafas_id == iafas_id)
        resultado = await self._sesion.execute(consulta)
        lotes = resultado.scalars().unique().all()
        agregados = await self._calcular_agregados([lote.id for lote in lotes])
        excedidos = await self._lotes_excedidos([lote.id for lote in lotes])
        return [
            ResumenLote(
                id=lote.id,
                numero=lote.numero,
                periodo=lote.periodo,
                iafas_codigo=lote.iafas.codigo,
                estado=lote.estado,
                generado_en=lote.generado_en,
                cantidad_documentos=agregados.get(lote.id, _AgregadoLote()).cantidad_documentos,
                monto_total=agregados.get(lote.id, _AgregadoLote()).monto_total,
                monitoreo_excedido=lote.id in excedidos,
            )
            for lote in lotes
        ]

    async def _lotes_excedidos(self, lote_ids: list[int]) -> set[int]:
        """CU-05: lotes aun REMITIDO_IAFAS cuyo monitoreo agoto la ventana."""
        if not lote_ids:
            return set()
        filas = await self._sesion.execute(
            sa.select(EventoModelo.agregado_id)
            .join(LoteFacturacionModelo, LoteFacturacionModelo.id == EventoModelo.agregado_id)
            .where(
                EventoModelo.tipo_agregado == "LOTE",
                EventoModelo.agregado_id.in_(lote_ids),
                EventoModelo.tipo_evento == TIPO_EVENTO_MONITOREO_EXCEDIDO,
                LoteFacturacionModelo.estado == "REMITIDO_IAFAS",
            )
        )
        return {int(lote_id) for (lote_id,) in filas.all()}

    async def _contar_documentos_por_lote(self, lote_ids: list[int]) -> dict[int, int]:
        resultado = await self._sesion.execute(
            sa.select(LoteDocumentoModelo.lote_id, sa.func.count())
            .where(LoteDocumentoModelo.lote_id.in_(lote_ids))
            .group_by(LoteDocumentoModelo.lote_id)
        )
        return {fila[0]: fila[1] for fila in resultado.all()}

    async def _sumar_procedimientos_por_lote(self, lote_ids: list[int]) -> dict[int, Decimal]:
        resultado = await self._sesion.execute(
            sa.select(
                LoteDocumentoModelo.lote_id,
                sa.func.sum(
                    ProcedimientoFacturadoModelo.cantidad
                    * ProcedimientoFacturadoModelo.monto_unitario
                ),
            )
            .select_from(LoteDocumentoModelo)
            .join(
                DocumentoFacturadorModelo,
                DocumentoFacturadorModelo.id == LoteDocumentoModelo.documento_id,
            )
            .join(
                ProcedimientoFacturadoModelo,
                ProcedimientoFacturadoModelo.cuenta_id == DocumentoFacturadorModelo.cuenta_id,
            )
            .where(LoteDocumentoModelo.lote_id.in_(lote_ids))
            .group_by(LoteDocumentoModelo.lote_id)
        )
        return {fila[0]: fila[1] for fila in resultado.all()}

    async def _sumar_productos_por_lote(self, lote_ids: list[int]) -> dict[int, Decimal]:
        resultado = await self._sesion.execute(
            sa.select(
                LoteDocumentoModelo.lote_id,
                sa.func.sum(ProductoFacturadoModelo.monto_presentado),
            )
            .select_from(LoteDocumentoModelo)
            .join(
                DocumentoFacturadorModelo,
                DocumentoFacturadorModelo.id == LoteDocumentoModelo.documento_id,
            )
            .join(
                ProductoFacturadoModelo,
                ProductoFacturadoModelo.cuenta_medica_id == DocumentoFacturadorModelo.cuenta_id,
            )
            .where(LoteDocumentoModelo.lote_id.in_(lote_ids))
            .group_by(LoteDocumentoModelo.lote_id)
        )
        return {fila[0]: fila[1] for fila in resultado.all()}

    async def _calcular_agregados(self, lote_ids: list[int]) -> dict[int, _AgregadoLote]:
        """Una consulta de agregacion por tabla de hecho (procedimientos,
        productos), no un unico join de las tres -- unir lote_documento
        con procedimiento_facturado Y producto_facturado a la vez
        multiplicaria filas (producto cartesiano parcial) y la suma
        saldria mal si una cuenta tiene mas de uno de cada."""
        if not lote_ids:
            return {}

        cantidades = await self._contar_documentos_por_lote(lote_ids)
        montos_procedimientos = await self._sumar_procedimientos_por_lote(lote_ids)
        montos_productos = await self._sumar_productos_por_lote(lote_ids)

        return {
            lote_id: _AgregadoLote(
                cantidad_documentos=cantidades.get(lote_id, 0),
                monto_total=(montos_procedimientos.get(lote_id) or Decimal("0.00"))
                + (montos_productos.get(lote_id) or Decimal("0.00")),
            )
            for lote_id in lote_ids
        }

    async def obtener(self, lote_id: int) -> DetalleLote | None:
        lote = await self._sesion.get(LoteFacturacionModelo, lote_id)
        if lote is None:
            return None
        cantidad = await self._sesion.scalar(
            sa.select(sa.func.count())
            .select_from(LoteDocumentoModelo)
            .where(LoteDocumentoModelo.lote_id == lote_id)
        )
        iafas = await self._sesion.get(IafasModelo, lote.iafas_id)
        assert iafas is not None
        return DetalleLote(
            id=lote.id,
            numero=lote.numero,
            periodo=lote.periodo,
            iafas_codigo=iafas.codigo,
            estado=lote.estado,
            generado_en=lote.generado_en,
            cantidad_documentos=cantidad or 0,
            nombre_s01=lote.nombre_s01,
            sha256_s01=lote.sha256_s01,
            s01_obtenido_en=lote.s01_obtenido_en,
            enviado_susalud_en=lote.enviado_susalud_en,
            version_esquema_tedef=lote.version_esquema_tedef,
            version_mapeo=lote.version_mapeo,
            monitoreo_excedido=lote.id in await self._lotes_excedidos([lote.id]),
        )

    async def obtener_prevalidacion(self, lote_id: int) -> InformePrevalidacionLote | None:
        resultado = await self._sesion.execute(
            sa.select(InformePrevalidacionModelo).where(
                InformePrevalidacionModelo.lote_id == lote_id
            )
        )
        informe = resultado.scalar_one_or_none()
        if informe is None:
            return None
        hallazgos_resultado = await self._sesion.execute(
            sa.select(HallazgoPrevalidacionModelo).where(
                HallazgoPrevalidacionModelo.informe_id == informe.id
            )
        )
        return InformePrevalidacionLote(
            conforme=informe.conforme,
            generado_en=informe.generado_en,
            hallazgos=tuple(
                Hallazgo(
                    severidad=h.severidad,  # type: ignore[arg-type]
                    tabla=h.tabla,
                    campo_numero=h.campo_numero,
                    campo_nombre=h.campo_nombre,
                    criterio_id=h.criterio_id,
                    criterio_texto=h.criterio_texto,
                    valor=h.valor,
                    mensaje=h.mensaje,
                )
                for h in hallazgos_resultado.scalars().all()
            ),
        )

    async def obtener_validacion_oficial(self, lote_id: int) -> list[ResultadoValidacionOficial]:
        resultado = await self._sesion.execute(
            sa.select(ValidacionOficialModelo)
            .where(ValidacionOficialModelo.lote_id == lote_id)
            .order_by(ValidacionOficialModelo.registrado_en)
        )
        validaciones = resultado.scalars().all()
        salida = []
        for validacion in validaciones:
            observaciones_resultado = await self._sesion.execute(
                sa.select(ObservacionValidadorModelo).where(
                    ObservacionValidadorModelo.validacion_oficial_id == validacion.id
                )
            )
            salida.append(
                ResultadoValidacionOficial(
                    etapa=validacion.etapa,
                    resultado=validacion.resultado,
                    estado_informado_validador=validacion.estado_informado_validador,
                    registrado_en=validacion.registrado_en,
                    observaciones=tuple(
                        ObservacionOficial(
                            tabla=o.tabla,
                            numero_linea=o.numero_linea,
                            campo_clave=o.campo_clave,
                            campo=o.campo,
                            valor_observado=o.valor_observado,
                            codigo_error=o.codigo_error,
                            descripcion=o.descripcion,
                        )
                        for o in observaciones_resultado.scalars().all()
                    ),
                )
            )
        return salida

    async def obtener_acuses(self, lote_id: int) -> list[ResumenAcuse]:
        resultado = await self._sesion.execute(
            sa.select(AcuseTransmisionModelo)
            .where(AcuseTransmisionModelo.lote_id == lote_id)
            .order_by(AcuseTransmisionModelo.intentado_en.desc())
        )
        return [
            ResumenAcuse(
                id=a.id,
                resultado_transferencia=a.resultado_transferencia,
                motivo_transferencia=a.motivo_transferencia,
                intentado_en=a.intentado_en,
                respuesta_receptor=a.respuesta_receptor,
                motivo_receptor=a.motivo_receptor,
                respondido_en=a.respondido_en,
            )
            for a in resultado.scalars().all()
        ]

    async def obtener_cuentas(self, lote_id: int) -> list[CuentaDelLote]:
        resultado = await self._sesion.execute(
            sa.select(CuentaMedicaModelo, AseguradoModelo)
            .select_from(LoteDocumentoModelo)
            .join(
                DocumentoFacturadorModelo,
                DocumentoFacturadorModelo.id == LoteDocumentoModelo.documento_id,
            )
            .join(
                CuentaMedicaModelo,
                CuentaMedicaModelo.id == DocumentoFacturadorModelo.cuenta_id,
            )
            .join(AseguradoModelo, AseguradoModelo.id == CuentaMedicaModelo.asegurado_id)
            .where(LoteDocumentoModelo.lote_id == lote_id)
            .order_by(CuentaMedicaModelo.identificacion_interna)
        )
        filas = resultado.all()
        montos = await self._montos_por_cuenta([cuenta.id for cuenta, _ in filas])
        return [
            CuentaDelLote(
                id=cuenta.id,
                identificacion_interna=cuenta.identificacion_interna,
                nombres_asegurado=asegurado.nombres,
                apellidos_asegurado=asegurado.apellidos,
                monto=montos.get(cuenta.id, Decimal("0.00")),
                estado=cuenta.estado,
                fecha_prestacion=cuenta.fecha_prestacion,
            )
            for cuenta, asegurado in filas
        ]

    async def _montos_por_cuenta(self, cuenta_ids: list[int]) -> dict[int, Decimal]:
        """Misma logica que `_sumar_procedimientos_por_lote`/
        `_sumar_productos_por_lote` (dos consultas de agregacion
        separadas, no un unico join de las tres tablas -- ver el
        docstring de `_calcular_agregados`), agrupada por cuenta en vez
        de por lote."""
        if not cuenta_ids:
            return {}

        procedimientos = await self._sesion.execute(
            sa.select(
                ProcedimientoFacturadoModelo.cuenta_id,
                sa.func.sum(
                    ProcedimientoFacturadoModelo.cantidad
                    * ProcedimientoFacturadoModelo.monto_unitario
                ),
            )
            .where(ProcedimientoFacturadoModelo.cuenta_id.in_(cuenta_ids))
            .group_by(ProcedimientoFacturadoModelo.cuenta_id)
        )
        productos = await self._sesion.execute(
            sa.select(
                ProductoFacturadoModelo.cuenta_medica_id,
                sa.func.sum(ProductoFacturadoModelo.monto_presentado),
            )
            .where(ProductoFacturadoModelo.cuenta_medica_id.in_(cuenta_ids))
            .group_by(ProductoFacturadoModelo.cuenta_medica_id)
        )
        montos_procedimientos = {fila[0]: fila[1] for fila in procedimientos.all()}
        montos_productos = {fila[0]: fila[1] for fila in productos.all()}
        return {
            cuenta_id: (montos_procedimientos.get(cuenta_id) or Decimal("0.00"))
            + (montos_productos.get(cuenta_id) or Decimal("0.00"))
            for cuenta_id in cuenta_ids
        }

    async def obtener_ruta_s01(self, lote_id: int) -> str | None:
        lote = await self._sesion.get(LoteFacturacionModelo, lote_id)
        return lote.ruta_s01 if lote else None
