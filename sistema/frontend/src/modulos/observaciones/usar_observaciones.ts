import { useQuery } from "@tanstack/react-query";
import { listar_motivos_observacion, listar_observaciones } from "../../api/observaciones";
import type { usar_sesion } from "../../sesion/contexto_sesion";

// Unica fuente de la condicion de visibilidad de la seccion/pestania de
// observaciones: la usa tanto seccion_observaciones.tsx como el
// detalle de cuenta (para decidir si la pestania aparece).
export function tiene_acceso_observaciones(
  sesion: ReturnType<typeof usar_sesion>["sesion"],
): boolean {
  if (!sesion) return false;
  const roles_con_acceso = ["analista", "auditor", "jefe"] as const;
  return roles_con_acceso.some((rol) => sesion.roles.includes(rol));
}

export function usar_observaciones_cuenta(cuenta_id: number) {
  return useQuery({
    queryKey: ["cuentas", cuenta_id, "observaciones"],
    queryFn: () => listar_observaciones(cuenta_id),
  });
}

export function usar_motivos_observacion(habilitada = true) {
  return useQuery({
    queryKey: ["observaciones", "motivos"],
    queryFn: listar_motivos_observacion,
    enabled: habilitada,
  });
}

// La descripcion de cada motivo por su codigo (2026-11-18): las tablas
// mostraban solo el codigo. Solo se consulta con un rol que ve el catalogo.
export function usar_descripciones_motivos(habilitada: boolean): Map<string, string> {
  const consulta = usar_motivos_observacion(habilitada);
  return new Map((consulta.data ?? []).map((motivo) => [motivo.codigo, motivo.descripcion]));
}
