import { usar_sesion } from "../../sesion/contexto_sesion";

// Estados en que se codifica (Tabla 69: nada despues de CERRADA o ANULADA):
// antes de facturar, al corregir una cuenta rechazada y al refacturar por
// una glosa tecnica. El backend aplica la misma regla.
const _ESTADOS_CODIFICABLES = new Set(["REGISTRADA", "RECHAZADA", "GLOSADA", "GLOSADA_PARCIAL"]);

// Codificar los procedimientos es tarea del auditor medico (tabla de actores
// de la tesis): el analista ve los procedimientos, no los agrega.
export function usar_puede_codificar(estado: string): boolean {
  const { sesion } = usar_sesion();
  return Boolean(sesion?.roles.includes("auditor")) && _ESTADOS_CODIFICABLES.has(estado);
}
