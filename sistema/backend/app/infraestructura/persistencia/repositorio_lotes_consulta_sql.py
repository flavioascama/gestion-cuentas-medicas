"""Adaptador de RepositorioLotesConsulta (Fase 18, Seccion 11)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.dominio.integracion.casos_uso import (
    TIPO_EVENTO_MONITOREO_EXCEDIDO,
    TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS,
)
from app.dominio.integracion.casos_uso_validacion import TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR
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
from app.dominio.integracion.vigencia_lote import ESTADOS_LOTE_EN_CURSO, motivo_desactualizado
from app.infraestructura.cola.repositorio_trabajos_sql import RepositorioTrabajosSql
from app.infraestructura.persistencia.cuentas_por_linea_sql import (
    CuentasPorLinea,
    cuenta_de_linea,
    cuentas_por_linea,
)
from app.infraestructura.persistencia.modelos_integracion import (
    AcuseTransmisionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    EventoModelo,
    IafasModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
    TrabajoModelo,
)
from app.infraestructura.persistencia.modelos_plataformas import (
    ObservacionValidadorModelo,
    ValidacionOficialModelo,
)
from app.infraestructura.persistencia.modelos_prevalidacion import (
    HallazgoPrevalidacionModelo,
    InformePrevalidacionModelo,
)
from app.infraestructura.persistencia.montos_cuenta_sql import facturado_remitido
from app.infraestructura.persistencia.vigencia_lote_sql import (
    vigencia_de_lote,
    vigencias_de_lotes,
)


@dataclass(frozen=True, slots=True)
class _AgregadoLote:
    cantidad_documentos: int = 0
    monto_total: Decimal = Decimal("0.00")


def _a_observacion_oficial(
    fila: ObservacionValidadorModelo, lineas: CuentasPorLinea
) -> ObservacionOficial:
    cuenta = cuenta_de_linea(lineas, fila.tabla, fila.numero_linea)
    return ObservacionOficial(
        tabla=fila.tabla,
        numero_linea=fila.numero_linea,
        campo_clave=fila.campo_clave,
        campo=fila.campo,
        valor_observado=fila.valor_observado,
        codigo_error=fila.codigo_error,
        descripcion=fila.descripcion,
        cuenta_medica_id=cuenta[0] if cuenta else None,
        identificacion_interna=cuenta[1] if cuenta else None,
    )


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
            # Los lotes que ya terminaron (aceptados por la IAFAS y enviados a
            # SUSALUD) van al final: primero los que tienen trabajo (2026-11-18).
            .order_by(
                sa.and_(
                    LoteFacturacionModelo.estado == "ACEPTADO",
                    LoteFacturacionModelo.enviado_susalud_en.is_not(None),
                ).asc(),
                LoteFacturacionModelo.generado_en.desc(),
            )
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
        # Solo un lote en curso puede quedar desactualizado (ver obtener).
        en_curso = [lote.id for lote in lotes if lote.estado in ESTADOS_LOTE_EN_CURSO]
        vigencias = await vigencias_de_lotes(self._sesion, en_curso)
        motivos = {i: motivo_desactualizado(v) for i, v in vigencias.items()}
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
                vigente=motivos.get(lote.id) is None,
                motivo_desactualizado=motivos.get(lote.id),
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

    async def _calcular_agregados(self, lote_ids: list[int]) -> dict[int, _AgregadoLote]:
        """El monto de un lote es lo facturado a la IAFAS por sus cuentas:
        la suma de los totales de sus comprobantes, con IGV (auditoria
        final, hallazgo 4; antes era la suma de lo presentado), tal como
        estaban al generar el lote (segunda auditoria final, hallazgo 1)."""
        if not lote_ids:
            return {}

        resultado = await self._sesion.execute(
            sa.select(
                LoteDocumentoModelo.lote_id,
                LoteDocumentoModelo.documento_id,
                LoteDocumentoModelo.total_facturado,
            ).where(LoteDocumentoModelo.lote_id.in_(lote_ids))
        )
        filas = resultado.all()
        montos = await facturado_remitido(self._sesion, [(d, t) for _, d, t in filas])
        agregados: dict[int, _AgregadoLote] = {}
        for lote_id in lote_ids:
            del_lote = [m for (lote, _, _), m in zip(filas, montos, strict=True) if lote == lote_id]
            agregados[lote_id] = _AgregadoLote(
                cantidad_documentos=len(del_lote),
                monto_total=sum(del_lote, Decimal("0.00")),
            )
        return agregados

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
        motivo = await self._motivo_desactualizado(lote)
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
            proxima_consulta=await self._proxima_consulta(lote),
            validacion_reintentable=lote.estado == "CARGADO_VALIDADOR"
            and not await self._validacion_en_curso(lote.id),
            vigente=motivo is None,
            motivo_desactualizado=motivo,
        )

    async def _motivo_desactualizado(self, lote: LoteFacturacionModelo) -> str | None:
        # Solo un lote en curso puede dejar de ser vigente: despues de la
        # remision sus cuentas ya no estan en FACTURADA.
        if lote.estado not in ESTADOS_LOTE_EN_CURSO:
            return None
        return motivo_desactualizado(await vigencia_de_lote(self._sesion, lote.id))

    async def _proxima_consulta(self, lote: LoteFacturacionModelo) -> datetime | None:
        if lote.estado != "REMITIDO_IAFAS":
            return None
        proxima: datetime | None = await self._sesion.scalar(
            sa.select(sa.func.min(TrabajoModelo.proximo_intento)).where(
                TrabajoModelo.tipo == TIPO_TRABAJO_MONITOREAR_RESPUESTA_IAFAS,
                TrabajoModelo.estado.in_(("PENDIENTE", "EN_PROCESO")),
                TrabajoModelo.carga_util["lote_id"].as_integer() == lote.id,
            )
        )
        return proxima

    async def _validacion_en_curso(self, lote_id: int) -> bool:
        return await RepositorioTrabajosSql(self._sesion).hay_sin_terminar(
            TIPO_TRABAJO_CARGAR_LOTE_VALIDADOR, lote_id
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
        lineas = await cuentas_por_linea(self._sesion, lote_id) if validaciones else {}
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
                        _a_observacion_oficial(o, lineas)
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
            sa.select(
                CuentaMedicaModelo,
                AseguradoModelo,
                LoteDocumentoModelo.documento_id,
                LoteDocumentoModelo.total_facturado,
            )
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
        # Lo facturado a la IAFAS por la cuenta, como en el monto del lote.
        montos = await facturado_remitido(self._sesion, [(d, t) for _, _, d, t in filas])
        return [
            CuentaDelLote(
                id=cuenta.id,
                identificacion_interna=cuenta.identificacion_interna,
                nombres_asegurado=asegurado.nombres,
                apellidos_asegurado=asegurado.apellidos,
                monto=monto,
                estado=cuenta.estado,
                fecha_prestacion=cuenta.fecha_prestacion,
            )
            for (cuenta, asegurado, _, _), monto in zip(filas, montos, strict=True)
        ]

    async def obtener_ruta_s01(self, lote_id: int) -> str | None:
        lote = await self._sesion.get(LoteFacturacionModelo, lote_id)
        return lote.ruta_s01 if lote else None
