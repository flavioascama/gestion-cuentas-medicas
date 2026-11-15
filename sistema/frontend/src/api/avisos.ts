import { obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type Aviso = components["schemas"]["AvisoRespuesta"];

export function listar_avisos(): Promise<Aviso[]> {
  return obtener<Aviso[]>("/avisos");
}
