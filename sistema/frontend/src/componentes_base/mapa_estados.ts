// Mapa unico de estados (GUIA_DISENO_INTERFAZ.md, Seccion 5: "mismos
// colores y textos en toda la aplicacion, definidos en un unico mapa de
// estados"). Cubre cuenta_medica, lote_facturacion, trabajo,
// sesion_plataforma, validacion_oficial y acuse_transmision (Seccion 6
// del plan v3, restricciones CHECK de los modelos SQLAlchemy).
//
// Cinco categorias de color, pero las cuentas y los lotes usan solo
// cuatro y con un criterio estricto (2026-11-12): gris para el avance
// normal, ambar para lo que hay que atender, rojo para un rechazo y
// verde para el desenlace exitoso. El texto de la pildora siempre dice
// el estado exacto (Tabla 58), que la trazabilidad necesita.
//
// "CERRADA" es ambiguo a proposito: lo comparten cuenta_medica (Tabla
// 58, estado terminal exitoso) y sesion_plataforma (una sesion que se
// cerro, sin connotacion de exito o fracaso) porque resolver_estado()
// no conoce la entidad, solo el texto del estado -- se resuelve a favor
// del significado de cuenta_medica (exito), el mas visible en pantalla.

export type ColorEstado = "gris" | "azul" | "ambar" | "verde" | "rojo";

interface DefinicionEstado {
  texto: string;
  color: ColorEstado;
}

const _ESTADOS: Record<string, DefinicionEstado> = {
  // cuenta_medica.estado (Tabla 58). Color solo donde hay algo que la
  // clinica debe atender o un desenlace (2026-11-12, pedido del usuario:
  // catorce estados con cinco colores eran ruido): el avance normal del
  // ciclo va en gris; ambar = la IAFAS observo la cuenta y hay que
  // responder; rojo = la IAFAS rechazo la cuenta; verde = cerrada.
  REGISTRADA: { texto: "Registrada", color: "gris" },
  FACTURADA: { texto: "Facturada", color: "gris" },
  ENVIADA: { texto: "Enviada", color: "gris" },
  RECHAZADA: { texto: "Rechazada", color: "rojo" },
  EN_AUDITORIA: { texto: "En auditoría", color: "gris" },
  GLOSADA: { texto: "Glosada", color: "ambar" },
  GLOSADA_PARCIAL: { texto: "Glosada parcial", color: "ambar" },
  SUBSANADA: { texto: "Subsanada", color: "gris" },
  LIQUIDADA: { texto: "Liquidada", color: "gris" },
  LIQUIDADA_PARCIAL: { texto: "Liquidada parcial", color: "gris" },
  PAGADA: { texto: "Pagada", color: "gris" },
  PAGADA_PARCIAL: { texto: "Pagada parcial", color: "gris" },
  CERRADA: { texto: "Cerrada", color: "verde" },
  ANULADA: { texto: "Anulada", color: "gris" },

  // lote_facturacion.estado: mismo criterio (ambar = observado por el
  // validador, hay que corregir; rojo = rechazado; verde = aceptado).
  GENERADO: { texto: "Generado", color: "gris" },
  CARGADO_VALIDADOR: { texto: "Cargado en el validador", color: "gris" },
  OBSERVADO_VALIDADOR: { texto: "Observado por el validador", color: "ambar" },
  VALIDADO: { texto: "Validado", color: "gris" },
  REMITIDO_IAFAS: { texto: "Remitido a la IAFAS", color: "gris" },
  ACEPTADO: { texto: "Aceptado", color: "verde" },
  RECHAZADO: { texto: "Rechazado", color: "rojo" },
  // CU-05: el monitoreo agoto la ventana sin respuesta de la IAFAS (marca,
  // no estado: el lote sigue remitido).
  EXCEDIDO: { texto: "Excedido", color: "ambar" },
  // El lote ya no refleja sus cuentas (marca, no estado).
  DESACTUALIZADO: { texto: "Desactualizado", color: "ambar" },

  // Envio a SUSALUD por periodo (RT-05, RI-16). ENVIADO y PENDIENTE
  // comparten texto y color con los de abajo.
  ENVIADO_FUERA_DE_PLAZO: { texto: "Enviado fuera de plazo", color: "ambar" },
  POR_VENCER: { texto: "Por vencer", color: "ambar" },
  VENCIDO: { texto: "Vencido", color: "rojo" },
  SIN_LOTES: { texto: "Sin lotes", color: "ambar" },

  // trabajo.estado
  PENDIENTE: { texto: "Pendiente", color: "gris" },
  EN_PROCESO: { texto: "En proceso", color: "azul" },
  COMPLETADO: { texto: "Completado", color: "verde" },
  AGOTADO: { texto: "Agotado", color: "rojo" },
  REQUIERE_SESION: { texto: "Requiere sesión", color: "ambar" },
  SIN_RESULTADO: { texto: "Sin resultado", color: "ambar" },
  // Opciones que el administrador activa o apaga (navegacion del robot).
  OPCION_ACTIVADA: { texto: "Activada", color: "verde" },
  OPCION_DESACTIVADA: { texto: "Desactivada", color: "gris" },
  // El robot que corre en un equipo con pantalla (el que abre la ventana real).
  ROBOT_ENCENDIDO: { texto: "Encendido", color: "verde" },
  ROBOT_APAGADO: { texto: "Apagado", color: "gris" },

  // sesion_plataforma.estado
  SOLICITADA: { texto: "Solicitada", color: "gris" },
  ESPERANDO_CAPTCHA: { texto: "Esperando CAPTCHA", color: "ambar" },
  CAPTCHA_RESPONDIDO: { texto: "CAPTCHA respondido", color: "azul" },
  ACTIVA: { texto: "Activa", color: "verde" },
  EXPIRADA: { texto: "Expirada", color: "ambar" },
  FALLIDA: { texto: "Fallida", color: "rojo" },
  // "CERRADA" de sesion_plataforma comparte texto y color con la de
  // cuenta_medica (arriba): ver el comentario del encabezado.

  // validacion_oficial.resultado
  CONFORME: { texto: "Conforme", color: "verde" },
  OBSERVADO: { texto: "Observado", color: "ambar" },

  // acuse_transmision.resultado_transferencia / respuesta_receptor
  ENVIADO: { texto: "Enviado", color: "verde" },
  ERROR_TRANSFERENCIA: { texto: "Error de transferencia", color: "rojo" },

  // correo_iafas.estado: ambar solo el que una persona debe revisar.
  POR_REVISAR: { texto: "Por revisar", color: "ambar" },
  PROCESADO: { texto: "Aplicado a la cuenta", color: "gris" },
  VINCULADO: { texto: "Vinculado a la cuenta", color: "gris" },
  DESCARTADO: { texto: "Descartado", color: "gris" },
};

export function resolver_estado(estado: string): DefinicionEstado {
  return _ESTADOS[estado] ?? { texto: estado, color: "gris" };
}
