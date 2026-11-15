"""Adaptador de RepositorioIngestaCuentas y RepositorioCompletitudCuenta
(adenda de ingesta y completitud, previa a R1.4)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.integracion.puertos_ingesta import (
    DatosNuevaCuenta,
    ErrorIafasInexistente,
    EstadoPiezasCuenta,
    RepositorioCompletitudCuenta,
    RepositorioIngestaCuentas,
)
from app.infraestructura.persistencia.cifrado_columnas import indice_ciego
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
    ProcedimientoFacturadoModelo,
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

        asegurado_id = await self._obtener_o_crear_asegurado(datos)

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

    async def _obtener_o_crear_asegurado(self, datos: DatosNuevaCuenta) -> int:
        resultado = await self._sesion.execute(
            # C-05: el documento esta cifrado; se busca por su indice ciego.
            sa.select(AseguradoModelo).where(
                AseguradoModelo.documento_indice
                == indice_ciego(datos.tipo_documento_asegurado, datos.numero_documento_asegurado)
            )
        )
        existente = resultado.scalar_one_or_none()
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


class RepositorioCompletitudCuentaSql(RepositorioCompletitudCuenta):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def obtener_estado_piezas(self, cuenta_id: int) -> EstadoPiezasCuenta | None:
        cuenta = await self._sesion.get(CuentaMedicaModelo, cuenta_id)
        if cuenta is None:
            return None

        tiene_acreditacion = (
            await self._sesion.scalar(
                sa.select(sa.literal(True))
                .select_from(AcreditacionModelo)
                .where(AcreditacionModelo.cuenta_id == cuenta_id)
                .limit(1)
            )
            or False
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
            tiene_acreditacion=tiene_acreditacion,
            cantidad_procedimientos=cantidad_procedimientos,
            tiene_comprobante=tiene_comprobante,
        )

    async def marcar_facturada(self, cuenta_id: int) -> None:
        await self._sesion.execute(
            sa.update(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_id, CuentaMedicaModelo.estado == "REGISTRADA")
            .values(estado="FACTURADA")
        )
        await self._sesion.commit()
