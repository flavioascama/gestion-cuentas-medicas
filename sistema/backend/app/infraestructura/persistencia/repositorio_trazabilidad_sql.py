"""Adaptador de RepositorioTrazabilidad (Seccion 6.2; CU-14 a CU-16,
Fase 29).

La verificacion de integridad de la cadena (RT-10/RT-12, control C-10)
y el calculo de los indicadores (RF-15) viven aqui, no en el dominio:
ambos dependen de representacion de almacenamiento (el valor resumen
con clave guardado en cada fila, Tabla 68) o se agregan en Python por
simplicidad y portabilidad entre SQLite y PostgreSQL -- la aritmetica
de fechas sobre columnas de marca temporal no es portable entre los
dos dialectos, y el volumen de datos sinteticos del prototipo no
justifica resolverlo en SQL. El dominio solo ve el resultado ya
resuelto (`IndicadoresCiclo`, `HistorialCuenta`)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.compartido.configuracion import obtener_configuracion
from app.dominio.trazabilidad.puertos import RepositorioTrazabilidad
from app.dominio.trazabilidad.valores import (
    CicloCuenta,
    DistribucionEstado,
    DocumentoExpediente,
    EventoHistorial,
    FiltroIndicadores,
    HistorialCuenta,
    HistorialLote,
    IndicadoresCiclo,
    IndicadoresIafas,
    LotesPeriodoEstado,
    RegistrosContingencia,
    TiempoCicloCuentas,
    TiempoEtapa,
)
from app.infraestructura.persistencia.cadena_eventos import GENESIS, calcular_hash_evento_de_fila
from app.infraestructura.persistencia.modelos_farmacia import ProductoFacturadoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    EventoModelo,
    IafasModelo,
    LoteFacturacionModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.modelos_liquidacion import LiquidacionModelo
from app.infraestructura.persistencia.proyeccion_ciclo import ProyeccionCicloCuentaModelo

_TIPOS_EVENTO_CONTINGENCIA = (
    "CONTINGENCIA_COBERTURA_REGISTRADA",
    "CONTINGENCIA_VALIDACION_REGISTRADA",
    "CONTINGENCIA_REVISADA",
)

# R3.4: cuantas cuentas abiertas se listan como las mas antiguas del ciclo.
_CUENTAS_MAS_ANTIGUAS = 5


def _como_utc(instante: datetime) -> datetime:
    """SQLite (pruebas) devuelve instantes sin zona; Postgres, con zona.
    Los instantes del almacen se guardan siempre en UTC."""
    return instante if instante.tzinfo is not None else instante.replace(tzinfo=UTC)


def _horas_entre(inicio: datetime, fin: datetime) -> float:
    return max((fin - inicio).total_seconds(), 0.0) / 3600


def _tiempo_por_etapa(proyecciones: list[ProyeccionCicloCuentaModelo]) -> list[TiempoEtapa]:
    """Promedio de horas por estado alcanzado, desde la proyeccion (RNF-04):
    la suma de horas y de transiciones de todas las cuentas del filtro."""
    acumulado: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for proyeccion in proyecciones:
        for etapa, (horas, transiciones) in (proyeccion.tiempos or {}).items():
            acumulado[etapa][0] += float(horas)
            acumulado[etapa][1] += int(transiciones)
    return [
        TiempoEtapa(
            etapa=etapa, promedio_horas=horas / transiciones, transiciones=int(transiciones)
        )
        for etapa, (horas, transiciones) in sorted(acumulado.items())
        if transiciones
    ]


def _rango_del_periodo(periodo: str) -> tuple[date, date]:
    """`periodo` en formato AAAAMM (Seccion 6.1) -> primer y ultimo dia
    de ese mes."""

    anio, mes = int(periodo[:4]), int(periodo[4:6])
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio + 1, 1, 1) if mes == 12 else date(anio, mes + 1, 1)
    return primer_dia, ultimo_dia


class RepositorioTrazabilidadSql(RepositorioTrazabilidad):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def existe_cuenta(self, cuenta_medica_id: int) -> bool:
        return (
            await self._sesion.execute(
                sa.select(CuentaMedicaModelo.id).where(CuentaMedicaModelo.id == cuenta_medica_id)
            )
        ).scalar_one_or_none() is not None

    async def historial_de_cuenta(self, cuenta_medica_id: int) -> HistorialCuenta:
        eventos, rupturas = await self._historial_de("CUENTA", cuenta_medica_id)
        return HistorialCuenta(
            cuenta_medica_id=cuenta_medica_id,
            eventos=eventos,
            cadena_integra=not rupturas,
            rupturas=rupturas,
        )

    async def historial_de_lote(self, lote_id: int) -> HistorialLote:
        eventos, rupturas = await self._historial_de("LOTE", lote_id)
        return HistorialLote(
            lote_id=lote_id, eventos=eventos, cadena_integra=not rupturas, rupturas=rupturas
        )

    async def existe_lote(self, lote_id: int) -> bool:
        return await self._sesion.get(LoteFacturacionModelo, lote_id) is not None

    async def _historial_de(
        self, tipo_agregado: str, agregado_id: int
    ) -> tuple[list[EventoHistorial], list[str]]:
        filas = (
            (
                await self._sesion.execute(
                    sa.select(EventoModelo)
                    .where(
                        EventoModelo.tipo_agregado == tipo_agregado,
                        EventoModelo.agregado_id == agregado_id,
                    )
                    .order_by(EventoModelo.version)
                )
            )
            .scalars()
            .all()
        )

        clave = obtener_configuracion().clave_hmac_eventos.encode("utf-8")
        hash_anterior = GENESIS
        rupturas: list[str] = []
        eventos: list[EventoHistorial] = []
        for fila in filas:
            hash_esperado = calcular_hash_evento_de_fila(
                clave,
                hash_anterior,
                {
                    "tipo_agregado": fila.tipo_agregado,
                    "agregado_id": fila.agregado_id,
                    "version": fila.version,
                    "tipo_evento": fila.tipo_evento,
                    "actor": fila.actor,
                    "estado_previo": fila.estado_previo,
                    "estado_nuevo": fila.estado_nuevo,
                    "ocurrido_en": fila.ocurrido_en,
                },
            )
            if hash_esperado != fila.hash_evento:
                rupturas.append(f"version {fila.version}: el valor resumen no coincide")
            hash_anterior = hash_esperado
            eventos.append(
                EventoHistorial(
                    tipo_evento=fila.tipo_evento,
                    actor=fila.actor,
                    estado_previo=fila.estado_previo,
                    estado_nuevo=fila.estado_nuevo,
                    ocurrido_en=fila.ocurrido_en,
                    datos=fila.datos,
                )
            )
        return eventos, rupturas

    async def documentos_de_cuenta(self, cuenta_medica_id: int) -> list[DocumentoExpediente]:
        documentos: list[DocumentoExpediente] = []

        acreditacion = (
            await self._sesion.execute(
                sa.select(AcreditacionModelo).where(
                    AcreditacionModelo.cuenta_id == cuenta_medica_id
                )
            )
        ).scalar_one_or_none()
        if acreditacion is not None:
            documentos.append(
                DocumentoExpediente(
                    tipo="ACREDITACION",
                    referencia=acreditacion.codigo_autorizacion,
                    emitido_en=acreditacion.instante,
                )
            )

        comprobante = (
            await self._sesion.execute(
                sa.select(DocumentoFacturadorModelo).where(
                    DocumentoFacturadorModelo.cuenta_id == cuenta_medica_id
                )
            )
        ).scalar_one_or_none()
        if comprobante is not None:
            referencia = (
                f"{comprobante.tipo_documento_pago}-{comprobante.serie}-{comprobante.numero}"
            )
            documentos.append(
                DocumentoExpediente(
                    tipo="COMPROBANTE_PAGO",
                    referencia=referencia,
                    emitido_en=None,
                )
            )
        return documentos

    async def calcular_indicadores(
        self, filtro: FiltroIndicadores, ahora: datetime | None = None
    ) -> IndicadoresCiclo:
        cuenta_ids = await self._cuentas_del_filtro(filtro)
        proyecciones = await self._proyecciones(cuenta_ids)
        return IndicadoresCiclo(
            tiempo_por_etapa=_tiempo_por_etapa(proyecciones),
            pct_lotes_observados=await self._pct_lotes(filtro, "OBSERVADO_VALIDADOR"),
            pct_lotes_rechazados=await self._pct_lotes(filtro, "RECHAZADO"),
            tasa_glosas=await self._tasa_glosas(cuenta_ids),
            distribucion_por_estado=await self._distribucion_por_estado(cuenta_ids),
            cartera_por_cobrar=await self._cartera_por_cobrar(cuenta_ids),
            lotes_evaluados=await self._contar_lotes(filtro),
            cuentas_evaluadas=len(cuenta_ids),
            lotes_por_periodo=await self._lotes_por_periodo(filtro.iafas_codigo),
            por_iafas=await self._indicadores_por_iafas(filtro.periodo),
            tiempo_ciclo_cuentas=await self._tiempo_ciclo_cuentas(
                proyecciones, _como_utc(ahora or datetime.now(UTC))
            ),
            registros_contingencia=await self._registros_contingencia(cuenta_ids, filtro),
        )

    async def _registros_contingencia(
        self, cuenta_ids: list[int], filtro: FiltroIndicadores
    ) -> RegistrosContingencia:
        """Los de las cuentas y lotes del filtro, con su revision derivada
        de los eventos (un registro sin CONTINGENCIA_REVISADA posterior
        sigue pendiente)."""
        lote_ids = self._lotes_del_filtro(filtro).with_only_columns(LoteFacturacionModelo.id)
        filas = (
            await self._sesion.execute(
                sa.select(
                    EventoModelo.evento_id, EventoModelo.tipo_evento, EventoModelo.datos
                ).where(
                    EventoModelo.tipo_evento.in_(_TIPOS_EVENTO_CONTINGENCIA),
                    sa.or_(
                        sa.and_(
                            EventoModelo.tipo_agregado == "CUENTA",
                            EventoModelo.agregado_id.in_(cuenta_ids),
                        ),
                        sa.and_(
                            EventoModelo.tipo_agregado == "LOTE",
                            EventoModelo.agregado_id.in_(lote_ids.scalar_subquery()),
                        ),
                    ),
                )
            )
        ).all()
        revisados = {
            str((datos or {}).get("registro_evento_id"))
            for _, tipo, datos in filas
            if tipo == "CONTINGENCIA_REVISADA"
        }
        registros = [
            str(evento_id) for evento_id, tipo, _ in filas if tipo != "CONTINGENCIA_REVISADA"
        ]
        return RegistrosContingencia(
            total=len(registros),
            pendientes_revision=sum(1 for r in registros if r not in revisados),
        )

    async def _tiempo_ciclo_cuentas(
        self, proyecciones: list[ProyeccionCicloCuentaModelo], ahora: datetime
    ) -> TiempoCicloCuentas:
        horas_cerradas: list[float] = []
        horas_abiertas: dict[int, float] = {}
        for proyeccion in proyecciones:
            if proyeccion.primer_cambio_en is None:
                continue
            inicio = _como_utc(proyeccion.primer_cambio_en)
            if proyeccion.estado == "CERRADA" and proyeccion.cerrada_en is not None:
                horas_cerradas.append(_horas_entre(inicio, _como_utc(proyeccion.cerrada_en)))
            elif proyeccion.estado != "ANULADA":
                horas_abiertas[proyeccion.cuenta_medica_id] = _horas_entre(inicio, ahora)

        mas_antiguas = sorted(horas_abiertas.items(), key=lambda par: par[1], reverse=True)[
            :_CUENTAS_MAS_ANTIGUAS
        ]
        return TiempoCicloCuentas(
            cuentas_cerradas=len(horas_cerradas),
            promedio_horas_cerradas=statistics.fmean(horas_cerradas) if horas_cerradas else None,
            mediana_horas_cerradas=statistics.median(horas_cerradas) if horas_cerradas else None,
            cuentas_abiertas=len(horas_abiertas),
            promedio_horas_abiertas=(
                statistics.fmean(horas_abiertas.values()) if horas_abiertas else None
            ),
            mas_antiguas_abiertas=await self._ciclos_de_cuentas(dict(mas_antiguas)),
        )

    async def _ciclos_de_cuentas(self, horas_por_cuenta: dict[int, float]) -> list[CicloCuenta]:
        if not horas_por_cuenta:
            return []
        filas = (
            await self._sesion.execute(
                sa.select(
                    CuentaMedicaModelo.id,
                    CuentaMedicaModelo.identificacion_interna,
                    CuentaMedicaModelo.estado,
                ).where(CuentaMedicaModelo.id.in_(horas_por_cuenta))
            )
        ).all()
        datos = {fila[0]: (fila[1], fila[2]) for fila in filas}
        return [
            CicloCuenta(
                cuenta_medica_id=cuenta_id,
                identificacion_interna=datos[cuenta_id][0],
                estado=datos[cuenta_id][1],
                horas=horas,
            )
            for cuenta_id, horas in horas_por_cuenta.items()
            if cuenta_id in datos
        ]

    async def _lotes_por_periodo(self, iafas_codigo: str | None) -> list[LotesPeriodoEstado]:
        consulta = (
            self._lotes_del_filtro(FiltroIndicadores(iafas_codigo=iafas_codigo))
            .with_only_columns(
                LoteFacturacionModelo.periodo,
                LoteFacturacionModelo.estado,
                sa.func.count(LoteFacturacionModelo.id),
            )
            .group_by(LoteFacturacionModelo.periodo, LoteFacturacionModelo.estado)
            .order_by(LoteFacturacionModelo.periodo, LoteFacturacionModelo.estado)
        )
        filas = (await self._sesion.execute(consulta)).all()
        return [
            LotesPeriodoEstado(periodo=periodo, estado=estado, cantidad=cantidad)
            for periodo, estado, cantidad in filas
        ]

    async def _indicadores_por_iafas(self, periodo: str | None) -> list[IndicadoresIafas]:
        """Reusa los mismos calculos del panel global, una IAFAS a la vez:
        pocas IAFAS en el prototipo, y asi no hay una segunda formula de
        cada indicador que pueda divergir de la primera."""
        todas = (
            (await self._sesion.execute(sa.select(IafasModelo).order_by(IafasModelo.codigo)))
            .scalars()
            .all()
        )
        resultado: list[IndicadoresIafas] = []
        for iafas in todas:
            filtro = FiltroIndicadores(iafas_codigo=iafas.codigo, periodo=periodo)
            cuenta_ids = await self._cuentas_del_filtro(filtro)
            resultado.append(
                IndicadoresIafas(
                    iafas_codigo=iafas.codigo,
                    iafas_razon_social=iafas.razon_social,
                    cuentas=len(cuenta_ids),
                    monto_registrado=await self._monto_registrado(cuenta_ids),
                    cartera_por_cobrar=await self._cartera_por_cobrar(cuenta_ids),
                    tasa_glosas=await self._tasa_glosas(cuenta_ids),
                    lotes=await self._contar_lotes(filtro),
                    pct_lotes_observados=await self._pct_lotes(filtro, "OBSERVADO_VALIDADOR"),
                )
            )
        return resultado

    async def _monto_registrado(self, cuenta_ids: list[int]) -> Decimal:
        if not cuenta_ids:
            return Decimal("0.00")
        procedimientos = (
            await self._sesion.execute(
                sa.select(
                    sa.func.sum(
                        ProcedimientoFacturadoModelo.cantidad
                        * ProcedimientoFacturadoModelo.monto_unitario
                    )
                ).where(ProcedimientoFacturadoModelo.cuenta_id.in_(cuenta_ids))
            )
        ).scalar_one()
        productos = (
            await self._sesion.execute(
                sa.select(sa.func.sum(ProductoFacturadoModelo.monto_presentado)).where(
                    ProductoFacturadoModelo.cuenta_medica_id.in_(cuenta_ids)
                )
            )
        ).scalar_one()
        return Decimal(str(procedimientos or 0)) + Decimal(str(productos or 0))

    async def _cuentas_del_filtro(self, filtro: FiltroIndicadores) -> list[int]:
        consulta = sa.select(CuentaMedicaModelo.id)
        if filtro.iafas_codigo is not None:
            consulta = consulta.join(
                IafasModelo, IafasModelo.id == CuentaMedicaModelo.iafas_id
            ).where(IafasModelo.codigo == filtro.iafas_codigo)
        if filtro.periodo is not None:
            desde, hasta = _rango_del_periodo(filtro.periodo)
            consulta = consulta.where(
                CuentaMedicaModelo.fecha_prestacion >= desde,
                CuentaMedicaModelo.fecha_prestacion < hasta,
            )
        return list((await self._sesion.execute(consulta)).scalars().all())

    async def _proyecciones(self, cuenta_ids: list[int]) -> list[ProyeccionCicloCuentaModelo]:
        """La proyeccion del ciclo de las cuentas del filtro (RNF-04): el
        panel ya no recorre los eventos de cada cuenta en la consulta."""
        if not cuenta_ids:
            return []
        filas = await self._sesion.execute(
            sa.select(ProyeccionCicloCuentaModelo).where(
                ProyeccionCicloCuentaModelo.cuenta_medica_id.in_(cuenta_ids)
            )
        )
        return list(filas.scalars().all())

    async def _distribucion_por_estado(self, cuenta_ids: list[int]) -> list[DistribucionEstado]:
        if not cuenta_ids:
            return []
        filas = (
            await self._sesion.execute(
                sa.select(CuentaMedicaModelo.estado, sa.func.count())
                .where(CuentaMedicaModelo.id.in_(cuenta_ids))
                .group_by(CuentaMedicaModelo.estado)
            )
        ).all()
        return [
            DistribucionEstado(estado=estado, cantidad=cantidad)
            for estado, cantidad in sorted(filas)
        ]

    async def _tasa_glosas(self, cuenta_ids: list[int]) -> float:
        if not cuenta_ids:
            return 0.0
        con_glosa = await self._sesion.scalar(
            sa.select(sa.func.count()).where(
                ProyeccionCicloCuentaModelo.cuenta_medica_id.in_(cuenta_ids),
                ProyeccionCicloCuentaModelo.glosada.is_(True),
            )
        )
        return int(con_glosa or 0) / len(cuenta_ids)

    async def _cartera_por_cobrar(self, cuenta_ids: list[int]) -> Decimal:
        if not cuenta_ids:
            return Decimal("0.00")
        filas = (
            await self._sesion.execute(
                sa.select(LiquidacionModelo.diferencia).where(
                    LiquidacionModelo.cuenta_medica_id.in_(cuenta_ids),
                    LiquidacionModelo.diferencia.is_not(None),
                    LiquidacionModelo.diferencia < 0,
                )
            )
        ).scalars()
        return sum(
            (-diferencia for diferencia in filas if diferencia is not None), start=Decimal("0.00")
        )

    def _lotes_del_filtro(
        self, filtro: FiltroIndicadores
    ) -> sa.Select[tuple[LoteFacturacionModelo]]:
        consulta = sa.select(LoteFacturacionModelo)
        if filtro.iafas_codigo is not None:
            consulta = consulta.join(
                IafasModelo, IafasModelo.id == LoteFacturacionModelo.iafas_id
            ).where(IafasModelo.codigo == filtro.iafas_codigo)
        if filtro.periodo is not None:
            consulta = consulta.where(LoteFacturacionModelo.periodo == filtro.periodo)
        return consulta

    async def _contar_lotes(self, filtro: FiltroIndicadores) -> int:
        consulta = self._lotes_del_filtro(filtro).with_only_columns(
            sa.func.count(LoteFacturacionModelo.id)
        )
        return (await self._sesion.execute(consulta)).scalar_one()

    async def _pct_lotes(self, filtro: FiltroIndicadores, estado: str) -> float:
        total = await self._contar_lotes(filtro)
        if total == 0:
            return 0.0
        consulta = (
            self._lotes_del_filtro(filtro)
            .with_only_columns(sa.func.count(LoteFacturacionModelo.id))
            .where(LoteFacturacionModelo.estado == estado)
        )
        con_estado = (await self._sesion.execute(consulta)).scalar_one()
        return con_estado / total
