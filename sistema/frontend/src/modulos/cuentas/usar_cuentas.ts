import { useQuery } from "@tanstack/react-query";
import {
  consultar_completitud,
  listar_cuentas,
  obtener_acreditacion,
  obtener_cuenta,
  type FiltrosListarCuentas,
} from "../../api/cuentas";
import { listar_vencimientos, type Vencimiento } from "../../api/plazos";

export function usar_bandeja_cuentas(filtros: FiltrosListarCuentas) {
  return useQuery({
    queryKey: ["cuentas", filtros],
    queryFn: () =>
      listar_cuentas(filtros.estado, {
        etapa: filtros.etapa,
        iafas_codigo: filtros.iafas_codigo,
        fecha_prestacion: filtros.fecha_prestacion,
      }),
  });
}

export function usar_detalle_cuenta(cuenta_id: number) {
  return useQuery({
    queryKey: ["cuentas", cuenta_id],
    queryFn: () => obtener_cuenta(cuenta_id),
  });
}

export function usar_acreditacion_cuenta(cuenta_id: number) {
  return useQuery({
    queryKey: ["cuentas", cuenta_id, "acreditacion"],
    queryFn: () => obtener_acreditacion(cuenta_id),
    retry: false,
  });
}

export function usar_completitud_cuenta(cuenta_id: number) {
  return useQuery({
    queryKey: ["cuentas", cuenta_id, "completitud"],
    queryFn: () => consultar_completitud(cuenta_id),
  });
}

// RNF-06: el plazo vigente de cada cuenta (bandeja y detalle).
export function usar_vencimientos() {
  const consulta = useQuery({
    queryKey: ["plazos", "vencimientos"],
    queryFn: listar_vencimientos,
    refetchInterval: 60_000,
  });
  const por_cuenta = new Map<number, Vencimiento>();
  for (const vencimiento of consulta.data ?? []) {
    por_cuenta.set(vencimiento.cuenta_medica_id, vencimiento);
  }
  return por_cuenta;
}
