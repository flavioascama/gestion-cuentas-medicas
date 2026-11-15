import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type HistorialCuenta = components["schemas"]["HistorialCuentaRespuesta"];
export type HistorialLote = components["schemas"]["HistorialLoteRespuesta"];
export type EventoHistorial = components["schemas"]["EventoHistorialRespuesta"];
export type Expediente = components["schemas"]["ExpedienteRespuesta"];
export type IndicadoresCiclo = components["schemas"]["IndicadoresCicloRespuesta"];
export type TiempoEtapa = components["schemas"]["TiempoEtapaRespuesta"];
export type DistribucionEstado = components["schemas"]["DistribucionEstadoRespuesta"];
export type LotesPeriodoEstado = components["schemas"]["LotesPeriodoEstadoRespuesta"];
export type IndicadoresIafas = components["schemas"]["IndicadoresIafasRespuesta"];
export type TiempoCicloCuentas = components["schemas"]["TiempoCicloCuentasRespuesta"];
export type CicloCuenta = components["schemas"]["CicloCuentaRespuesta"];

export function obtener_historial_cuenta(cuenta_id: number): Promise<HistorialCuenta> {
  return obtener<HistorialCuenta>(`/cuentas/${cuenta_id}/historial`);
}

export function obtener_historial_lote(lote_id: number): Promise<HistorialLote> {
  return obtener<HistorialLote>(`/lotes/${lote_id}/historial`);
}

export function exportar_expediente(cuenta_id: number, motivo: string): Promise<Expediente> {
  return enviar<Expediente>("POST", `/cuentas/${cuenta_id}/expediente`, { motivo });
}

export interface FiltrosIndicadores {
  iafas_codigo?: string;
  periodo?: string;
  [clave: string]: string | undefined;
}

export function obtener_indicadores(filtros: FiltrosIndicadores): Promise<IndicadoresCiclo> {
  return obtener<IndicadoresCiclo>("/indicadores", filtros);
}
