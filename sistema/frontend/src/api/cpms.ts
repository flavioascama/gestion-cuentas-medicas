import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type RespuestaSugerenciaCpms = components["schemas"]["RespuestaSugerenciaCpms"];
export type CandidatoCpms = components["schemas"]["CandidatoCpmsRespuesta"];
export type SolicitudConfirmarProcedimiento =
  components["schemas"]["SolicitudConfirmarProcedimiento"];
export type RespuestaProcedimientoConfirmado =
  components["schemas"]["RespuestaProcedimientoConfirmado"];
export type VersionCpms = components["schemas"]["VersionCpmsRespuesta"];
export type RespuestaCatalogoCpmsCargado = components["schemas"]["RespuestaCatalogoCpmsCargado"];

export interface FiltrosSugerenciaCpms {
  cuenta_medica_id?: number;
  codigo_grupo?: string;
  codigo_seccion?: string;
  codigo_subseccion?: string;
}

export function sugerir_codigo_cpms(
  descripcion: string,
  filtros: FiltrosSugerenciaCpms = {},
): Promise<RespuestaSugerenciaCpms> {
  return obtener<RespuestaSugerenciaCpms>("/cpms/sugerencias", { descripcion, ...filtros });
}

export function confirmar_procedimiento(
  cuenta_id: number,
  solicitud: SolicitudConfirmarProcedimiento,
): Promise<RespuestaProcedimientoConfirmado> {
  return enviar<RespuestaProcedimientoConfirmado>(
    "POST",
    `/cuentas/${cuenta_id}/procedimientos`,
    solicitud,
  );
}

// El precio con que se facturo por ultima vez ese codigo a la IAFAS de la
// cuenta; null si nunca se facturo.
export function ultimo_precio_procedimiento(
  cuenta_id: number,
  codigo: string,
): Promise<components["schemas"]["UltimoPrecioRespuesta"]> {
  return obtener(`/cuentas/${cuenta_id}/procedimientos/ultimo-precio`, { codigo });
}

export function listar_versiones_cpms(): Promise<VersionCpms[]> {
  return obtener<VersionCpms[]>("/catalogo-cpms/versiones");
}

export function cargar_catalogo_cpms(etiqueta?: string): Promise<RespuestaCatalogoCpmsCargado> {
  return enviar<RespuestaCatalogoCpmsCargado>("POST", "/catalogo-cpms/versiones", { etiqueta });
}
