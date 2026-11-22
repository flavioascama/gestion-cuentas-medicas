import { usar_sesion } from "../../sesion/contexto_sesion";
import { usar_en_correccion_validador } from "./usar_cuentas";

// Estados en que se codifica (Tabla 69: nada despues de CERRADA o ANULADA):
// antes de facturar, al corregir una cuenta rechazada y al refacturar por
// una glosa tecnica; tambien si el validador observo su lote. El backend
// aplica la misma regla.
const _ESTADOS_CODIFICABLES = new Set(["REGISTRADA", "RECHAZADA", "GLOSADA"]);

// Codificar los procedimientos es tarea del auditor medico (tabla de actores
// de la tesis): el analista ve los procedimientos, no los agrega.
export function usar_puede_codificar(estado: string, cuenta_id: number): boolean {
  const { sesion } = usar_sesion();
  const en_correccion = usar_en_correccion_validador(cuenta_id);
  const estado_admitido = _ESTADOS_CODIFICABLES.has(estado) || en_correccion;
  return Boolean(sesion?.roles.includes("auditor")) && estado_admitido;
}
