import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type CartaGarantia = components["schemas"]["CartaGarantiaRespuesta"];
export type SolicitudCartaGarantia = components["schemas"]["SolicitudCartaGarantia"];

export function obtener_carta_garantia(cuenta_id: number): Promise<CartaGarantia | null> {
  return obtener<CartaGarantia | null>(`/cuentas/${cuenta_id}/carta-garantia`);
}

export function registrar_carta_garantia(
  cuenta_id: number,
  datos: SolicitudCartaGarantia,
): Promise<CartaGarantia> {
  return enviar<CartaGarantia>("POST", `/cuentas/${cuenta_id}/carta-garantia`, datos);
}

// En Registrada y Rechazada; queda en el historial.
export function corregir_carta_garantia(
  cuenta_id: number,
  datos: SolicitudCartaGarantia,
): Promise<CartaGarantia> {
  return enviar<CartaGarantia>("PUT", `/cuentas/${cuenta_id}/carta-garantia`, datos);
}
