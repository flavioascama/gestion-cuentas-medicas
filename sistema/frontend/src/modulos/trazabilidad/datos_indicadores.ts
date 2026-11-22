import type {
  DistribucionEstado,
  IndicadoresIafas,
  LotesPeriodoEstado,
  TiempoEtapa,
} from "../../api/trazabilidad";
import { resolver_estado } from "../../componentes_base/mapa_estados";
import { formatear_monto, formatear_periodo } from "../../utilidades/formato";
import { etiqueta_periodo, formatear_entero, formatear_porcentaje } from "./formato_indicadores";
import type { FilaGrafico } from "./grafico_barras";
import type { ColumnaApilada, SerieApilada } from "./geometria_columnas";

// Resultado del lote, no su etapa tecnica: siete estados con cinco
// colores de etiqueta no se distinguen apilados (Validado y Aceptado
// comparten el verde de la etiqueta). El orden es el mismo con el que
// se validaron los colores del grafico (tokens.css): no reordenar.
export const SERIES_LOTE: SerieApilada[] = [
  { clave: "aceptado", etiqueta: "Aceptado", tono: "exito" },
  { clave: "en_tramite", etiqueta: "En trámite", tono: "proceso" },
  { clave: "observado", etiqueta: "Observado", tono: "alerta" },
  { clave: "rechazado", etiqueta: "Rechazado", tono: "critico" },
];

const _CATEGORIA_POR_ESTADO: Record<string, string> = {
  ACEPTADO: "aceptado",
  GENERADO: "en_tramite",
  CARGADO_VALIDADOR: "en_tramite",
  VALIDADO: "en_tramite",
  REMITIDO_IAFAS: "en_tramite",
  OBSERVADO_VALIDADOR: "observado",
  RECHAZADO: "rechazado",
};

export function construir_columnas_periodo(filas: LotesPeriodoEstado[]): ColumnaApilada[] {
  const por_periodo = new Map<string, Record<string, number>>();
  for (const fila of filas) {
    const valores = por_periodo.get(fila.periodo) ?? {};
    const categoria = _CATEGORIA_POR_ESTADO[fila.estado] ?? "en_tramite";
    valores[categoria] = (valores[categoria] ?? 0) + fila.cantidad;
    por_periodo.set(fila.periodo, valores);
  }
  return [...por_periodo.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([periodo, valores]) => ({
      clave: periodo,
      etiqueta: formatear_periodo(periodo),
      etiqueta_eje: etiqueta_periodo(periodo),
      valores,
    }));
}

export type MetricaIafas =
  "cuentas" | "monto_registrado" | "cartera_por_cobrar" | "tasa_glosas" | "pct_lotes_observados";

interface DefinicionMetrica {
  etiqueta: string;
  valor: (fila: IndicadoresIafas) => number;
  formatear: (valor: number) => string;
}

export const METRICAS_IAFAS: Record<MetricaIafas, DefinicionMetrica> = {
  cuentas: { etiqueta: "Cuentas", valor: (f) => f.cuentas, formatear: formatear_entero },
  monto_registrado: {
    etiqueta: "Monto registrado",
    valor: (f) => Number(f.monto_registrado),
    formatear: formatear_monto,
  },
  cartera_por_cobrar: {
    etiqueta: "Cartera",
    valor: (f) => Number(f.cartera_por_cobrar),
    formatear: formatear_monto,
  },
  tasa_glosas: { etiqueta: "Glosas", valor: (f) => f.tasa_glosas, formatear: formatear_porcentaje },
  pct_lotes_observados: {
    etiqueta: "Lotes observados",
    valor: (f) => f.pct_lotes_observados,
    formatear: formatear_porcentaje,
  },
};

export function construir_filas_iafas(
  filas: IndicadoresIafas[],
  metrica: MetricaIafas,
): FilaGrafico[] {
  const definicion = METRICAS_IAFAS[metrica];
  return [...filas]
    .sort((a, b) => definicion.valor(b) - definicion.valor(a))
    .map((fila) => ({
      clave: fila.iafas_codigo,
      etiqueta: fila.iafas_razon_social,
      valor: definicion.valor(fila),
      tono: "primario",
      detalle: `Código ${fila.iafas_codigo}`,
    }));
}

// La etapa con mayor promedio es el cuello de botella: es la unica que
// se resalta (enfasis), las demas quedan en el color base.
export function construir_filas_etapas(filas: TiempoEtapa[]): FilaGrafico[] {
  return [...filas]
    .sort((a, b) => b.promedio_horas - a.promedio_horas)
    .map((fila, indice) => ({
      clave: fila.etapa,
      etiqueta: resolver_estado(fila.etapa).texto,
      valor: fila.promedio_horas,
      tono: indice === 0 && fila.promedio_horas > 0 ? "ambar" : "primario",
      detalle: `${formatear_entero(fila.transiciones)} transiciones`,
    }));
}

export function construir_filas_estados(filas: DistribucionEstado[]): FilaGrafico[] {
  const total = filas.reduce((suma, fila) => suma + fila.cantidad, 0);
  return [...filas]
    .sort((a, b) => b.cantidad - a.cantidad)
    .map((fila) => ({
      clave: fila.estado,
      etiqueta: resolver_estado(fila.estado).texto,
      valor: fila.cantidad,
      tono: resolver_estado(fila.estado).color,
      detalle: total > 0 ? formatear_porcentaje(fila.cantidad / total) : undefined,
    }));
}
