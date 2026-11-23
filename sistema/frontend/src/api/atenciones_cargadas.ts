import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type AtencionesCargadas = components["schemas"]["AtencionesCargadasRespuesta"];

// Atenciones del sistema hospitalario cargadas con un Excel (administrador).
export function cargar_atenciones_hospitalarias(
  archivo: components["schemas"]["SolicitudCargarAtenciones"],
): Promise<AtencionesCargadas> {
  return enviar<AtencionesCargadas>("POST", "/administracion/atenciones-hospitalarias", archivo);
}

export function descargar_plantilla_atenciones(): Promise<Blob> {
  return obtener<Blob>("/administracion/atenciones-hospitalarias/plantilla");
}
