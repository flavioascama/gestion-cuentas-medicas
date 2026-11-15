"""Documento 'Solicitud de Atencion Medica' (Seccion 9.1: 'emision e
impresion/reimpresion del documento... que sustenta la prestacion').
Genera un PDF real con fpdf2 -- la pantalla HTML (plantillas/documento.html)
cubre la impresion desde el navegador; este modulo cubre la descarga en
PDF explicita que pide la Seccion 9.1 para el historial."""

from __future__ import annotations

from fpdf import FPDF

from app.almacenamiento import Acreditacion
from app.datos import RepositorioDatos


def generar_pdf_solicitud(
    acreditacion: Acreditacion, repositorio: RepositorioDatos, reimpresion: bool
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(150, 100, 0)
    pdf.cell(0, 6, "ENTORNO DE SIMULACION. NO CORRESPONDE A UN SISTEMA OFICIAL.", align="C")
    pdf.ln(10)

    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "SOLICITUD DE ATENCION MEDICA", align="C")
    pdf.ln(8)
    if reimpresion:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(180, 0, 0)
        pdf.cell(0, 8, "REIMPRESION", align="C")
        pdf.ln(10)
        pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "", 11)
    filas = [
        ("Codigo de autorizacion", acreditacion.codigo_autorizacion),
        (
            "Documento del asegurado",
            f"{acreditacion.tipo_documento} {acreditacion.numero_documento}",
        ),
        ("Nombre del asegurado", acreditacion.nombre_asegurado),
        ("IAFAS", repositorio.nombre_iafas(acreditacion.iafas_codigo)),
        ("Condicion de cobertura", acreditacion.condicion_cobertura),
        ("Tipo de copago", acreditacion.tipo_copago or "Sin copago"),
    ]
    if acreditacion.monto_copago_fijo is not None:
        filas.append(("Monto de copago fijo", f"S/ {acreditacion.monto_copago_fijo:.2f}"))
    if acreditacion.porcentaje_coaseguro is not None:
        filas.append(("Porcentaje de coaseguro", f"{acreditacion.porcentaje_coaseguro}%"))
    filas.append(("Generado el", acreditacion.generado_en))

    for etiqueta, valor in filas:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(60, 8, f"{etiqueta}:")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 8, str(valor))
        pdf.ln(8)

    salida = pdf.output()
    return bytes(salida)
