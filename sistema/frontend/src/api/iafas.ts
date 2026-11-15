import { obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type ResumenIafas = components["schemas"]["ResumenIafasRespuesta"];

export function listar_iafas(): Promise<ResumenIafas[]> {
  return obtener<ResumenIafas[]>("/iafas");
}
