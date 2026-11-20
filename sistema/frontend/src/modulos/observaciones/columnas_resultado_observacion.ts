import type { CargaSesion } from "../../api/auth";
import type { Observacion } from "../../api/observaciones";
import type { ColumnaTabla } from "../../componentes_base/tabla_datos";
import { formatear_fecha, formatear_fecha_hora, formatear_monto } from "../../utilidades/formato";

// Cuanto se observo, en que termino y si la respuesta llego a la IAFAS
// (2026-11-19).

const _ETIQUETA_RESULTADO: Record<string, string> = {
  LEVANTADA: "Levantada",
  MANTENIDA: "Mantenida",
};

function texto_resultado(fila: Observacion): string {
  if (!fila.resultado) return "—";
  const etiqueta = _ETIQUETA_RESULTADO[fila.resultado] ?? fila.resultado;
  return fila.resultado_en ? `${etiqueta} ${formatear_fecha(fila.resultado_en)}` : etiqueta;
}

function texto_entrega(fila: Observacion): string {
  if (fila.entrega_estado === "PENDIENTE") return "Pendiente";
  if (fila.entrega_estado === "NO_ENTREGADA") return "No entregada";
  if (fila.entrega_estado !== "ENTREGADA") return "—";
  return fila.entrega_en ? `Entregada ${formatear_fecha_hora(fila.entrega_en)}` : "Entregada";
}

export const COLUMNAS_RESULTADO: ColumnaTabla<Observacion>[] = [
  {
    clave: "monto_observado",
    encabezado: "Monto observado",
    alinear_derecha: true,
    formatear: (fila) =>
      fila.monto_observado != null ? formatear_monto(fila.monto_observado) : "—",
  },
  { clave: "resultado", encabezado: "Resultado", formatear: texto_resultado },
  { clave: "entrega_estado", encabezado: "Entrega", formatear: texto_entrega },
];

// La pide de nuevo quien respondio o el analista, si no llego.
export function puede_pedir_entrega(observacion: Observacion, sesion: CargaSesion): boolean {
  if (observacion.entrega_estado !== "NO_ENTREGADA") return false;
  return (
    sesion.roles.includes("analista") ||
    sesion.nombre_usuario === observacion.entrega_solicitada_por
  );
}
