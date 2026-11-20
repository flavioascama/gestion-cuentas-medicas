"""Cuenta en correccion por el validador TEDEF Web: FACTURADA y con su
lote mas reciente OBSERVADO_VALIDADOR. El adaptador SQL contra SQLite en
memoria y, en los cuatro casos de uso que editan la cuenta, que esa
condicion admite la operacion y una FACTURADA normal la sigue rechazando."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.cpms.casos_uso import (
    ConfirmacionCodigoCpms,
    ConfirmarCodigoCpms,
    ErrorCuentaNoCodificable,
    QuitarProcedimiento,
)
from app.dominio.farmacia.dispensacion import (
    ErrorCuentaNoEditableFarmacia,
    QuitarProductoDispensado,
    RegistrarProductoDispensado,
)
from app.dominio.integracion.diagnostico_cuenta import (
    ErrorDiagnosticoNoAdmitido,
    RegistrarDiagnosticoPrincipal,
)
from app.dominio.pse.documentos import ErrorEstadoNoAdmiteDocumento
from app.infraestructura.persistencia.modelos_integracion import (
    CuentaMedicaModelo,
    LoteDocumentoModelo,
    LoteFacturacionModelo,
)
from app.infraestructura.persistencia.repositorio_estado_cuenta_sql import (
    RepositorioEstadoCuentaSql,
)
from pruebas import prueba_casos_uso_cpms as cpms
from pruebas import prueba_documentos_pago as pago
from pruebas import prueba_farmacia_dispensacion as farmacia
from pruebas.prueba_repositorio_monitoreo_respuesta import (
    _sembrar_cuenta_enviada,
    _sembrar_lote_remitido,
)

# --- Adaptador SQL ---


async def _cuenta_con_lote(sesion: AsyncSession, estado_lote: str) -> tuple[int, int]:
    """(lote_id, cuenta_id): cuenta FACTURADA cuyo unico lote tiene `estado_lote`."""
    lote_id, cuenta_id = await _sembrar_lote_remitido(sesion)
    await sesion.execute(
        sa.update(LoteFacturacionModelo)
        .where(LoteFacturacionModelo.id == lote_id)
        .values(estado=estado_lote)
    )
    await sesion.execute(
        sa.update(CuentaMedicaModelo)
        .where(CuentaMedicaModelo.id == cuenta_id)
        .values(estado="FACTURADA")
    )
    await sesion.commit()
    return lote_id, cuenta_id


async def prueba_lote_mas_reciente_observado_pone_la_cuenta_en_correccion(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        _, cuenta_id = await _cuenta_con_lote(sesion, "OBSERVADO_VALIDADOR")
        assert await RepositorioEstadoCuentaSql(sesion).en_correccion_validador(cuenta_id)


async def prueba_al_entrar_a_un_lote_nuevo_deja_de_estar_en_correccion(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        lote_id, cuenta_id = await _cuenta_con_lote(sesion, "OBSERVADO_VALIDADOR")
        observado = await sesion.get(LoteFacturacionModelo, lote_id)
        assert observado is not None
        (documento_id,) = (
            await sesion.execute(
                sa.select(LoteDocumentoModelo.documento_id).where(
                    LoteDocumentoModelo.lote_id == lote_id
                )
            )
        ).scalars()
        nuevo = LoteFacturacionModelo(
            numero="0000002",
            iafas_id=observado.iafas_id,
            periodo="202609",
            generado_en=datetime(2026, 9, 20, 8, 0, 0),
            estado="GENERADO",
        )
        sesion.add(nuevo)
        await sesion.flush()
        sesion.add(LoteDocumentoModelo(lote_id=nuevo.id, documento_id=documento_id))
        await sesion.commit()
        assert not await RepositorioEstadoCuentaSql(sesion).en_correccion_validador(cuenta_id)


async def prueba_lote_validado_no_pone_la_cuenta_en_correccion(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        _, cuenta_id = await _cuenta_con_lote(sesion, "VALIDADO")
        assert not await RepositorioEstadoCuentaSql(sesion).en_correccion_validador(cuenta_id)


async def prueba_cuenta_sin_lote_no_esta_en_correccion(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        _, _, cuenta_id = await _sembrar_cuenta_enviada(sesion, ventana_monitoreo_horas=48)
        await sesion.execute(
            sa.update(CuentaMedicaModelo)
            .where(CuentaMedicaModelo.id == cuenta_id)
            .values(estado="FACTURADA")
        )
        await sesion.commit()
        assert not await RepositorioEstadoCuentaSql(sesion).en_correccion_validador(cuenta_id)


# --- Casos de uso: FACTURADA en correccion admite, FACTURADA normal rechaza ---

_CONFIRMACION = ConfirmacionCodigoCpms(
    cuenta_medica_id=7,
    descripcion_registrada="consulta",
    codigo_elegido="99201",
    posicion_aceptada=None,
    usuario_confirmo_id=3,
    cantidad=1,
    monto_unitario=Decimal("1.00"),
    fecha=date(2026, 9, 16),
)


def _confirmar(en_correccion: bool) -> tuple[ConfirmarCodigoCpms, cpms._RepositorioFalso]:
    repositorio = cpms._RepositorioFalso(codigos_existentes={"99201": cpms._candidato("99201")})
    caso_uso = ConfirmarCodigoCpms(
        repositorio=repositorio,  # type: ignore[arg-type]
        registro_mediciones=cpms._RegistroMedicionesFalso(),  # type: ignore[arg-type]
        reloj=cpms._RelojFijo(datetime(2026, 9, 16, 10, 5, 0)),
        estado_cuenta=cpms._EstadoCuentaFijo("FACTURADA", en_correccion),
    )
    return caso_uso, repositorio


async def prueba_codificacion_en_correccion_por_el_validador() -> None:
    inicio = datetime(2026, 9, 16, 10, 0, 0)
    caso_uso, repositorio = _confirmar(en_correccion=True)
    await caso_uso.ejecutar(_CONFIRMACION, actor="prueba", inicio_sugerencia=inicio)
    assert len(repositorio.confirmaciones) == 1

    quitar = QuitarProcedimiento(
        repositorio,  # type: ignore[arg-type]
        cpms._EstadoCuentaFijo("FACTURADA", en_correccion=True),
        cpms._RegistroEventosFalso(),
    )
    await quitar.ejecutar(7, 41, actor="carlos.auditor")
    assert repositorio.quitados == [41]

    caso_uso, _ = _confirmar(en_correccion=False)
    with pytest.raises(ErrorCuentaNoCodificable):
        await caso_uso.ejecutar(_CONFIRMACION, actor="prueba", inicio_sugerencia=inicio)


async def prueba_farmacia_en_correccion_por_el_validador() -> None:
    repositorio, registro = farmacia._RepositorioFalso(), farmacia._RegistroEventosFalso()
    estado = farmacia._EstadoFijo("FACTURADA", en_correccion=True)
    await RegistrarProductoDispensado(repositorio, estado, registro).ejecutar(
        7, farmacia._DATOS, actor="ana.analista"
    )
    await QuitarProductoDispensado(repositorio, estado, registro).ejecutar(
        7, 41, actor="ana.analista"
    )
    assert (len(repositorio.guardados), repositorio.quitados) == (1, [41])

    normal = farmacia._EstadoFijo("FACTURADA")
    with pytest.raises(ErrorCuentaNoEditableFarmacia):
        await RegistrarProductoDispensado(repositorio, normal, registro).ejecutar(
            7, farmacia._DATOS, actor="ana.analista"
        )


@dataclass
class _RepositorioDiagnosticoFalso:
    fijados: list[str] = field(default_factory=list)

    async def estado_y_diagnostico(self, cuenta_id: int) -> tuple[str, str | None] | None:
        return "FACTURADA", "A090"

    async def existe_cie10(self, codigo: str) -> bool:
        return True

    async def fijar_diagnostico(self, cuenta_id: int, codigo: str) -> None:
        self.fijados.append(codigo)


async def prueba_diagnostico_registrado_se_cambia_en_correccion_por_el_validador() -> None:
    repositorio = _RepositorioDiagnosticoFalso()
    registro = farmacia._RegistroEventosFalso()
    en_correccion = farmacia._EstadoFijo("FACTURADA", en_correccion=True)
    caso_uso = RegistrarDiagnosticoPrincipal(repositorio, registro, en_correccion)
    assert await caso_uso.ejecutar(7, "a072", "carlos.auditor") == "A072"
    assert repositorio.fijados == ["A072"]

    normal = RegistrarDiagnosticoPrincipal(repositorio, registro, farmacia._EstadoFijo("FACTURADA"))
    with pytest.raises(ErrorDiagnosticoNoAdmitido):
        await normal.ejecutar(7, "A072", "carlos.auditor")


async def prueba_reemplazo_en_correccion_por_el_validador() -> None:
    documentos = pago._Documentos()
    caso_uso = pago.ReemplazarComprobantePago(
        documentos,
        pago.EmisionPse(pago._Comprobantes(), pago._Emisor()),
        pago._EstadoFijo("FACTURADA", en_correccion=True),
        pago._Registro(),
        pago._Reloj(),
    )
    vigente = await caso_uso.ejecutar(7, "Correccion por observacion del validador", "ana")
    assert vigente.numero == "00000999"
    assert len(documentos.reemplazos) == 1

    normal, _ = pago._reemplazo(pago._Documentos(), "FACTURADA")
    with pytest.raises(ErrorEstadoNoAdmiteDocumento):
        await normal.ejecutar(7, "motivo", "ana")
