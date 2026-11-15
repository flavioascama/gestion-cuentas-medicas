import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type DisponibilidadContingencia =
  components["schemas"]["DisponibilidadContingenciaRespuesta"];
export type SolicitudCoberturaContingencia =
  components["schemas"]["SolicitudCoberturaContingencia"];
export type SolicitudValidacionContingencia =
  components["schemas"]["SolicitudValidacionContingencia"];
export type RegistroContingencia = components["schemas"]["RegistroContingenciaRespuesta"];

export function disponibilidad_cobertura_contingencia(
  cuenta_id: number,
): Promise<DisponibilidadContingencia> {
  return obtener<DisponibilidadContingencia>(`/cuentas/${cuenta_id}/cobertura/contingencia`);
}

export function registrar_cobertura_contingencia(
  cuenta_id: number,
  solicitud: SolicitudCoberturaContingencia,
): Promise<{ acreditacion_id: number }> {
  return enviar("POST", `/cuentas/${cuenta_id}/cobertura/contingencia`, solicitud);
}

export function disponibilidad_validacion_contingencia(
  lote_id: number,
): Promise<DisponibilidadContingencia> {
  return obtener<DisponibilidadContingencia>(`/lotes/${lote_id}/validacion/contingencia`);
}

export function registrar_validacion_contingencia(
  lote_id: number,
  solicitud: SolicitudValidacionContingencia,
): Promise<{ estado_lote: string }> {
  return enviar("POST", `/lotes/${lote_id}/validacion/contingencia`, solicitud);
}

export function listar_registros_contingencia(): Promise<RegistroContingencia[]> {
  return obtener<RegistroContingencia[]>("/contingencias");
}

export function revisar_registro_contingencia(
  evento_id: string,
  conforme: boolean,
  comentario: string,
): Promise<void> {
  return enviar("POST", `/contingencias/${evento_id}/revision`, { conforme, comentario });
}

export type UltimaConsultaCobertura = components["schemas"]["UltimaConsultaCoberturaRespuesta"];

export function ultima_consulta_cobertura(
  cuenta_id: number,
): Promise<UltimaConsultaCobertura | null> {
  return obtener<UltimaConsultaCobertura | null>(`/cuentas/${cuenta_id}/cobertura/ultima-consulta`);
}
