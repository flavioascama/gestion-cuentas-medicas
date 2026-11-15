import type { usar_sesion } from "../../sesion/contexto_sesion";

type Sesion = ReturnType<typeof usar_sesion>["sesion"];

const _LECTURA = ["analista", "auditor", "jefe", "tesoreria"];

export function tiene_acceso_comunicaciones(sesion: Sesion): boolean {
  return sesion?.roles.some((rol) => _LECTURA.includes(rol)) ?? false;
}
