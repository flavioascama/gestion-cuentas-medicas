import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type ResumenLote = components["schemas"]["ResumenLoteRespuesta"];
export type DetalleLote = components["schemas"]["DetalleLoteRespuesta"];
export type InformePrevalidacion = components["schemas"]["InformePrevalidacionRespuesta"];
export type Hallazgo = components["schemas"]["HallazgoRespuesta"];
export type ResultadoValidacionOficial =
  components["schemas"]["ResultadoValidacionOficialRespuesta"];
export type ObservacionOficial = components["schemas"]["ObservacionOficialRespuesta"];
export type ResumenAcuse = components["schemas"]["ResumenAcuseRespuesta"];
export type CuentaLote = components["schemas"]["CuentaLoteRespuesta"];
export type RespuestaGenerarLote = components["schemas"]["RespuestaGenerarLote"];
export type RespuestaRemitirLote = components["schemas"]["RespuestaRemitirLote"];
export type RespuestaTrabajoEncolado = components["schemas"]["RespuestaTrabajoEncolado"];
export type RespuestaEnvioSusalud = components["schemas"]["RespuestaEnvioSusalud"];

export type LoteSugerido = components["schemas"]["LoteSugeridoRespuesta"];
export type CuentaPorLotear = components["schemas"]["CuentaPorLotearRespuesta"];

// Sin periodo: el servidor toma el mes de emision de los comprobantes.
export interface SolicitudGenerarLote {
  iafas_id: number;
  periodo?: string;
  cuenta_ids: number[];
}

export function listar_lotes_sugeridos(): Promise<LoteSugerido[]> {
  return obtener<LoteSugerido[]>("/lotes/sugeridos");
}

export function generar_lote(solicitud: SolicitudGenerarLote): Promise<RespuestaGenerarLote> {
  return enviar<RespuestaGenerarLote>("POST", "/lotes", solicitud);
}

export interface FiltrosListarLotes {
  periodo?: string;
  estado?: string;
  iafas_id?: number;
}

export function listar_lotes(filtros: FiltrosListarLotes = {}): Promise<ResumenLote[]> {
  return obtener<ResumenLote[]>("/lotes", { ...filtros });
}

export function obtener_lote(lote_id: number): Promise<DetalleLote> {
  return obtener<DetalleLote>(`/lotes/${lote_id}`);
}

export function obtener_prevalidacion_lote(lote_id: number): Promise<InformePrevalidacion> {
  return obtener<InformePrevalidacion>(`/lotes/${lote_id}/prevalidacion`);
}

export function solicitar_carga_en_validador(lote_id: number): Promise<RespuestaTrabajoEncolado> {
  return enviar<RespuestaTrabajoEncolado>("POST", `/lotes/${lote_id}/carga-validador`);
}

export function obtener_validacion_oficial_lote(
  lote_id: number,
): Promise<ResultadoValidacionOficial[]> {
  return obtener<ResultadoValidacionOficial[]>(`/lotes/${lote_id}/validacion-oficial`);
}

export function remitir_lote(lote_id: number): Promise<RespuestaRemitirLote> {
  return enviar<RespuestaRemitirLote>("POST", `/lotes/${lote_id}/remision-iafas`);
}

export function solicitar_monitoreo_respuesta(lote_id: number): Promise<RespuestaTrabajoEncolado> {
  return enviar<RespuestaTrabajoEncolado>("POST", `/lotes/${lote_id}/monitoreo`);
}

export function obtener_acuses_lote(lote_id: number): Promise<ResumenAcuse[]> {
  return obtener<ResumenAcuse[]>(`/lotes/${lote_id}/acuses`);
}

export function obtener_cuentas_lote(lote_id: number): Promise<CuentaLote[]> {
  return obtener<CuentaLote[]>(`/lotes/${lote_id}/cuentas`);
}

export function obtener_archivo_s01_lote(lote_id: number): Promise<Blob> {
  return obtener<Blob>(`/lotes/${lote_id}/archivo-s01`);
}

export function solicitar_envio_susalud(periodo: string): Promise<RespuestaEnvioSusalud> {
  return enviar<RespuestaEnvioSusalud>("POST", "/lotes/envio-susalud", { periodo });
}
