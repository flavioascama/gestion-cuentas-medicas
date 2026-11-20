import { enviar, obtener } from "./cliente_http";
import type { RespuestaCuentaCreada } from "./cuentas";
import type { components } from "./tipos_openapi";

export type ResumenAtencion = components["schemas"]["ResumenAtencionRespuesta"];
export type ProcedimientoPorCodificar = components["schemas"]["ProcedimientoPorCodificarRespuesta"];

// El documento del paciente no viaja en la direccion: la lista llega
// completa y se filtra en la pantalla.
export function listar_atenciones(): Promise<ResumenAtencion[]> {
  return obtener<ResumenAtencion[]>("/atenciones-hospitalarias");
}

export function importar_atencion(atencion_id: string): Promise<RespuestaCuentaCreada> {
  return enviar<RespuestaCuentaCreada>(
    "POST",
    `/atenciones-hospitalarias/${encodeURIComponent(atencion_id)}/importar`,
  );
}

// El cuerpo es el archivo .json exportado por el sistema hospitalario.
export function importar_archivo(contenido: unknown): Promise<RespuestaCuentaCreada> {
  return enviar<RespuestaCuentaCreada>("POST", "/cuentas/importar", contenido);
}

export function listar_por_codificar(cuenta_id: number): Promise<ProcedimientoPorCodificar[]> {
  return obtener<ProcedimientoPorCodificar[]>(`/cuentas/${cuenta_id}/procedimientos-por-codificar`);
}
