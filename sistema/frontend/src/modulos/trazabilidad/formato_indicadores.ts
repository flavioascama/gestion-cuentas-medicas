// Formatos propios del panel gerencial; los generales de la aplicacion
// (montos, fechas) siguen en utilidades/formato.ts.

const _MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"];

export function formatear_porcentaje(fraccion: number): string {
  return `${(fraccion * 100).toFixed(1)}%`;
}

export function formatear_entero(valor: number): string {
  return new Intl.NumberFormat("es-PE").format(valor);
}

// "202609" -> "Set 2026": gerencia lee meses, no el codigo AAAAMM que
// usa la trama TEDEF.
export function etiqueta_periodo(periodo: string): string {
  const mes = Number(periodo.slice(4, 6));
  if (periodo.length !== 6 || mes < 1 || mes > 12) return periodo;
  return `${_MESES[mes - 1]} ${periodo.slice(0, 4)}`;
}

// Las duraciones reales van de segundos a dias: con una unidad fija
// ("h") casi todas las etapas se mostraban como "0.0 h".
export function formatear_horas(horas: number): string {
  const segundos = horas * 3600;
  if (segundos < 60) return `${Math.round(segundos)} s`;
  if (segundos < 3600) return `${Math.round(segundos / 60)} min`;
  if (horas < 48) return `${horas.toFixed(1)} h`;
  return `${(horas / 24).toFixed(1)} días`;
}

// AAAAMM (backend) <-> AAAA-MM (<input type="month">).
export function periodo_a_mes_input(periodo: string): string {
  if (periodo.length !== 6) return "";
  return `${periodo.slice(0, 4)}-${periodo.slice(4, 6)}`;
}

export function mes_input_a_periodo(valor: string): string {
  return valor.replace("-", "");
}
