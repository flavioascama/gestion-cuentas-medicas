import { obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type DetalleTrabajo = components["schemas"]["DetalleTrabajoRespuesta"];

export function obtener_trabajo(trabajo_id: number): Promise<DetalleTrabajo> {
  return obtener<DetalleTrabajo>(`/trabajos/${trabajo_id}`);
}
