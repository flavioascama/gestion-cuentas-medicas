import { obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type ResumenCie10 = components["schemas"]["ResumenCie10Respuesta"];

export function buscar_cie10(texto: string): Promise<ResumenCie10[]> {
  return obtener<ResumenCie10[]>(`/cie10/buscar?q=${encodeURIComponent(texto)}`);
}
