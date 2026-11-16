import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type ParametrosIafas = components["schemas"]["ParametrosIafasRespuesta"];
export type SolicitudParametrosIafas = components["schemas"]["SolicitudParametrosIafas"];
export type ParametroSistema = components["schemas"]["ParametroSistemaRespuesta"];

export function listar_parametros_iafas(): Promise<ParametrosIafas[]> {
  return obtener<ParametrosIafas[]>("/parametros/iafas");
}

export function actualizar_parametros_iafas(
  iafas_id: number,
  cambios: SolicitudParametrosIafas,
): Promise<ParametrosIafas> {
  return enviar<ParametrosIafas>("PATCH", `/parametros/iafas/${iafas_id}`, cambios);
}

export function actualizar_remitente_iafas(
  iafas_id: number,
  correo_remitente: string | null,
): Promise<ParametrosIafas> {
  return enviar<ParametrosIafas>("PUT", `/parametros/iafas/${iafas_id}/correo-remitente`, {
    correo_remitente,
  });
}

export function listar_parametros_sistema(): Promise<ParametroSistema[]> {
  return obtener<ParametroSistema[]>("/parametros/sistema");
}
