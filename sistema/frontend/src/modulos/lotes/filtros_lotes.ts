// Filtros de la bandeja de lotes: valores, opciones y conversiones del
// periodo. Separado del componente para que este solo exporte componentes.

export interface Filtros {
  periodo: string;
  estado: string;
  iafas_id: string;
}

export const FILTROS_VACIOS: Filtros = { periodo: "", estado: "", iafas_id: "" };

export function hay_filtros_aplicados(filtros: Filtros, busqueda: string): boolean {
  return [busqueda, filtros.periodo, filtros.estado, filtros.iafas_id].some(Boolean);
}

export const OPCIONES_ESTADO_LOTE = [
  { valor: "", etiqueta: "Todos" },
  { valor: "GENERADO", etiqueta: "Generado" },
  { valor: "CARGADO_VALIDADOR", etiqueta: "Cargado en el validador" },
  { valor: "OBSERVADO_VALIDADOR", etiqueta: "Observado por el validador" },
  { valor: "VALIDADO", etiqueta: "Validado" },
  { valor: "REMITIDO_IAFAS", etiqueta: "Remitido a la IAFAS" },
  { valor: "ACEPTADO", etiqueta: "Aceptado" },
  { valor: "RECHAZADO", etiqueta: "Rechazado" },
];

// AAAAMM (formato que ya entiende el backend) <-> AAAA-MM (formato que
// exige <input type="month">).
export function formatear_periodo_legible(periodo: string): string {
  if (periodo.length !== 6) return "";
  return `${periodo.slice(0, 4)}-${periodo.slice(4, 6)}`;
}

export function periodo_desde_mes_input(valor: string): string {
  return valor.replace("-", "");
}
