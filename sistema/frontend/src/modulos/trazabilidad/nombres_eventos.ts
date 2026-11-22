import { resolver_estado } from "../../componentes_base/mapa_estados";

// Nombre legible de cada tipo de evento que registra el servidor, para el
// historial (cuenta y lote) y el expediente de auditoria: un solo catalogo.
const _NOMBRES_EVENTOS: Record<string, string> = {
  // Transiciones de la cuenta.
  REGISTRO: "Cuenta registrada",
  FACTURACION: "Cuenta facturada",
  REMISION: "Cuenta enviada a la IAFAS",
  RECHAZO_LOTE: "Cuenta rechazada por la IAFAS",
  CORRECCION_REENVIO: "Cuenta corregida para reenvío",
  INICIO_AUDITORIA: "Auditoría de la IAFAS iniciada",
  GLOSA: "Observación total de la IAFAS",
  GLOSA_PARCIAL: "Observación parcial de la IAFAS",
  SUBSANACION: "Observación subsanada",
  NUEVA_OBSERVACION: "Nueva observación de la IAFAS",
  LIQUIDACION: "Liquidación registrada",
  LIQUIDACION_PARCIAL: "Liquidación parcial registrada",
  CONCILIACION_PAGO: "Pago conciliado",
  CONCILIACION_PAGO_PARCIAL: "Pago parcial conciliado",
  CIERRE: "Cuenta cerrada",
  ANULACION: "Cuenta anulada",
  // Cuenta.
  CUENTA_REGISTRADA: "Cuenta registrada",
  CUENTA_FACTURADA: "Cuenta facturada",
  CUENTA_ENVIADA: "Cuenta enviada a la IAFAS",
  CUENTA_EN_AUDITORIA: "Cuenta en auditoría de la IAFAS",
  CUENTA_RECHAZADA: "Cuenta rechazada por la IAFAS",
  ATENCION_IMPORTADA: "Atención importada del sistema hospitalario",
  SOLICITUD_ATENCION_CONSULTADA: "Atención consultada en el sistema hospitalario",
  COBERTURA_VERIFICADA: "Cobertura verificada",
  CARTA_GARANTIA_REGISTRADA: "Carta de garantía registrada",
  DIAGNOSTICO_REGISTRADO: "Diagnóstico registrado",
  PROCEDIMIENTO_CODIFICADO: "Procedimiento codificado",
  PROCEDIMIENTO_RETIRADO: "Procedimiento retirado",
  PRODUCTO_FARMACIA_REGISTRADO: "Producto de farmacia registrado",
  PRODUCTO_FARMACIA_RETIRADO: "Producto de farmacia retirado",
  COMPROBANTE_PAGO_EMITIDO: "Comprobante de pago emitido",
  COMPROBANTE_PAGO_REEMPLAZADO: "Comprobante de pago reemplazado",
  NOTA_DOCUMENTO_REGISTRADA: "Nota registrada",
  COPAGO_COBRADO_REGISTRADO: "Copago cobrado registrado",
  PAGO_ADICIONAL_REGISTRADO: "Pago adicional registrado",
  AUDITORIA_CONFORME: "Conformidad de la auditoría registrada",
  OBSERVACION_ADICIONAL: "Observación adicional de la IAFAS",
  OBSERVACION_REASIGNADA: "Observación reasignada",
  OBSERVACION_RESPONDIDA: "Observación respondida",
  RESPUESTA_IAFAS_REMITIDA: "Respuesta entregada a la IAFAS",
  COMUNICACION_IAFAS_RECIBIDA: "Comunicación de la IAFAS recibida",
  COMUNICACION_IAFAS_NO_APLICADA: "Comunicación de la IAFAS no aplicada",
  CORREO_IAFAS_CONSULTADO: "Correo de la IAFAS consultado",
  CORREO_IAFAS_VINCULADO: "Correo de la IAFAS vinculado a la cuenta",
  CORREO_IAFAS_DESCARTADO: "Correo de la IAFAS descartado",
  CORREO_IAFAS_POR_REVISAR: "Correo de la IAFAS por revisar",
  ANULACION_SOLICITADA: "Anulación solicitada",
  ANULACION_RECHAZADA: "Anulación rechazada",
  CONTINGENCIA_COBERTURA_REGISTRADA: "Cobertura registrada en contingencia",
  CONTINGENCIA_VALIDACION_REGISTRADA: "Validación registrada en contingencia",
  CONTINGENCIA_REVISADA: "Registro en contingencia revisado",
  HISTORIAL_CONSULTADO: "Historial consultado",
  EXPEDIENTE_EXPORTADO: "Expediente de auditoría exportado",
  RUPTURA_CADENA_DETECTADA: "Alteración en el registro de eventos detectada",
  // Lote.
  LOTE_GENERADO: "Lote generado",
  LOTE_VALIDACION_SOLICITADA: "Validación del lote solicitada",
  LOTE_CARGADO_VALIDADOR: "Lote cargado en el validador",
  LOTE_OBSERVADO_VALIDADOR: "Lote observado por el validador",
  LOTE_VALIDADO: "Lote validado",
  LOTE_REMITIDO: "Lote remitido a la IAFAS",
  LOTE_REMISION_FALLIDA: "Remisión del lote sin completar",
  LOTE_MONITOREO_SOLICITADO: "Respuesta de la IAFAS solicitada",
  LOTE_MONITOREO_EXCEDIDO: "Respuesta de la IAFAS fuera de plazo",
  LOTE_ACEPTADO: "Lote aceptado por la IAFAS",
  LOTE_RECHAZADO: "Lote rechazado por la IAFAS",
  LOTE_ENVIADO_SUSALUD: "Lote enviado a SUSALUD",
  DECLARACION_SIN_FACTURACION_REGISTRADA: "Declaración sin facturación registrada",
  // Plazos.
  CARTA_GARANTIA_PROXIMA_A_VENCER: "Cobertura por vencer",
  OBSERVACION_PLAZO_PROXIMO_A_VENCER: "Plazo de la observación por vencer",
  OBSERVACION_PLAZO_VENCIDO_ESCALADO: "Plazo de la observación vencido",
  LOTE_RECHAZADO_PLAZO_PROXIMO_A_VENCER: "Plazo de reenvío por vencer",
  LOTE_RECHAZADO_REENVIO_PENDIENTE_ESCALADO: "Plazo de reenvío vencido",
  AUDITORIA_PLAZO_PROXIMO_A_VENCER: "Plazo de la auditoría por vencer",
  AUDITORIA_EXCEDIDA: "Plazo de la auditoría vencido",
  LIQUIDACION_PAGO_PROXIMO_A_VENCER: "Plazo de pago por vencer",
  LIQUIDACION_PAGO_VENCIDO_ESCALADO: "Plazo de pago vencido",
  SUSALUD_ENVIO_PROXIMO_A_VENCER: "Envío a SUSALUD por vencer",
  SUSALUD_ENVIO_VENCIDO_ESCALADO: "Envío a SUSALUD vencido",
  // Acceso y administración.
  SESION_INICIADA: "Sesión iniciada",
  SESION_RECHAZADA: "Ingreso rechazado",
  SESION_CERRADA: "Sesión cerrada",
  SESION_PLATAFORMA_ACTIVA: "Ingreso a la plataforma externa",
  SESION_PLATAFORMA_FALLIDA: "Ingreso a la plataforma externa sin completar",
  ACCESO_DENEGADO: "Acceso no permitido",
  CLAVE_CAMBIADA: "Contraseña cambiada",
  CAMBIO_DE_CLAVE_RECHAZADO: "Cambio de contraseña rechazado",
  CLAVE_RESTABLECIDA: "Contraseña restablecida",
  USUARIO_CREADO: "Usuario creado",
  USUARIO_ACTUALIZADO: "Usuario actualizado",
  USUARIO_REACTIVADO: "Usuario reactivado",
  USUARIO_DESACTIVADO: "Usuario desactivado",
  IAFAS_REGISTRADA: "IAFAS registrada",
  IAFAS_ELIMINADA: "IAFAS dada de baja",
  PARAMETROS_IAFAS_ACTUALIZADOS: "Parámetros de la IAFAS actualizados",
  PARAMETROS_SISTEMA_ACTUALIZADOS: "Parámetros del sistema actualizados",
  CATALOGO_GTIN_CARGADO: "Catálogo de productos cargado",
  NAVEGACION_ROBOT_OPCION_CAMBIADA: "Opción de ver las plataformas externas cambiada",
  NAVEGACION_ROBOT_CONSULTADA: "Opción de ver las plataformas externas consultada",
  AVISO_MARCADO_ATENDIDO: "Aviso marcado como atendido",
  CARTA_GARANTIA_CORREGIDA: "Carta de garantía corregida",
  LIQUIDACION_CORREGIDA: "Liquidación corregida",
  PAGO_CORREGIDO: "Pago corregido",
  ASEGURADO_CORREGIDO: "Datos del asegurado corregidos",
  EVIDENCIA_DESCIFRADA: "Evidencia consultada",
  CONTINUIDAD_RESTABLECIDA: "Secuencia de estados regularizada",
};

// Un tipo no catalogado: el texto con espacios y sin mayusculas sostenidas.
export function nombre_evento(tipo_evento: string): string {
  const nombre = _NOMBRES_EVENTOS[tipo_evento];
  if (nombre) return nombre;
  const texto = tipo_evento.replace(/_/g, " ").toLowerCase();
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

// Quien actuo sin ser una persona (la automatizacion, el temporizador).
const _ACTORES_SISTEMA = new Set([
  "trabajador_automatizacion",
  "robot_comunicaciones_iafas",
  "temporizador_sistema",
]);

export function nombre_actor(actor: string): string {
  return _ACTORES_SISTEMA.has(actor) || actor.startsWith("robot_") ? "Sistema" : actor;
}

export function nombre_estado_evento(estado: string | null | undefined): string {
  return estado ? resolver_estado(estado).texto : "—";
}
