"""Pruebas de RepositorioCpmsSql contra SQLite en memoria (Seccion 8.2)."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.cpms.puertos import DatosConfirmacionCodigo
from app.infraestructura.persistencia.modelos_acceso import UsuarioModelo
from app.infraestructura.persistencia.modelos_cpms import CpmsProcedimientoModelo, CpmsVersionModelo
from app.infraestructura.persistencia.modelos_integracion import (
    AseguradoModelo,
    CuentaMedicaModelo,
    IafasModelo,
    IpressModelo,
    ProcedimientoFacturadoModelo,
)
from app.infraestructura.persistencia.repositorio_cpms_sql import RepositorioCpmsSql


async def _sembrar_catalogo(sesion: AsyncSession) -> tuple[int, int]:
    """Devuelve (version_1_id, version_2_id): dos versiones, para probar
    que 'vigente' es la mas reciente."""

    version_1 = CpmsVersionModelo(etiqueta="2022-01-01", archivos_origen=[], conteo=1)
    sesion.add(version_1)
    await sesion.flush()
    sesion.add(
        CpmsProcedimientoModelo(
            cpms_version_id=version_1.id,
            codigo_grupo="1",
            nombre_grupo="Grupo",
            codigo_seccion="10",
            nombre_seccion="Seccion",
            codigo_subseccion="100",
            nombre_subseccion="Subseccion",
            codigo_procedimiento="00100",
            denominacion_procedimiento="Version vieja",
        )
    )

    version_2 = CpmsVersionModelo(etiqueta="2023-06-05", archivos_origen=[], conteo=1)
    sesion.add(version_2)
    await sesion.flush()
    sesion.add(
        CpmsProcedimientoModelo(
            cpms_version_id=version_2.id,
            codigo_grupo="1",
            nombre_grupo="Grupo",
            codigo_seccion="10",
            nombre_seccion="Seccion",
            codigo_subseccion="100",
            nombre_subseccion="Subseccion",
            codigo_procedimiento="00100",
            denominacion_procedimiento="Anestesia para procedimientos en glandulas salivales",
        )
    )
    await sesion.commit()
    return version_1.id, version_2.id


async def _sembrar_cuenta_y_usuario(sesion: AsyncSession) -> tuple[int, int]:
    iafas = IafasModelo(
        codigo="00012",
        razon_social="IAFAS de prueba",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    ipress = IpressModelo(ruc="20123456789", codigo_ipress="12345678", razon_social="Clinica")
    usuario = UsuarioModelo(nombre_usuario="auditor1", nombres="Auditor Uno", hash_clave="x")
    sesion.add_all([iafas, ipress, usuario])
    await sesion.flush()

    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento="12345678",
        nombres="Ana",
        apellidos="Perez",
        iafas_id=iafas.id,
        ficticio=True,
    )
    sesion.add(asegurado)
    await sesion.flush()

    cuenta = CuentaMedicaModelo(
        identificacion_interna="CTA0000001",
        asegurado_id=asegurado.id,
        iafas_id=iafas.id,
        ipress_id=ipress.id,
        fecha_prestacion=date(2026, 9, 10),
        hora_prestacion=time(9, 0, 0),
        numero_historia_clinica="00000001",
        estado="REGISTRADA",
    )
    sesion.add(cuenta)
    await sesion.commit()
    return cuenta.id, usuario.id


async def prueba_version_vigente_es_la_mas_reciente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        _, version_2_id = await _sembrar_catalogo(sesion)
        repositorio = RepositorioCpmsSql(sesion)
        version_id, etiqueta = await repositorio.version_vigente()
        assert version_id == version_2_id
        assert etiqueta == "2023-06-05"


async def prueba_obtener_candidato_encuentra_el_codigo_en_su_version(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        version_1_id, version_2_id = await _sembrar_catalogo(sesion)
        repositorio = RepositorioCpmsSql(sesion)

        candidato_v2 = await repositorio.obtener_candidato(version_2_id, "00100")
        assert candidato_v2 is not None
        assert candidato_v2.denominacion == "Anestesia para procedimientos en glandulas salivales"

        candidato_v1 = await repositorio.obtener_candidato(version_1_id, "00100")
        assert candidato_v1 is not None
        assert candidato_v1.denominacion == "Version vieja"


async def prueba_obtener_candidato_devuelve_none_si_no_existe(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        _, version_2_id = await _sembrar_catalogo(sesion)
        repositorio = RepositorioCpmsSql(sesion)
        assert await repositorio.obtener_candidato(version_2_id, "99999") is None


async def prueba_listar_procedimientos_solo_de_esa_version(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        version_1_id, version_2_id = await _sembrar_catalogo(sesion)
        repositorio = RepositorioCpmsSql(sesion)
        procedimientos_v1 = await repositorio.listar_procedimientos(version_1_id)
        assert len(procedimientos_v1) == 1
        assert procedimientos_v1[0].denominacion == "Version vieja"


async def prueba_confirmar_codigo_persiste_todos_los_campos_exigidos(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        _, version_2_id = await _sembrar_catalogo(sesion)
        cuenta_id, usuario_id = await _sembrar_cuenta_y_usuario(sesion)
        repositorio = RepositorioCpmsSql(sesion)

        id_creado = await repositorio.confirmar_codigo(
            DatosConfirmacionCodigo(
                cuenta_id=cuenta_id,
                descripcion_registrada="Anestesia para glandulas salivales",
                codigo_asignado="00100",
                cpms_version_id=version_2_id,
                origen_codigo="sugerencia_tfidf",
                posicion_aceptada=2,
                usuario_confirmo_id=usuario_id,
                cantidad=1,
                monto_unitario=Decimal("50.00"),
                fecha=date(2026, 9, 16),
                confirmado_en=datetime(2026, 9, 16, 10, 5, 0),
            )
        )
        assert id_creado > 0

    async with fabrica_sesiones() as sesion:
        registro = await sesion.get(ProcedimientoFacturadoModelo, id_creado)
        assert registro is not None
        assert registro.codigo_asignado == "00100"
        assert registro.origen_codigo == "sugerencia_tfidf"
        assert registro.posicion_aceptada == 2
        assert registro.usuario_confirmo_id == usuario_id
        assert registro.confirmado_en == datetime(2026, 9, 16, 10, 5, 0)
        assert registro.tipo_clasificacion == "01"  # CPMS (Seccion 8.2, dominios.yaml T3 campo 7)
