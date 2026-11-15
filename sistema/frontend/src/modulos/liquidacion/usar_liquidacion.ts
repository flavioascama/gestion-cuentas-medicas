import { useQuery } from "@tanstack/react-query";
import { obtener_liquidacion } from "../../api/liquidacion";

export function usar_liquidacion_cuenta(cuenta_id: number) {
  return useQuery({
    queryKey: ["cuentas", cuenta_id, "liquidacion"],
    queryFn: () => obtener_liquidacion(cuenta_id),
  });
}
