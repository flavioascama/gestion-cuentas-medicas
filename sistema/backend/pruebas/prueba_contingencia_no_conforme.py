"""Efecto de la revision NO CONFORME del jefe (control C-18): la cobertura
registrada a mano deja de servir para facturar y el lote validado a mano
deja de estar vigente; nada se revierte si ya se avanzo."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.dominio.acreditacion.valores import ContextoCuentaAcreditacion
from app.dominio.contingencia.casos_uso import ConsultarDisponibilidadContingencia
from app.dominio.contingencia.valores import (
    COMPONENTE_REGISTRO_MANUAL,
    TIPO_EVENTO_COBERTURA_CONTINGENCIA,
    TIPO_EVENTO_REVISION_CONTINGENCIA,
    TIPO_EVENTO_VALIDACION_CONTINGENCIA,
)
from app.dominio.integracion.facturacion_cuenta import cobertura
from app.dominio.integracion.vigencia_lote import (
    ErrorLoteDesactualizado,
    VigenciaLote,
    exigir_lote_vigente,
)
from app.dominio.pse.puertos import RequisitosComprobante
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    EventoModelo,
)
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from app.infraestructura.persistencia.repositorio_comprobante_pago_sql import (
    RepositorioComprobantePagoSql,
)
from app.infraestructura.persistencia.repositorio_contingencia_sql import (
    RepositorioContingenciaSql,
)
from app.infraestructura.persistencia.repositorio_ingesta_cuentas_sql import (
    RepositorioCompletitudCuentaSql,
)
from app.infraestructura.persistencia.repositorio_lote_sql import RepositorioLoteFacturacionSql
from app.infraestructura.persistencia.vigencia_lote_sql import (
    cuentas_en_lotes_vigentes,
    vigencia_de_lote,
)
from pruebas.prueba_casos_uso_contingencia import _Contingencia
from pruebas.prueba_lotes_sugeridos import _crear_cuenta
from pruebas.prueba_vigencia_lote_sql import _GENERADO, _acreditar, _base, _lote

_FALTANTE = "una verificación de cobertura conforme"


def prueba_el_comprobante_pide_una_verificacion_conforme() -> None:
    requisitos = RequisitosComprobante(True, True, 1, cobertura_no_conforme=True)
    assert requisitos.faltantes() == (_FALTANTE,)


def prueba_un_lote_con_validacion_no_conforme_no_se_remite() -> None:
    vigencia = VigenciaLote(1, _GENERADO, (), validacion_no_conforme=True)
    assert not vigencia.vigente
    with pytest.raises(ErrorLoteDesactualizado, match="no fue conforme"):
        exigir_lote_vigente(vigencia)


async def _registrar(sesion: AsyncSession, evento: Evento) -> str:
    await RegistroEventosSql(sesion).registrar(evento)
    await sesion.flush()
    return str(
        (
            await sesion.execute(
                sa.select(EventoModelo.evento_id)
                .where(EventoModelo.tipo_evento == evento.tipo_evento)
                .order_by(EventoModelo.version.desc())
                .limit(1)
            )
        ).scalar_one()
    )


async def _revisar(sesion: AsyncSession, registro_id: str, conforme: bool, **agregado: int) -> None:
    await _registrar(
        sesion,
        Evento(
            tipo_evento=TIPO_EVENTO_REVISION_CONTINGENCIA,
            actor="jefe",
            estado_previo=None,
            estado_nuevo=None,
            datos={"registro_evento_id": registro_id, "conforme": conforme, "comentario": ""},
            cuenta_medica_id=agregado.get("cuenta_medica_id"),
            lote_id=agregado.get("lote_id"),
        ),
    )


async def _cobertura_manual(sesion: AsyncSession, cuenta_id: int, conforme: bool) -> None:
    acreditacion = AcreditacionModelo(
        cuenta_id=cuenta_id,
        condicion_cobertura="Cubierto",
        codigo_autorizacion="AUT-9",
        tipo_documento_autorizacion="1",
        codigo_asegurado="ASEG-9",
        tipo_afiliacion="1",
        instante=_GENERADO,
        componente_ejecutor=COMPONENTE_REGISTRO_MANUAL,
    )
    sesion.add(acreditacion)
    await sesion.flush()
    registro_id = await _registrar(
        sesion,
        Evento(
            cuenta_medica_id=cuenta_id,
            tipo_evento=TIPO_EVENTO_COBERTURA_CONTINGENCIA,
            actor="ana",
            estado_previo=None,
            estado_nuevo=None,
            datos={"acreditacion_id": acreditacion.id, "sustento": "constancia de la IAFAS"},
        ),
    )
    await _revisar(sesion, registro_id, conforme, cuenta_medica_id=cuenta_id)


async def prueba_la_cobertura_no_conforme_no_sirve_para_facturar(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress, iafas = await _base(sesion)
        no_conforme = (await _crear_cuenta(sesion, ipress, iafas, "1", "REGISTRADA")).cuenta_id
        conforme = (await _crear_cuenta(sesion, ipress, iafas, "2", "REGISTRADA")).cuenta_id
        await _cobertura_manual(sesion, no_conforme, conforme=False)
        await _cobertura_manual(sesion, conforme, conforme=True)

        requisitos = await RepositorioComprobantePagoSql(sesion).requisitos_para_facturar(
            no_conforme
        )
        assert requisitos is not None and _FALTANTE in requisitos.faltantes()
        piezas = await RepositorioCompletitudCuentaSql(sesion).obtener_estado_piezas(no_conforme)
        assert piezas is not None and cobertura(piezas) == (False, "verificar_cobertura")
        assert await RepositorioContingenciaSql(sesion).cobertura_vigente_no_conforme(no_conforme)
        assert not await RepositorioContingenciaSql(sesion).cobertura_vigente_no_conforme(conforme)

        # La salida: una nueva verificacion de cobertura pasa a ser la vigente.
        await _acreditar(sesion, no_conforme)
        requisitos = await RepositorioComprobantePagoSql(sesion).requisitos_para_facturar(
            no_conforme
        )
        assert requisitos is not None and _FALTANTE not in requisitos.faltantes()


@dataclass
class _Acreditaciones:
    tiene_comprobante: bool = False

    async def existe_acreditacion(self, cuenta_medica_id: int) -> bool:
        return True

    async def obtener_contexto_cuenta(self, cuenta_medica_id: int) -> ContextoCuentaAcreditacion:
        return ContextoCuentaAcreditacion(
            cuenta_medica_id=cuenta_medica_id,
            tipo_documento_paciente="1",
            numero_documento_paciente="11111111",
            estado_cuenta="FACTURADA" if self.tiene_comprobante else "REGISTRADA",
            tiene_comprobante=self.tiene_comprobante,
        )


@pytest.mark.parametrize(
    "no_conforme,tiene_comprobante,habilitada",
    [(True, False, True), (True, True, False), (False, False, False)],
)
async def prueba_un_nuevo_registro_en_contingencia_solo_sin_comprobante(
    no_conforme: bool, tiene_comprobante: bool, habilitada: bool
) -> None:
    disponibilidad = ConsultarDisponibilidadContingencia(
        _Contingencia(no_conforme=no_conforme),  # type: ignore[arg-type]
        _Acreditaciones(tiene_comprobante),  # type: ignore[arg-type]
    )
    assert await disponibilidad.cobertura(5) is habilitada


async def prueba_el_lote_con_validacion_no_conforme_deja_de_estar_vigente(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        ipress, iafas = await _base(sesion)
        documento = await _crear_cuenta(sesion, ipress, iafas, "1", "FACTURADA")
        await _acreditar(sesion, documento.cuenta_id)
        lote_id = await _lote(sesion, iafas, [documento], estado="VALIDADO")
        assert documento.cuenta_id in await cuentas_en_lotes_vigentes(sesion)

        registro_id = await _registrar(
            sesion,
            Evento(
                cuenta_medica_id=None,
                lote_id=lote_id,
                tipo_evento=TIPO_EVENTO_VALIDACION_CONTINGENCIA,
                actor="ana",
                estado_previo=None,
                estado_nuevo=None,
                datos={"resultado": "VALIDADO", "sustento": "constancia del validador"},
            ),
        )
        await _revisar(sesion, registro_id, conforme=False, lote_id=lote_id)

        vigencia = await vigencia_de_lote(sesion, lote_id)
        assert vigencia is not None and vigencia.validacion_no_conforme
        with pytest.raises(ErrorLoteDesactualizado, match="no fue conforme"):
            exigir_lote_vigente(vigencia)
        # Sus cuentas quedan libres para un lote nuevo.
        assert documento.cuenta_id not in await cuentas_en_lotes_vigentes(sesion)
        documentos = await RepositorioLoteFacturacionSql(sesion).obtener_documentos_facturados(
            iafas.id, [documento.cuenta_id]
        )
        assert [d.cuenta_medica_id for d in documentos] == [documento.cuenta_id]
