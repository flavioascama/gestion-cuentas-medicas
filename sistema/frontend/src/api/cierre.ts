import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type RespuestaCierre = components["schemas"]["RespuestaCierre"];
export type RespuestaSolicitudAnulacion = components["schemas"]["RespuestaSolicitudAnulacion"];
export type SolicitudAnulacion = components["schemas"]["SolicitudAnulacionRespuesta"];
export type RespuestaResolucionAnulacion = components["schemas"]["RespuestaResolucionAnulacion"];
export type EstadoCierre = components["schemas"]["EstadoCierreRespuesta"];

export function consultar_cierre(cuenta_id: number): Promise<EstadoCierre> {
  return obtener<EstadoCierre>(`/cuentas/${cuenta_id}/cierre`);
}

export function cerrar_cuenta(cuenta_id: number): Promise<RespuestaCierre> {
  return enviar<RespuestaCierre>("POST", `/cuentas/${cuenta_id}/cierre`);
}

export function solicitar_anulacion(
  cuenta_id: number,
  motivo: string,
): Promise<RespuestaSolicitudAnulacion> {
  return enviar<RespuestaSolicitudAnulacion>("POST", `/cuentas/${cuenta_id}/anulacion/solicitud`, {
    motivo,
  });
}

export function listar_anulaciones_pendientes(): Promise<SolicitudAnulacion[]> {
  return obtener<SolicitudAnulacion[]>("/anulaciones/pendientes");
}

export function resolver_anulacion(
  solicitud_id: number,
  aprobada: boolean,
  motivo: string,
): Promise<RespuestaResolucionAnulacion> {
  return enviar<RespuestaResolucionAnulacion>("POST", `/anulaciones/${solicitud_id}/resolucion`, {
    aprobada,
    motivo: motivo.trim() || null,
  });
}
