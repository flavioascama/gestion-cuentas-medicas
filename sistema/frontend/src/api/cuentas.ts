import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type ResumenCuenta = components["schemas"]["ResumenCuentaRespuesta"];
export type DetalleCuenta = components["schemas"]["DetalleCuentaRespuesta"];
export type AcreditacionRespuesta = components["schemas"]["AcreditacionRespuesta"];
export type RespuestaTrabajoEncolado = components["schemas"]["RespuestaTrabajoEncolado"];
export type SolicitudNuevaCuenta = components["schemas"]["SolicitudNuevaCuenta"];
export type RespuestaCuentaCreada = components["schemas"]["RespuestaCuentaCreada"];
export type RespuestaCompletitudCuenta = components["schemas"]["RespuestaCompletitudCuenta"];
export type RespuestaComprobantePago = components["schemas"]["RespuestaComprobantePago"];

export interface FiltrosListarCuentas {
  estado?: string;
  etapa?: string;
  iafas_codigo?: string;
  fecha_prestacion?: string;
}

export function listar_cuentas(
  estado?: string,
  filtros: Omit<FiltrosListarCuentas, "estado"> = {},
): Promise<ResumenCuenta[]> {
  return obtener<ResumenCuenta[]>("/cuentas", { estado, ...filtros });
}

export function obtener_cuenta(cuenta_id: number): Promise<DetalleCuenta> {
  return obtener<DetalleCuenta>(`/cuentas/${cuenta_id}`);
}

export function solicitar_verificacion_cobertura(
  cuenta_id: number,
): Promise<RespuestaTrabajoEncolado> {
  return enviar<RespuestaTrabajoEncolado>("POST", `/cuentas/${cuenta_id}/cobertura`);
}

export function obtener_acreditacion(cuenta_id: number): Promise<AcreditacionRespuesta> {
  return obtener<AcreditacionRespuesta>(`/cuentas/${cuenta_id}/acreditacion`);
}

export function registrar_cuenta(datos: SolicitudNuevaCuenta): Promise<RespuestaCuentaCreada> {
  return enviar<RespuestaCuentaCreada>("POST", "/cuentas", datos);
}

export function consultar_completitud(cuenta_id: number): Promise<RespuestaCompletitudCuenta> {
  return obtener<RespuestaCompletitudCuenta>(`/cuentas/${cuenta_id}/completitud`);
}

export function emitir_comprobante_pago(cuenta_id: number): Promise<RespuestaComprobantePago> {
  return enviar<RespuestaComprobantePago>("POST", `/cuentas/${cuenta_id}/comprobante`);
}
