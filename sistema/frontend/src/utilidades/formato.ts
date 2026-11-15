// Formatos unicos de la aplicacion (GUIA_DISENO_INTERFAZ.md, Seccion 5:
// "fechas dd/mm/aaaa y horas HH:MM:SS, montos 'S/ 1 250.00'").

export function formatear_fecha(iso: string): string {
  // Una fecha sin hora ("2026-11-13") es un dia calendario: new Date() la
  // tomaria como medianoche UTC y en Lima la mostraria un dia antes.
  const solo_fecha = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (solo_fecha) return `${solo_fecha[3]}/${solo_fecha[2]}/${solo_fecha[1]}`;
  const fecha = new Date(iso);
  const dia = String(fecha.getDate()).padStart(2, "0");
  const mes = String(fecha.getMonth() + 1).padStart(2, "0");
  return `${dia}/${mes}/${fecha.getFullYear()}`;
}

export function formatear_fecha_hora(iso: string): string {
  const fecha = new Date(iso);
  const horas = String(fecha.getHours()).padStart(2, "0");
  const minutos = String(fecha.getMinutes()).padStart(2, "0");
  const segundos = String(fecha.getSeconds()).padStart(2, "0");
  return `${formatear_fecha(iso)} ${horas}:${minutos}:${segundos}`;
}

export function formatear_monto(valor: number | string): string {
  const numero = typeof valor === "string" ? Number(valor) : valor;
  const formateado = new Intl.NumberFormat("es-PE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numero);
  return `S/ ${formateado}`;
}

export function formatear_duracion(segundos_totales: number): string {
  const segundos = Math.max(0, Math.floor(segundos_totales));
  const horas = String(Math.floor(segundos / 3600)).padStart(2, "0");
  const minutos = String(Math.floor((segundos % 3600) / 60)).padStart(2, "0");
  const resto_segundos = String(segundos % 60).padStart(2, "0");
  return `${horas}:${minutos}:${resto_segundos}`;
}

// "hace 5 min", "hace 3 h", "hace 2 días": cuando ocurrio un aviso, sin
// obligar a leer una fecha completa; para mas de una semana, la fecha.
export function formatear_hace(iso: string, ahora: number = Date.now()): string {
  const segundos = Math.max(0, Math.round((ahora - new Date(iso).getTime()) / 1000));
  if (segundos < 60) return "hace un momento";
  const minutos = Math.round(segundos / 60);
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.round(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.round(horas / 24);
  if (dias <= 7) return dias === 1 ? "hace 1 día" : `hace ${dias} días`;
  return formatear_fecha(iso);
}
