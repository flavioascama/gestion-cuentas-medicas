"""Pruebas de la custodia de datos (C-04, C-05, C-12, RNF-15, RNF-16): TLS
exigido fuera de desarrollo, columnas sensibles cifradas con indice ciego,
retencion de evidencias y proyeccion del ciclo derivada de los eventos."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.compartido.configuracion import Configuracion
from app.dominio.puertos_comunes import Evento
from app.infraestructura.persistencia.cifrado_columnas import (
    cifrar_texto,
    descifrar_texto,
    indice_ciego,
)
from app.infraestructura.persistencia.modelos_integracion import AseguradoModelo
from app.infraestructura.persistencia.proyeccion_ciclo import (
    ProyeccionCicloCuentaModelo,
    reconstruir_proyecciones,
)
from app.infraestructura.persistencia.registro_eventos_sql import RegistroEventosSql
from herramientas.purgar_evidencias import purgar
from pruebas.prueba_repositorio_plazos import _sembrar_cuenta, _sembrar_iafas

_URLS_TLS = {
    "ACREDITA_SALUD_URL_BASE": "https://acredita.example",
    "TEDEF_WEB_URL_BASE": "https://tedef.example",
    "PSE_URL_BASE": "https://pse.example",
    "SISTEMA_HOSPITALARIO_URL_BASE": "https://hospitalario.example",
    "RECEPTOR_IAFAS_URL_BASE": "https://receptor.example",
}


def prueba_fuera_de_desarrollo_no_arranca_sin_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTORNO", "produccion")
    monkeypatch.setenv("ACREDITA_SALUD_URL_BASE", "http://acredita.example")
    with pytest.raises(ValidationError, match="sin TLS"):
        Configuracion()


def prueba_fuera_de_desarrollo_arranca_con_todo_cifrado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTORNO", "produccion")
    for clave, valor in _URLS_TLS.items():
        monkeypatch.setenv(clave, valor)
    url = os.environ["URL_BASE_DATOS"].split("?")[0] + "?ssl=require"
    monkeypatch.setenv("URL_BASE_DATOS", url)
    assert Configuracion().entorno == "produccion"


def prueba_desarrollo_admite_los_simuladores_sin_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTORNO", "desarrollo")
    monkeypatch.setenv("ACREDITA_SALUD_URL_BASE", "http://acredita-salud:8000")
    assert Configuracion().entorno == "desarrollo"


def prueba_cifrado_de_texto_e_indice_ciego() -> None:
    cifrado = cifrar_texto("45127896")
    assert cifrado != "45127896" and cifrado != cifrar_texto("45127896")
    assert descifrar_texto(cifrado) == "45127896"
    assert indice_ciego("1", "45127896") == indice_ciego("1", "45127896")
    assert indice_ciego("1", "45127896") != indice_ciego("4", "45127896")


async def prueba_el_asegurado_se_guarda_cifrado_y_se_busca_por_indice(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        asegurado = AseguradoModelo(
            tipo_documento="1",
            numero_documento="70112233",
            nombres="Rosa",
            apellidos="Quispe Mamani",
            iafas_id=iafas_id,
            ficticio=True,
        )
        sesion.add(asegurado)
        await sesion.commit()

        crudo = (
            await sesion.execute(
                sa.text("SELECT nombres, numero_documento FROM asegurado WHERE id = :id"),
                {"id": asegurado.id},
            )
        ).one()
        assert "Rosa" not in crudo[0] and crudo[1] != "70112233"

        encontrado = await sesion.scalar(
            sa.select(AseguradoModelo).where(
                AseguradoModelo.documento_indice == indice_ciego("1", "70112233")
            )
        )
        assert encontrado is not None and encontrado.nombres == "Rosa"


def prueba_la_retencion_borra_solo_las_evidencias_vencidas(tmp_path: Path) -> None:
    carpeta = tmp_path / "evidencia_acreditacion"
    vieja, nueva = carpeta / "10", carpeta / "11"
    for directorio in (vieja, nueva):
        directorio.mkdir(parents=True)
        (directorio / "documento.png.cifrado").write_bytes(b"x")
    hace_tres_anios = time.time() - 3 * 365 * 86400
    os.utime(vieja, (hace_tres_anios, hace_tres_anios))

    assert purgar(tmp_path, 730, datetime.now(UTC)) == ["10"]
    assert not vieja.exists() and nueva.exists()


async def prueba_la_proyeccion_se_reconstruye_igual_desde_el_almacen(
    fabrica_sesiones: async_sessionmaker[AsyncSession],
) -> None:
    async with fabrica_sesiones() as sesion:
        iafas_id = await _sembrar_iafas(
            sesion,
            dias_plazo_respuesta_observacion=7,
            dias_plazo_comunicacion_auditoria=30,
            dias_plazo_pago_liquidacion=30,
        )
        cuenta_id = await _sembrar_cuenta(sesion, iafas_id, "FACTURADA")
        registro = RegistroEventosSql(sesion)
        for tipo, previo, nuevo in (
            ("REGISTRO", None, "REGISTRADA"),
            ("FACTURACION", "REGISTRADA", "FACTURADA"),
        ):
            await registro.registrar(
                Evento(
                    cuenta_medica_id=cuenta_id,
                    tipo_evento=tipo,
                    actor="prueba",
                    estado_previo=previo,
                    estado_nuevo=nuevo,
                )
            )
        al_registrar = await sesion.get(ProyeccionCicloCuentaModelo, cuenta_id)
        assert al_registrar is not None
        assert (al_registrar.estado, al_registrar.version_evento) == ("FACTURADA", 2)
        assert al_registrar.tiempos["FACTURADA"][1] == 1

        await reconstruir_proyecciones(sesion, [cuenta_id])
        reconstruida = await sesion.get(ProyeccionCicloCuentaModelo, cuenta_id)
        assert reconstruida is not None
        assert reconstruida.estado == "FACTURADA"
        assert reconstruida.tiempos.keys() == {"FACTURADA"}
        assert reconstruida.primer_cambio_en is not None
        assert reconstruida.ultimo_cambio_en - reconstruida.primer_cambio_en < timedelta(minutes=1)
