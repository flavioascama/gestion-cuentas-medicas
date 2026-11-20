import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type Vencimiento = components["schemas"]["VencimientoRespuesta"];
export type ControlPeriodoSusalud = components["schemas"]["ControlPeriodoSusaludRespuesta"];

export function listar_vencimientos(): Promise<Vencimiento[]> {
  return obtener<Vencimiento[]>("/plazos/vencimientos");
}

export function listar_control_susalud(): Promise<ControlPeriodoSusalud[]> {
  return obtener<ControlPeriodoSusalud[]>("/plazos/susalud");
}

export type DeclaracionSinFacturacion = components["schemas"]["DeclaracionSinFacturacionRespuesta"];

export function registrar_declaracion_sin_facturacion(
  periodo: string,
): Promise<DeclaracionSinFacturacion> {
  return enviar<DeclaracionSinFacturacion>("POST", "/plazos/susalud/declaraciones", { periodo });
}
