import type { ComunicacionIafas } from "../../api/comunicaciones_iafas";
import type { ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";

// Lo que la IAFAS comunico por su portal o por correo, como lo registro
// el robot de comunicaciones.

export const TIPOS_COMUNICACION: Record<string, string> = {
  AUDITORIA_CONFORME: "Conformidad de auditoría",
  OBSERVACION: "Observación",
  LIQUIDACION: "Liquidación",
  PAGO: "Aviso de pago",
};

export const CANALES_COMUNICACION: Record<string, string> = {
  PORTAL: "Portal de la IAFAS",
  CORREO: "Correo electrónico",
};

function valor(datos: Record<string, unknown>, clave: string): string | null {
  const dato = datos[clave];
  if (typeof dato === "string" && dato) return dato;
  return typeof dato === "number" ? String(dato) : null;
}

function contenido(fila: ComunicacionIafas): string {
  const datos = fila.datos;
  if (fila.tipo === "OBSERVACION") {
    const motivo = valor(datos, "motivo_codigo") ?? "—";
    const glosado = valor(datos, "monto_glosado");
    const alcance = datos.es_parcial === true ? "parcial" : "total";
    return `Motivo ${motivo} (${alcance})${glosado ? `, glosado ${formatear_monto(glosado)}` : ""}`;
  }
  const monto = valor(datos, fila.tipo === "PAGO" ? "monto_pagado" : "monto_liquidado");
  return monto ? formatear_monto(monto) : "—";
}

function resultado(fila: ComunicacionIafas): string {
  if (fila.resultado === "APLICADA") return "Aplicada";
  return fila.detalle ? `No aplicada: ${fila.detalle}` : "No aplicada";
}

export const COLUMNAS_COMUNICACIONES: ColumnaTabla<ComunicacionIafas>[] = [
  { clave: "codigo", encabezado: "Código" },
  {
    clave: "tipo",
    encabezado: "Comunicación",
    formatear: (fila) => TIPOS_COMUNICACION[fila.tipo] ?? fila.tipo,
  },
  {
    clave: "canal",
    encabezado: "Canal",
    formatear: (fila) => CANALES_COMUNICACION[fila.canal] ?? fila.canal,
  },
  { clave: "datos", encabezado: "Contenido", formatear: contenido },
  {
    clave: "recibida_en",
    encabezado: "Recibida",
    formatear: (fila) => formatear_fecha_hora(fila.recibida_en),
  },
  { clave: "resultado", encabezado: "Registro", formatear: resultado },
  {
    clave: "respuesta_remitida_en",
    encabezado: "Respuesta entregada",
    formatear: (fila) =>
      fila.respuesta_remitida_en ? formatear_fecha_hora(fila.respuesta_remitida_en) : "—",
  },
];
