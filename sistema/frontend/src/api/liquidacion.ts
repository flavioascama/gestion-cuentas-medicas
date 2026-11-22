import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type Liquidacion = components["schemas"]["LiquidacionRespuesta"];
export type RespuestaLiquidacionRegistrada =
  components["schemas"]["RespuestaLiquidacionRegistrada"];
export type RespuestaConciliacion = components["schemas"]["RespuestaConciliacion"];

export function obtener_liquidacion(cuenta_id: number): Promise<Liquidacion | null> {
  return obtener<Liquidacion | null>(`/cuentas/${cuenta_id}/liquidacion`);
}

export function registrar_liquidacion(
  cuenta_id: number,
  monto_liquidado: string,
): Promise<RespuestaLiquidacionRegistrada> {
  return enviar<RespuestaLiquidacionRegistrada>("POST", `/cuentas/${cuenta_id}/liquidacion`, {
    monto_liquidado,
  });
}

// Mientras la cuenta siga como quedo al liquidarse y sin pago; queda en el historial.
export function corregir_liquidacion(
  cuenta_id: number,
  monto_liquidado: string,
): Promise<Liquidacion> {
  return enviar<Liquidacion>("PUT", `/cuentas/${cuenta_id}/liquidacion`, { monto_liquidado });
}

export function conciliar_pago(
  cuenta_id: number,
  monto_pagado: string,
): Promise<RespuestaConciliacion> {
  return enviar<RespuestaConciliacion>("POST", `/cuentas/${cuenta_id}/pago`, { monto_pagado });
}
