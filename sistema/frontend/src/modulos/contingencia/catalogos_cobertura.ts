import type { OpcionSelector } from "../../componentes_base/selector";

// Los valores que admite cada dato de la cobertura (2026-11-18). Tipo de
// documento y de afiliacion son los del estandar TEDEF (Tabla 2, campos 12
// y 7); el copago, los mismos que deja la consulta de ACREDITA SALUD.
export const DOCUMENTOS_AUTORIZACION: OpcionSelector[] = [
  { valor: "01", etiqueta: "Solicitud de atención médica (SITEDS)" },
  { valor: "02", etiqueta: "Solicitud de chequeo médico (SITEDS)" },
  { valor: "03", etiqueta: "Carta de garantía" },
  { valor: "04", etiqueta: "Por código" },
  { valor: "06", etiqueta: "Otro tipo de autorización" },
  { valor: "07", etiqueta: "Declaración de accidente" },
  { valor: "99", etiqueta: "No aplica" },
];
export const AFILIACIONES: OpcionSelector[] = [
  { valor: "1", etiqueta: "Regular" },
  { valor: "2", etiqueta: "SCTR" },
  { valor: "3", etiqueta: "Potestativo (independiente)" },
  { valor: "4", etiqueta: "SCTR independiente" },
  { valor: "5", etiqueta: "Otros contributivos y complementario" },
  { valor: "6", etiqueta: "SOAT" },
  { valor: "7", etiqueta: "AFOCAT" },
  { valor: "8", etiqueta: "SIS subsidiado" },
  { valor: "9", etiqueta: "Semicontributivo" },
];
export const TIPOS_COPAGO: OpcionSelector[] = [
  { valor: "ninguno", etiqueta: "Ninguno" },
  { valor: "fijo", etiqueta: "Monto fijo" },
  { valor: "coaseguro", etiqueta: "Coaseguro" },
];

export function nombre_en_catalogo(opciones: OpcionSelector[], valor: string): string {
  return opciones.find((opcion) => opcion.valor === valor)?.etiqueta ?? valor;
}
