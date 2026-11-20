"""Adaptador de RepositorioImportacionAtencion (2026-11-19): crea la cuenta
de una atencion del sistema hospitalario con sus procedimientos por
codificar, sus productos de farmacia y su copago cobrado, sin confirmar la
transaccion (la confirma el evento que registra el caso de uso)."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.dominio.farmacia.dispensacion import ProductoARegistrar, ProductoCatalogo
from app.dominio.integracion.atencion_hospitalaria import (
    AtencionHospitalaria,
    CuentaImportada,
    RepositorioImportacionAtencion,
)
from app.dominio.integracion.copago_cobrado import ORIGEN_SISTEMA_HOSPITALARIO, CopagoCobrado
from app.dominio.integracion.puertos_ingesta import DatosNuevaCuenta
from app.infraestructura.persistencia.modelos_atencion_hospitalaria import (
    ProcedimientoPorCodificarModelo,
)
from app.infraestructura.persistencia.modelos_cie10 import Cie10CodigoModelo, Cie10VersionModelo
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.repositorio_dispensacion_sql import (
    RepositorioDispensacionSql,
)
from app.infraestructura.persistencia.repositorio_ingesta_cuentas_sql import (
    RepositorioIngestaCuentasSql,
)
from app.infraestructura.persistencia.repositorio_por_codificar_sql import (
    RepositorioCopagoCobradoSql,
)


def _datos_asegurado(atencion: AtencionHospitalaria, iafas_id: int) -> DatosNuevaCuenta:
    paciente = atencion.paciente
    return DatosNuevaCuenta(
        tipo_documento_asegurado=paciente.tipo_documento,
        numero_documento_asegurado=paciente.numero_documento,
        nombres_asegurado=paciente.nombres,
        apellidos_asegurado=paciente.apellidos,
        iafas_id=iafas_id,
        fecha_prestacion=atencion.fecha_prestacion,
        hora_prestacion=atencion.hora_prestacion,
        diagnostico_principal_cie10=atencion.diagnostico_principal_cie10,
    )


def _cuenta(cuenta: CuentaImportada, asegurado_id: int, ipress_id: int) -> CuentaMedicaModelo:
    atencion = cuenta.atencion
    hospitalizacion = atencion.hospitalizacion
    return CuentaMedicaModelo(
        identificacion_interna="",  # se completa con el id, como la cuenta manual
        asegurado_id=asegurado_id,
        iafas_id=cuenta.iafas_id,
        ipress_id=ipress_id,
        fecha_prestacion=atencion.fecha_prestacion,
        hora_prestacion=atencion.hora_prestacion,
        numero_historia_clinica=atencion.numero_historia_clinica.strip(),
        diagnostico_principal_cie10=atencion.diagnostico_principal_cie10,
        estado="REGISTRADA",
        tipo_atencion=atencion.tipo_atencion,
        atencion_origen_id=atencion.atencion_id,
        colegiatura_medico=atencion.profesional.numero_colegiatura.strip(),
        nombre_medico=atencion.profesional.nombres,
        diagnosticos_secundarios_cie10=",".join(atencion.diagnosticos_secundarios_cie10) or None,
        fecha_ingreso_hospitalario=hospitalizacion.fecha_ingreso if hospitalizacion else None,
        fecha_alta_hospitalaria=hospitalizacion.fecha_alta if hospitalizacion else None,
    )


class RepositorioImportacionAtencionSql(RepositorioImportacionAtencion):
    def __init__(self, sesion: AsyncSession) -> None:
        self._sesion = sesion

    async def cuenta_de_atencion(self, atencion_id: str) -> int | None:
        cuenta_id: int | None = await self._sesion.scalar(
            sa.select(CuentaMedicaModelo.id).where(
                CuentaMedicaModelo.atencion_origen_id == atencion_id
            )
        )
        return cuenta_id

    async def atenciones_importadas(self, atencion_ids: list[str]) -> set[str]:
        if not atencion_ids:
            return set()
        filas = await self._sesion.scalars(
            sa.select(CuentaMedicaModelo.atencion_origen_id).where(
                CuentaMedicaModelo.atencion_origen_id.in_(atencion_ids)
            )
        )
        return {fila for fila in filas.all() if fila is not None}

    async def iafas_por_codigo(self, codigo: str) -> int | None:
        iafas_id: int | None = await self._sesion.scalar(
            sa.select(IafasModelo.id).where(IafasModelo.codigo == codigo)
        )
        return iafas_id

    async def cie10_desconocidos(self, codigos: tuple[str, ...]) -> tuple[str, ...]:
        version_id = await self._sesion.scalar(sa.select(sa.func.max(Cie10VersionModelo.id)))
        conocidos: set[str] = set()
        if version_id is not None and codigos:
            filas = await self._sesion.scalars(
                sa.select(Cie10CodigoModelo.codigo).where(
                    Cie10CodigoModelo.cie10_version_id == version_id,
                    Cie10CodigoModelo.codigo.in_(codigos),
                )
            )
            conocidos = set(filas.all())
        return tuple(codigo for codigo in codigos if codigo not in conocidos)

    async def producto_vigente(self, codigo: str) -> ProductoCatalogo | None:
        return await RepositorioDispensacionSql(self._sesion).producto_vigente(codigo)

    async def crear_cuenta_importada(self, cuenta: CuentaImportada) -> int:
        atencion = cuenta.atencion
        ipress_id = await self._sesion.scalar(sa.select(IpressModelo.id).limit(1))
        assert ipress_id is not None, "No hay ninguna IPRESS sembrada (Seccion 6.1)."
        asegurado_id = await RepositorioIngestaCuentasSql(self._sesion).obtener_o_crear_asegurado(
            _datos_asegurado(atencion, cuenta.iafas_id)
        )
        modelo = _cuenta(cuenta, asegurado_id, ipress_id)
        self._sesion.add(modelo)
        await self._sesion.flush()
        modelo.identificacion_interna = f"CTA-{modelo.id:06d}"
        self._sesion.add_all(
            ProcedimientoPorCodificarModelo(
                cuenta_medica_id=modelo.id,
                descripcion=p.descripcion.strip(),
                area=p.area,
                cantidad=p.cantidad,
                monto_unitario=p.monto_unitario,
                fecha=p.fecha,
            )
            for p in atencion.procedimientos
        )
        await self._guardar_productos(modelo.id, cuenta)
        await self._guardar_copago(modelo.id, cuenta)
        await self._sesion.flush()
        return modelo.id

    async def _guardar_productos(self, cuenta_id: int, cuenta: CuentaImportada) -> None:
        # Misma fila y correlativo que el registro manual (T4 campo 6).
        dispensacion = RepositorioDispensacionSql(self._sesion)
        for producto in cuenta.productos:
            await dispensacion.guardar(
                ProductoARegistrar(
                    cuenta_id, producto.catalogo, producto.datos, producto.monto_presentado
                )
            )

    async def _guardar_copago(self, cuenta_id: int, cuenta: CuentaImportada) -> None:
        copago = cuenta.atencion.copago_cobrado
        if copago is None:
            return
        await RepositorioCopagoCobradoSql(self._sesion).registrar(
            cuenta_id,
            CopagoCobrado(
                monto=copago.monto,
                fecha=copago.fecha,
                referencia=copago.referencia.strip(),
                origen=ORIGEN_SISTEMA_HOSPITALARIO,
                registrado_por=cuenta.actor,
            ),
        )
