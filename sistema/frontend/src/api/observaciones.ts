import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type Observacion = components["schemas"]["ObservacionRespuesta"];
export type MotivoObservacion = components["schemas"]["MotivoObservacionRespuesta"];
export type RespuestaObservacionRegistrada =
  components["schemas"]["RespuestaObservacionRegistrada"];
export type SolicitudRegistroObservacion = components["schemas"]["SolicitudRegistroObservacion"];
export type SolicitudAsignacionObservacion =
  components["schemas"]["SolicitudAsignacionObservacion"];
export type SolicitudRespuestaObservacion = components["schemas"]["SolicitudRespuestaObservacion"];
export type ConformidadAuditoria = components["schemas"]["ConformidadAuditoriaRespuesta"];
export type ResponsablePosible = components["schemas"]["ResponsablePosibleRespuesta"];
export type RespuestaNuevaEntrega = components["schemas"]["RespuestaNuevaEntrega"];

export function listar_observaciones(cuenta_id: number): Promise<Observacion[]> {
  return obtener<Observacion[]>(`/cuentas/${cuenta_id}/observaciones`);
}

// Las personas a las que el jefe puede asignar una observacion.
export function listar_responsables_posibles(): Promise<ResponsablePosible[]> {
  return obtener<ResponsablePosible[]>("/observaciones/responsables");
}

export function listar_motivos_observacion(): Promise<MotivoObservacion[]> {
  return obtener<MotivoObservacion[]>("/observaciones/motivos");
}

export function registrar_observacion(
  cuenta_id: number,
  datos: SolicitudRegistroObservacion,
): Promise<RespuestaObservacionRegistrada> {
  return enviar<RespuestaObservacionRegistrada>(
    "POST",
    `/cuentas/${cuenta_id}/observaciones`,
    datos,
  );
}

export function asignar_responsable_observacion(
  observacion_id: number,
  datos: SolicitudAsignacionObservacion,
): Promise<void> {
  return enviar<void>("PATCH", `/observaciones/${observacion_id}/asignacion`, datos);
}

export function responder_observacion(
  observacion_id: number,
  datos: SolicitudRespuestaObservacion,
): Promise<void> {
  return enviar<void>("POST", `/observaciones/${observacion_id}/respuesta`, datos);
}

// Vuelve a encolar la entrega de la respuesta a la IAFAS (2026-11-19).
export function pedir_nueva_entrega(observacion_id: number): Promise<RespuestaNuevaEntrega> {
  return enviar<RespuestaNuevaEntrega>("POST", `/observaciones/${observacion_id}/entrega`);
}

export function consultar_conformidad_auditoria(cuenta_id: number): Promise<ConformidadAuditoria> {
  return obtener<ConformidadAuditoria>(`/cuentas/${cuenta_id}/auditoria/conformidad`);
}

export function registrar_conformidad_auditoria(cuenta_id: number): Promise<void> {
  return enviar<void>("POST", `/cuentas/${cuenta_id}/auditoria/conformidad`);
}
