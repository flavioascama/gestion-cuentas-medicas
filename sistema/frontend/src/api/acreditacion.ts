import { obtener } from "./cliente_http";

// La Solicitud de Atencion Medica de la acreditacion vigente (imagen).
export function obtener_solicitud_atencion(cuenta_id: number): Promise<Blob> {
  return obtener<Blob>(`/cuentas/${cuenta_id}/acreditacion/solicitud-atencion`);
}
