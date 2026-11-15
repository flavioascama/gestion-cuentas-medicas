import { enviar, obtener } from "./cliente_http";
import type { components } from "./tipos_openapi";

export type DocumentosPago = components["schemas"]["DocumentosPagoRespuesta"];
export type ComprobanteVigente = components["schemas"]["ComprobanteVigenteRespuesta"];
export type NotaDocumento = components["schemas"]["NotaDocumentoRespuesta"];
export type SolicitudNota = components["schemas"]["SolicitudNota"];

export function consultar_documentos_pago(cuenta_id: number): Promise<DocumentosPago | null> {
  return obtener<DocumentosPago | null>(`/cuentas/${cuenta_id}/comprobante`);
}

export function reemplazar_comprobante(
  cuenta_id: number,
  motivo: string,
): Promise<ComprobanteVigente> {
  return enviar<ComprobanteVigente>("POST", `/cuentas/${cuenta_id}/comprobante/reemplazo`, {
    motivo,
  });
}

export function registrar_nota(cuenta_id: number, datos: SolicitudNota): Promise<NotaDocumento> {
  return enviar<NotaDocumento>("POST", `/cuentas/${cuenta_id}/comprobante/nota`, datos);
}
