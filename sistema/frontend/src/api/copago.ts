import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type CopagoCobrado = components["schemas"]["CopagoCobradoRespuesta"];
export type CopagoAsegurado = components["schemas"]["CopagoAseguradoRespuesta"];
export type SolicitudCopagoCobrado = components["schemas"]["SolicitudCopagoCobrado"];

export function consultar_copago_asegurado(cuenta_id: number): Promise<CopagoAsegurado> {
  return obtener<CopagoAsegurado>(`/cuentas/${cuenta_id}/copago-asegurado`);
}

export function consultar_copago_cobrado(cuenta_id: number): Promise<CopagoCobrado | null> {
  return obtener<CopagoCobrado | null>(`/cuentas/${cuenta_id}/copago-cobrado`);
}

export function registrar_copago_cobrado(
  cuenta_id: number,
  solicitud: SolicitudCopagoCobrado,
): Promise<CopagoCobrado> {
  return enviar<CopagoCobrado>("POST", `/cuentas/${cuenta_id}/copago-cobrado`, solicitud);
}
