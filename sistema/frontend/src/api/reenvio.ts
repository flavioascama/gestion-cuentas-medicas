import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type RechazoCuenta = components["schemas"]["RechazoCuentaRespuesta"];
export type RespuestaCorreccionReenvio = components["schemas"]["RespuestaCorreccionReenvio"];

export function obtener_rechazo_cuenta(cuenta_id: number): Promise<RechazoCuenta> {
  return obtener<RechazoCuenta>(`/cuentas/${cuenta_id}/rechazo`);
}

export function corregir_cuenta_rechazada(
  cuenta_id: number,
  descripcion_correccion: string,
): Promise<RespuestaCorreccionReenvio> {
  return enviar<RespuestaCorreccionReenvio>("POST", `/cuentas/${cuenta_id}/correccion-reenvio`, {
    descripcion_correccion,
  });
}
