"""Nueva consulta de la cobertura: se admite mientras la cuenta esta
REGISTRADA y sin comprobante; la respuesta nueva es la vigente (la mas
reciente) y la anterior se conserva. Tambien la aseguradora distinta."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.dominio.acreditacion.casos_uso import (
    ErrorCuentaYaAcreditada,
    ObtenerAcreditacion,
    SolicitarVerificacionCobertura,
)
from app.dominio.acreditacion.valores import (
    ContextoCuentaAcreditacion,
    ResultadoAcreditacion,
    admite_consulta,
    condicion_segun_aseguradora,
    es_acreditable,
)
from app.infraestructura.persistencia.modelos_integracion import (
    AcreditacionModelo,
    AseguradoModelo,
    CuentaMedicaModelo,
    DocumentoFacturadorModelo,
    IafasModelo,
    IpressModelo,
)
from app.infraestructura.persistencia.repositorio_acreditacion_sql import (
    RepositorioAcreditacionSql,
)

_RESULTADO = ResultadoAcreditacion(
    condicion_cobertura="ACREDITABLE",
    codigo_autorizacion="AUT0000001",
    tipo_documento_autorizacion="01",
    codigo_asegurado="00012-81953443",
    tipo_afiliacion="1",
    plan="PLAN A",
    vigente_desde=None,
    vigente_hasta=None,
    tipo_copago=None,
    monto_copago_fijo=None,
    porcentaje_coaseguro=None,
)
_INSTANTE = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)


class _Reloj:
    def ahora(self) -> datetime:
        return _INSTANTE


class _Trabajos:
    def __init__(self) -> None:
        self.encolados = 0

    async def encolar(
        self, tipo: str, carga_util: dict[str, object], proximo_intento: datetime
    ) -> int:
        self.encolados += 1
        return self.encolados


async def _sembrar_cuenta(sesion: AsyncSession, estado: str = "REGISTRADA") -> CuentaMedicaModelo:
    iafas = IafasModelo(
        codigo="00012",
        razon_social="IAFAS",
        periodicidad_remision_dias=7,
        ventana_monitoreo_horas=48,
    )
    ipress = IpressModelo(ruc="20123456789", codigo_ipress="12345678", razon_social="Clinica")
    sesion.add_all([iafas, ipress])
    await sesion.flush()
    asegurado = AseguradoModelo(
        tipo_documento="1",
        numero_documento="81953443",
        nombres="Elvira",
        apellidos="Ochoa",
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
        hora_prestacion=time(9, 0),
        numero_historia_clinica="00000001",
        estado=estado,
    )
    sesion.add(cuenta)
    await sesion.commit()
    return cuenta


async def _guardar(repositorio: RepositorioAcreditacionSql, cuenta_id: int, codigo: str) -> int:
    return await repositorio.guardar_acreditacion(
        cuenta_medica_id=cuenta_id,
        resultado=replace(_RESULTADO, codigo_autorizacion=codigo),
        instante=_INSTANTE,
        duracion_ms=0,
        componente_ejecutor="robot_acreditacion_playwright",
    )


async def prueba_la_vigente_es_la_ultima_y_la_anterior_se_conserva(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta = await _sembrar_cuenta(sesion)
        repositorio = RepositorioAcreditacionSql(sesion)
        await _guardar(repositorio, cuenta.id, "AUT0000001")
        segunda = await _guardar(repositorio, cuenta.id, "AUT0000002")

        vigente = await repositorio.obtener_acreditacion(cuenta.id)
        assert vigente is not None
        assert (vigente.id, vigente.resultado.codigo_autorizacion) == (segunda, "AUT0000002")
        total = await sesion.scalar(sa.select(sa.func.count()).select_from(AcreditacionModelo))
        assert total == 2

    async with fabrica_sesiones() as sesion:
        # La relacion que usan el lote y los montos tambien da la vigente.
        cargada = (
            await sesion.execute(
                sa.select(CuentaMedicaModelo).options(selectinload(CuentaMedicaModelo.acreditacion))
            )
        ).scalar_one()
        assert cargada.acreditacion is not None
        assert cargada.acreditacion.codigo_autorizacion == "AUT0000002"


async def prueba_contexto_trae_iafas_estado_y_comprobante(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta = await _sembrar_cuenta(sesion)
        repositorio = RepositorioAcreditacionSql(sesion)
        contexto = await repositorio.obtener_contexto_cuenta(cuenta.id)
        assert contexto is not None
        assert (contexto.codigo_iafas, contexto.estado_cuenta) == ("00012", "REGISTRADA")
        assert contexto.tiene_comprobante is False

        sesion.add(
            DocumentoFacturadorModelo(
                cuenta_id=cuenta.id,
                ipress_id=cuenta.ipress_id,
                tipo_documento_pago="01",
                serie="F001",
                numero="00000001",
                fecha_emision=date(2026, 11, 19),
            )
        )
        await sesion.commit()
        contexto = await repositorio.obtener_contexto_cuenta(cuenta.id)
        assert contexto is not None and contexto.tiene_comprobante is True


async def prueba_reconsulta_admitida_y_bloqueada_con_comprobante(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        cuenta = await _sembrar_cuenta(sesion)
        repositorio = RepositorioAcreditacionSql(sesion)
        await _guardar(repositorio, cuenta.id, "AUT0000001")
        trabajos = _Trabajos()
        solicitar = SolicitarVerificacionCobertura(repositorio, trabajos, _Reloj())  # type: ignore[arg-type]

        assert await solicitar.ejecutar(cuenta.id, "ana.analista") == 1
        vigente = await ObtenerAcreditacion(repositorio).ejecutar(cuenta.id)
        assert vigente is not None and vigente.admite_reconsulta is True

        sesion.add(
            DocumentoFacturadorModelo(
                cuenta_id=cuenta.id,
                ipress_id=cuenta.ipress_id,
                tipo_documento_pago="01",
                serie="F001",
                numero="00000001",
                fecha_emision=date(2026, 11, 19),
            )
        )
        await sesion.commit()
        with pytest.raises(ErrorCuentaYaAcreditada):
            await solicitar.ejecutar(cuenta.id, "ana.analista")
        vigente = await ObtenerAcreditacion(repositorio).ejecutar(cuenta.id)
        assert vigente is not None and vigente.admite_reconsulta is False


@pytest.mark.parametrize(
    ("estado", "comprobante", "ya_acreditada", "esperado"),
    [
        ("REGISTRADA", False, False, True),
        ("REGISTRADA", False, True, True),
        ("REGISTRADA", True, True, False),
        ("FACTURADA", False, True, False),
        ("FACTURADA", True, False, True),  # la primera consulta siempre
    ],
)
def prueba_admite_consulta(
    estado: str, comprobante: bool, ya_acreditada: bool, esperado: bool
) -> None:
    contexto = ContextoCuentaAcreditacion(
        cuenta_medica_id=1,
        tipo_documento_paciente="1",
        numero_documento_paciente="1",
        estado_cuenta=estado,
        tiene_comprobante=comprobante,
    )
    assert admite_consulta(contexto, ya_acreditada) is esperado


def prueba_aseguradora_distinta_no_es_acreditable() -> None:
    condicion = condicion_segun_aseguradora(
        "ACREDITABLE", "00012", "99553", "IAFAS Otra (ficticia)"
    )
    assert (
        condicion
        == "NO ACREDITABLE: el asegurado figura en otra aseguradora (IAFAS Otra (ficticia))"
    )
    assert not es_acreditable(condicion)


def prueba_misma_aseguradora_conserva_la_condicion() -> None:
    assert condicion_segun_aseguradora("ACREDITABLE CON RESTRICCIÓN: x", "00012", "00012", "A") == (
        "ACREDITABLE CON RESTRICCIÓN: x"
    )
    # Sin IAFAS en la cuenta o en la respuesta no hay con que comparar.
    assert condicion_segun_aseguradora("ACREDITABLE", "", "99553", "A") == "ACREDITABLE"
