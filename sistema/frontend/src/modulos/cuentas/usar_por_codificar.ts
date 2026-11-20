import { useQuery } from "@tanstack/react-query";
import { listar_por_codificar, type ProcedimientoPorCodificar } from "../../api/atenciones";

// Los procedimientos que el sistema hospitalario trajo sin codigo CPMS.
// Quien no puede verlos (error del servidor) los ve como lista vacia.
export function usar_por_codificar(cuenta_id: number): {
  cargando: boolean;
  pendientes: ProcedimientoPorCodificar[];
} {
  const consulta = useQuery({
    queryKey: ["cuentas", cuenta_id, "por-codificar"],
    queryFn: () => listar_por_codificar(cuenta_id),
    retry: false,
  });
  return { cargando: consulta.isPending, pendientes: consulta.data ?? [] };
}

export function texto_faltan_por_codificar(cantidad: number): string {
  return cantidad === 1
    ? "Falta 1 procedimiento por codificar"
    : `Faltan ${cantidad} procedimientos por codificar`;
}
