"""Adaptador de RepositorioIngestaCuentas y RepositorioCompletitudCuenta
(adenda de ingesta y completitud, previa a R1.4)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.acreditacion.valores import es_acreditable
from app.dominio.integracion.correccion_asegurado import (
    ESTADOS_SIN_SALIDA,
    RepositorioCorreccionAsegurado,
)
from app.dominio.integracion.puertos_ingesta import (
    AseguradoRegistrado,
    DatosNuevaCuenta,
    ErrorIafasInexistente,
    EstadoPiezasCuenta,
    LoteDeCuenta,
    RepositorioCompletitudCuenta,
    RepositorioIngestaCuentas,
)
from app.infraestructura.persistencia.cifrado_columnas import indice_ciego
from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.repositorio_por_codificar_sql import (
    contar_por_codificar,
    tiene_carta_garantia,
)
from app.infraestructura.persistencia.revision_contingencia_sql import (
    acreditacion_vigente_no_conforme,
)


class RepositorioIngestaCuentasSql(RepositorioIngestaCuentas):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def crear_cuenta(self, datos: DatosNuevaCuenta) -> int:
        iafas = await self._sesion.get(IafasModelo, datos.iafas_id)
        if iafas is None:
            raise ErrorIafasInexistente(datos.iafas_id)

        ipress_id = await self._sesion.scalar(sa.select(IpressModelo.id).limit(1))
        assert ipress_id is not None, "No hay ninguna IPRESS sembrada (Seccion 6.1)."

        asegurado_id = await self.obtener_o_crear_asegurado(datos)

        cuenta = CuentaMedicaModelo(
            identificacion_interna="",  # se completa abajo, ya con el id
            asegurado_id=asegurado_id,
            iafas_id=datos.iafas_id,
            ipress_id=ipress_id,
            fecha_prestacion=datos.fecha_prestacion,
            hora_prestacion=datos.hora_prestacion,
            numero_historia_clinica="",
            diagnostico_principal_cie10=datos.diagnostico_principal_cie10,
            estado="REGISTRADA",
        )
        self._sesion.add(cuenta)
        await self._sesion.flush()  # asigna cuenta.id sin cerrar la transaccion

        cuenta.identificacion_interna = f"CTA-{cuenta.id:06d}"
        cuenta.numero_historia_clinica = f"{cuenta.id:08d}"
        await self._sesion.commit()
        return cuenta.id

    async def existe_cie10(self, codigo: str) -> bool:
        encontrado = await self._sesion.scalar(
            sa.select(sa.literal(True))
            .select_from(Cie10CodigoModelo)
            .where(Cie10CodigoModelo.codigo == codigo)
            .limit(1)
        )
        return bool(encontrado)

    async def _asegurado(self, tipo_documento: str, numero: str) -> AseguradoModelo | None:
        resultado = await self._sesion.execute(
            # C-05: el documento esta cifrado; se busca por su indice ciego.
            sa.select(AseguradoModelo).where(
                AseguradoModelo.documento_indice == indice_ciego(tipo_documento, numero)
            )
        )
        return resultado.scalar_one_or_none()

    async def buscar_asegurado(
        self, tipo_documento: str, numero_documento: str
    ) -> AseguradoRegistrado | None:
        asegurado = await self._asegurado(tipo_documento, numero_documento)
        if asegurado is None:
            return None
        return AseguradoRegistrado(
            nombres=asegurado.nombres,
            apellidos=asegurado.apellidos,
            iafas_id=asegurado.iafas_id,
        )

    async def obtener_o_crear_asegurado(self, datos: DatosNuevaCuenta) -> int:
        """Tambien la usa la importacion de la atencion (2026-11-19)."""
        existente = await self._asegurado(
            datos.tipo_documento_asegurado, datos.numero_documento_asegurado
        )
        if existente is not None:
            return existente.id

        asegurado = AseguradoModelo(
            tipo_documento=datos.tipo_documento_asegurado,
            numero_documento=datos.numero_documento_asegurado,
            nombres=datos.nombres_asegurado,
            apellidos=datos.apellidos_asegurado,
            iafas_id=datos.iafas_id,
            ficticio=True,
        )
        self._sesion.add(asegurado)
        await self._sesion.flush()
        return asegurado.id


async def otras_cuentas_avanzadas(sesion: AsyncSession, cuenta: CuentaMedicaModelo) -> bool:
    """Otra cuenta del mismo asegurado fuera de Registrada o Anulada."""
    encontrada = await sesion.scalar(
        sa.select(sa.literal(True))
        .select_from(CuentaMedicaModelo)
        .where(
            CuentaMedicaModelo.asegurado_id == cuenta.asegurado_id,
            CuentaMedicaModelo.id != cuenta.id,
            CuentaMedicaModelo.estado.not_in(sorted(ESTADOS_SIN_SALIDA)),
        )
        .limit(1)
    )
    return bool(encontrada)


class RepositorioCorreccionAseguradoSql(RepositorioCorreccionAsegurado):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def estado_cuenta(self, cuenta_id: int) -> str | None:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        return cuenta.estado if cuenta is not None else None

    async def asegurado_con_otras_cuentas_avanzadas(self, cuenta_id: int) -> bool:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None
        return await otras_cuentas_avanzadas(self._sesion, cuenta)

    async def corregir_nombres(self, cuenta_id: int, nombres: str, apellidos: str) -> None:
        # Por el modelo y no con un UPDATE: los nombres se guardan cifrados (C-05).
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        assert cuenta is not None
        asegurado = await self._sesion.get(AseguradoModelo, cuenta.asegurado_id)
        assert asegurado is not None
        asegurado.nombres, asegurado.apellidos = nombres, apellidos
        await self._sesion.flush()


class RepositorioCompletitudCuentaSql(RepositorioCompletitudCuenta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_estado_piezas(self, cuenta_id: int) -> EstadoPiezasCuenta | None:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        if cuenta is None:
            return None

        condicion = await self._sesion.scalar(
            sa.select(AcreditacionModelo.condicion_cobertura)
            .where(AcreditacionModelo.cuenta_id == cuenta_id)
            .order_by(AcreditacionModelo.id.desc())  # la vigente
            .limit(1)
        )
        cantidad_procedimientos = (
            await self._sesion.scalar(
                sa.select(sa.func.count())
                .select_from(ProcedimientoFacturadoModelo)
                .where(ProcedimientoFacturadoModelo.cuenta_id == cuenta_id)
            )
            or 0
        )
        tiene_comprobante = (
            await self._sesion.scalar(
                sa.select(sa.literal(True))
                .select_from(DocumentoFacturadorModelo)
                .where(DocumentoFacturadorModelo.cuenta_id == cuenta_id)
                .limit(1)
            )
            or False
        )

        return EstadoPiezasCuenta(
            estado_cuenta=cuenta.estado,
            tiene_acreditacion=condicion is not None,
            acreditable=condicion is None or es_acreditable(condicion),
            cantidad_procedimientos=cantidad_procedimientos,
            tiene_comprobante=tiene_comprobante,
            tiene_diagnostico=bool(cuenta.diagnostico_principal_cie10),
            lote=await self._lote_de(cuenta_id),
            procedimientos_por_codificar=await contar_por_codificar(self._sesion, cuenta_id),
            exige_carta_garantia=cuenta.tipo_atencion == "HOSPITALIZACION",
            tiene_carta_garantia=await tiene_carta_garantia(self._sesion, cuenta_id),
            cobertura_no_conforme=await acreditacion_vigente_no_conforme(self._sesion, cuenta_id),
        )

    async def _lote_de(self, cuenta_id: int) -> LoteDeCuenta | None:
        fila = (
            await self._sesion.execute(
                sa.select(
                    LoteFacturacionModelo.id,
                    LoteFacturacionModelo.numero,
                    LoteFacturacionModelo.estado,
                )
                .join(LoteDocumentoModelo, LoteDocumentoModelo.lote_id == LoteFacturacionModelo.id)
                .join(
                    DocumentoFacturadorModelo,
                    DocumentoFacturadorModelo.id == LoteDocumentoModelo.documento_id,
                )
                .where(DocumentoFacturadorModelo.cuenta_id == cuenta_id)
                .order_by(LoteFacturacionModelo.generado_en.desc())
                .limit(1)
            )
        ).first()
        return LoteDeCuenta(lote_id=fila[0], numero=fila[1], estado=fila[2]) if fila else None

    async def marcar_facturada(self, cuenta_id: int) -> None:
        await self._sesion.execute(
            sa.update(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_id, CuentaMedicaModelo.estado == "REGISTRADA")
            .values(estado="FACTURADA")
        )
        await self._sesion.commit()
