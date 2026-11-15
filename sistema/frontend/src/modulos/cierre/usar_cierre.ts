import { useQuery } from "@tanstack/react-query";
import { listar_anulaciones_pendientes } from "../../api/cierre";
import type { usar_sesion } from "../../sesion/contexto_sesion";

const _ESTADOS_TERMINALES = new Set(["CERRADA", "ANULADA"]);

// Unica fuente de la condicion de visibilidad de la seccion/pestania de
// cierre y anulacion: la usa tanto seccion_cierre_anulacion.tsx como el
// detalle de cuenta (para decidir si la pestania aparece), para no
// duplicar la regla de rol/estado en dos lugares que podrian
// desalinearse.
export function es_visible_cierre_anulacion(
  sesion: ReturnType<typeof usar_sesion>["sesion"],
  estado: string,
): boolean {
  if (!sesion?.roles.includes("analista")) return false;
  return !_ESTADOS_TERMINALES.has(estado);
}

export function usar_anulaciones_pendientes() {
  return useQuery({
    queryKey: ["anulaciones", "pendientes"],
    queryFn: listar_anulaciones_pendientes,
  });
}
