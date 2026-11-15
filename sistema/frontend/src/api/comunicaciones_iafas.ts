import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type ComunicacionIafas = components["schemas"]["ComunicacionIafasRespuesta"];
export type RevisionSolicitada = components["schemas"]["RevisionSolicitada"];

export function listar_comunicaciones_iafas(cuenta_id: number): Promise<ComunicacionIafas[]> {
  return obtener<ComunicacionIafas[]>("/comunicaciones-iafas", { cuenta_id });
}

export function solicitar_revision_comunicaciones(): Promise<RevisionSolicitada> {
  return enviar<RevisionSolicitada>("POST", "/comunicaciones-iafas/revision");
}
