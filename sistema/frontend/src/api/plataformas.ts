import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type ResumenSesionPlataforma = components["schemas"]["ResumenSesionPlataformaRespuesta"];
export type RespuestaSesionSolicitada = components["schemas"]["RespuestaSesionSolicitada"];

export function listar_sesiones_plataforma(
  plataforma?: string,
): Promise<ResumenSesionPlataforma[]> {
  return obtener<ResumenSesionPlataforma[]>("/plataformas/sesiones", { plataforma });
}

export function solicitar_sesion_plataforma(
  plataforma: string,
): Promise<RespuestaSesionSolicitada> {
  return enviar<RespuestaSesionSolicitada>("POST", `/plataformas/${plataforma}/sesion`);
}

export function obtener_imagen_captcha(sesion_id: number): Promise<Blob> {
  return obtener<Blob>(`/plataformas/sesiones/${sesion_id}/captcha`);
}

export function responder_captcha(sesion_id: number, respuesta: string): Promise<void> {
  return enviar<void>("POST", `/plataformas/sesiones/${sesion_id}/captcha`, { respuesta });
}
