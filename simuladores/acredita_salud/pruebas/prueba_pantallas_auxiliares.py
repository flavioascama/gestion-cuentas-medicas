"""Pruebas de las pantallas auxiliares del alcance (Seccion 9.1): atencion
accidental, derivacion entre IPRESS, cartas de garantia, historial (con
exportacion a Excel) y carga masiva."""

from __future__ import annotations

import io

import openpyxl
from httpx import AsyncClient


async def prueba_registra_declaracion_de_siniestro(cliente_autenticado: AsyncClient) -> None:
    respuesta = await cliente_autenticado.post(
        "/atencion-accidental",
        data={
            "tipo_documento": "1",
            "numero_documento": "11111111",
            "fecha_siniestro": "2026-03-01",
            "descripcion": "Caida en la via publica",
        },
    )
    assert respuesta.status_code == 200
    assert "siniestro-registrado" in respuesta.text


async def prueba_registra_derivacion_entre_ipress(cliente_autenticado: AsyncClient) -> None:
    respuesta = await cliente_autenticado.post(
        "/derivacion",
        data={
            "tipo_documento": "1",
            "numero_documento": "11111111",
            "ipress_origen": "11111111",
            "ipress_destino": "22222222",
            "motivo": "Mayor capacidad resolutiva",
        },
    )
    assert respuesta.status_code == 200
    assert "derivacion-registrada" in respuesta.text


async def prueba_derivacion_para_asegurado_inexistente_muestra_error(
    cliente_autenticado: AsyncClient,
) -> None:
    respuesta = await cliente_autenticado.post(
        "/derivacion",
        data={
            "tipo_documento": "1",
            "numero_documento": "99999999",
            "ipress_origen": "11111111",
            "ipress_destino": "22222222",
            "motivo": "x",
        },
    )
    assert "error-derivacion" in respuesta.text


async def prueba_busca_cartas_de_garantia_sembradas_al_iniciar(
    cliente_autenticado: AsyncClient,
) -> None:
    respuesta = await cliente_autenticado.get("/cartas-garantia")
    assert respuesta.status_code == 200
    assert "fila-carta-garantia" in respuesta.text


async def prueba_historial_y_exportacion_excel_reflejan_lo_generado(
    cliente_autenticado: AsyncClient,
) -> None:
    await cliente_autenticado.post(
        "/acreditacion/generar", data={"tipo_documento": "1", "numero_documento": "33333333"}
    )

    historial = await cliente_autenticado.get("/historial")
    assert "AUT0000001" in historial.text

    excel = await cliente_autenticado.get("/historial/exportar.xlsx")
    assert excel.status_code == 200
    libro = openpyxl.load_workbook(io.BytesIO(excel.content))
    hoja = libro.active
    assert hoja is not None
    filas = list(hoja.iter_rows(values_only=True))
    assert filas[0][0] == "Codigo de autorizacion"
    assert any(fila[0] == "AUT0000001" for fila in filas[1:])


async def prueba_carga_masiva_procesa_un_archivo_xlsx(cliente_autenticado: AsyncClient) -> None:
    import openpyxl as ox

    libro = ox.Workbook()
    hoja = libro.active
    assert hoja is not None
    hoja.append(["tipo_documento", "numero_documento"])
    hoja.append(["1", "11111111"])
    hoja.append(["1", "99999999"])  # no existe
    buffer = io.BytesIO()
    libro.save(buffer)

    respuesta = await cliente_autenticado.post(
        "/carga-masiva",
        files={
            "archivo": (
                "documentos.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert respuesta.status_code == 200
    assert "Acreditado" in respuesta.text
    assert "No encontrado" in respuesta.text
