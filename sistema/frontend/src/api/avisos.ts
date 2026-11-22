import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type Aviso = components["schemas"]["AvisoRespuesta"];

export function listar_avisos(): Promise<Aviso[]> {
  return obtener<Aviso[]>("/avisos");
}

export function marcar_aviso_atendido(evento_id: string): Promise<void> {
  return enviar<void>("POST", `/avisos/${evento_id}/atendido`);
}
