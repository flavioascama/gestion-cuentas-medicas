// Textos visibles de los correos recibidos: un solo lugar, igual que
// mapa_estados.ts y mapa_roles.ts.

export const MOTIVOS_REVISION: Record<string, string> = {
  SIN_FORMATO: "Sin el formato de la IAFAS",
  REMITENTE_NO_REGISTRADO: "Remitente no registrado",
  COMPROBANTE_DESCONOCIDO: "Comprobante desconocido",
};

export const MOTIVOS_OMISION: Record<string, string> = {
  TIPO_NO_PERMITIDO: "Tipo de archivo no permitido",
  EXCEDE_TAMANO: "Supera el tamaño permitido",
  EXCEDE_CANTIDAD: "Supera la cantidad permitida",
};
