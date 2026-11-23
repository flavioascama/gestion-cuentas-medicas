import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type CorreoIafas = components["schemas"]["CorreoIafasRespuesta"];
export type CorreoIafasDetalle = components["schemas"]["CorreoIafasDetalleRespuesta"];
export type AdjuntoCorreo = components["schemas"]["AdjuntoCorreoRespuesta"];
export type EstadoCorreo = "PROCESADO" | "POR_REVISAR" | "VINCULADO" | "DESCARTADO";

export interface FiltroCorreos {
  estado?: EstadoCorreo;
  cuenta_id?: number;
}

export function listar_correos_iafas(filtro: FiltroCorreos): Promise<CorreoIafas[]> {
  return obtener<CorreoIafas[]>("/correos-iafas", { ...filtro });
}

export function consultar_correo_iafas(correo_id: number): Promise<CorreoIafasDetalle> {
  return obtener<CorreoIafasDetalle>(`/correos-iafas/${correo_id}`);
}

export function descargar_adjunto_correo(correo_id: number, adjunto_id: number): Promise<Blob> {
  return obtener<Blob>(`/correos-iafas/${correo_id}/adjuntos/${adjunto_id}`);
}

export function vincular_correo_iafas(
  correo_id: number,
  identificacion_interna: string,
): Promise<CorreoIafasDetalle> {
  return enviar<CorreoIafasDetalle>("POST", `/correos-iafas/${correo_id}/vinculacion`, {
    identificacion_interna,
  });
}

export function descartar_correo_iafas(
  correo_id: number,
  motivo: string,
): Promise<CorreoIafasDetalle> {
  return enviar<CorreoIafasDetalle>("POST", `/correos-iafas/${correo_id}/descarte`, { motivo });
}

export type RespuestaCorreo = components["schemas"]["RespuestaCorreoRespuesta"];

// Lo que la clinica le contesto a la IAFAS por ese correo.
export function listar_respuestas_correo(correo_id: number): Promise<RespuestaCorreo[]> {
  return obtener<RespuestaCorreo[]>(`/correos-iafas/${correo_id}/respuestas`);
}

export function responder_correo_iafas(correo_id: number, texto: string): Promise<void> {
  return enviar<void>("POST", `/correos-iafas/${correo_id}/respuestas`, { texto });
}
