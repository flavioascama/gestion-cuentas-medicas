import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  obtener_historial_cuenta,
  obtener_historial_lote,
  obtener_indicadores,
  type FiltrosIndicadores,
} from "../../api/trazabilidad";
import type { usar_sesion } from "../../sesion/contexto_sesion";

// Unica fuente de la condicion de visibilidad de la seccion/pestania de
// historial: la usa tanto seccion_historial.tsx como el detalle de
// cuenta (para decidir si la pestania aparece).
export function tiene_acceso_historial(sesion: ReturnType<typeof usar_sesion>["sesion"]): boolean {
  return sesion?.roles.includes("jefe") ?? false;
}

export function usar_historial_cuenta(cuenta_id: number) {
  return useQuery({
    queryKey: ["cuentas", cuenta_id, "historial"],
    queryFn: () => obtener_historial_cuenta(cuenta_id),
  });
}

export function usar_historial_lote(lote_id: number, habilitado: boolean) {
  return useQuery({
    queryKey: ["lotes", lote_id, "historial"],
    queryFn: () => obtener_historial_lote(lote_id),
    enabled: habilitado,
  });
}

// Seccion 1.3.3 de la tesis: el panel se refresca solo con un intervalo
// configurable (VITE_INTERVALO_REFRESCO_PANEL_SEGUNDOS, 60 por defecto).
const _INTERVALO_REFRESCO_PANEL_MS =
  Number(import.meta.env.VITE_INTERVALO_REFRESCO_PANEL_SEGUNDOS ?? 60) * 1000;

export function usar_indicadores(filtros: FiltrosIndicadores) {
  return useQuery({
    queryKey: ["indicadores", filtros],
    queryFn: () => obtener_indicadores(filtros),
    refetchInterval: _INTERVALO_REFRESCO_PANEL_MS,
    // Al cambiar de filtro, el panel anterior sigue visible (atenuado)
    // hasta que llega el nuevo: sin parpadeo ni salto de altura.
    placeholderData: keepPreviousData,
  });
}
