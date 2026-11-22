import type { Expediente } from "../../api/trazabilidad";
import { formatear_fecha, formatear_fecha_hora } from "../../utilidades/formato";
import { nombre_actor, nombre_estado_evento, nombre_evento } from "./nombres_eventos";

// CU-16: el expediente de auditoria como documento. Se arma con lo que
// devuelve el servidor y se abre en un marco propio con su hoja de
// impresion: el navegador lo imprime o lo guarda como PDF.

export interface DatosExpediente {
  expediente: Expediente;
  cuenta: string;
  ipress: string | null;
  exportado_por: string;
  motivo: string;
}

const _DOCUMENTOS: Record<string, string> = {
  ACREDITACION: "Acreditación de la cobertura",
  COMPROBANTE_PAGO: "Comprobante de pago",
};

const _ESTILOS = `
@page { size: A4; margin: 16mm; }
body { font-family: Arial, Helvetica, sans-serif; font-size: 11px; color: #111; margin: 0; }
h1 { font-size: 16px; margin: 0 0 4px; }
h2 { font-size: 13px; margin: 18px 0 6px; }
.subtitulo { margin: 0 0 12px; color: #444; }
dl { display: grid; grid-template-columns: max-content 1fr; gap: 3px 12px; margin: 0; }
dt { font-weight: bold; }
dd { margin: 0; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid #999; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #eee; }
thead { display: table-header-group; }
tr { page-break-inside: avoid; }
`;

function escapar(texto: string): string {
  return texto
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function filas_eventos(expediente: Expediente): string {
  return expediente.historial.eventos
    .map(
      (evento) =>
        `<tr><td>${escapar(formatear_fecha_hora(evento.ocurrido_en))}</td>` +
        `<td>${escapar(nombre_evento(evento.tipo_evento))}</td>` +
        `<td>${escapar(nombre_estado_evento(evento.estado_previo))}</td>` +
        `<td>${escapar(nombre_estado_evento(evento.estado_nuevo))}</td>` +
        `<td>${escapar(nombre_actor(evento.actor))}</td></tr>`,
    )
    .join("");
}

function fecha_documento(documento: Expediente["documentos"][number]): string {
  if (documento.emitido_en) return formatear_fecha_hora(documento.emitido_en);
  if (documento.fecha_emision) return formatear_fecha(documento.fecha_emision);
  return "—";
}

function filas_documentos(expediente: Expediente): string {
  if (expediente.documentos.length === 0) return `<tr><td colspan="3">Ninguno</td></tr>`;
  return expediente.documentos
    .map(
      (documento) =>
        `<tr><td>${escapar(_DOCUMENTOS[documento.tipo] ?? documento.tipo)}</td>` +
        `<td>${escapar(documento.referencia)}</td>` +
        `<td>${escapar(fecha_documento(documento))}</td></tr>`,
    )
    .join("");
}

export function html_expediente(datos: DatosExpediente): string {
  const { expediente } = datos;
  const titulo = `Expediente de auditoría ${datos.cuenta}`;
  return `<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>${escapar(titulo)}</title><style>${_ESTILOS}</style></head><body>
<h1>Expediente de auditoría de la cuenta médica</h1>
<p class="subtitulo">Clínica${datos.ipress ? ` · IPRESS ${escapar(datos.ipress)}` : ""}</p>
<dl>
<dt>Cuenta</dt><dd>${escapar(datos.cuenta)}</dd>
<dt>Generado</dt><dd>${escapar(formatear_fecha_hora(expediente.generado_en))}</dd>
<dt>Exportado por</dt><dd>${escapar(datos.exportado_por)}</dd>
<dt>Motivo</dt><dd>${escapar(datos.motivo)}</dd>
</dl>
<h2>Historial de eventos</h2>
<table><thead><tr><th>Fecha y hora</th><th>Acción</th><th>Estado previo</th><th>Estado nuevo</th><th>Actor</th></tr></thead>
<tbody>${filas_eventos(expediente)}</tbody></table>
<h2>Documentos asociados</h2>
<table><thead><tr><th>Documento</th><th>Referencia</th><th>Fecha</th></tr></thead>
<tbody>${filas_documentos(expediente)}</tbody></table>
</body></html>`;
}

const _ID_MARCO = "marco_expediente_auditoria";

// Un marco oculto por vez: el anterior se quita al abrir otro.
export function abrir_expediente(html: string): void {
  document.getElementById(_ID_MARCO)?.remove();
  const marco = document.createElement("iframe");
  marco.id = _ID_MARCO;
  marco.title = "Expediente de auditoría";
  marco.style.position = "fixed";
  marco.style.width = "0";
  marco.style.height = "0";
  marco.style.border = "0";
  marco.onload = () => {
    marco.contentWindow?.focus();
    marco.contentWindow?.print();
  };
  marco.srcdoc = html;
  document.body.appendChild(marco);
}
