import { useQuery } from "@tanstack/react-query";
import { enviar } from "../../api/cliente_http";
import { obtener_liquidacion, type Liquidacion } from "../../api/liquidacion";

export function usar_liquidacion_cuenta(cuenta_id: number) {
  return useQuery({
    queryKey: ["cuentas", cuenta_id, "liquidacion"],
    queryFn: () => obtener_liquidacion(cuenta_id),
  });
}

// El pago que registro una persona, mientras la cuenta no este Cerrada ni
// Anulada; queda en el historial.
export function corregir_pago(cuenta_id: number, monto_pagado: string): Promise<Liquidacion> {
  return enviar<Liquidacion>("PUT", `/cuentas/${cuenta_id}/pago`, { monto_pagado });
}
