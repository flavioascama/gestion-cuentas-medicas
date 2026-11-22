// Tipos de documento del asegurado (formulario de nueva cuenta y detalle).
export const OPCIONES_TIPO_DOCUMENTO = [
  { valor: "1", etiqueta: "DNI" },
  { valor: "2", etiqueta: "Carné de extranjería" },
  { valor: "3", etiqueta: "Pasaporte" },
];

const _TIPOS_ATENCION: Record<string, string> = {
  AMBULATORIA: "Ambulatoria",
  EMERGENCIA: "Emergencia",
  HOSPITALIZACION: "Hospitalización",
};

export function etiqueta_tipo_atencion(tipo: string): string {
  return _TIPOS_ATENCION[tipo] ?? tipo;
}

const _AREAS_PROCEDIMIENTO: Record<string, string> = {
  PROCEDIMIENTO: "Procedimiento",
  LABORATORIO: "Laboratorio",
  IMAGENES: "Imágenes",
};

export function etiqueta_area_procedimiento(area: string): string {
  return _AREAS_PROCEDIMIENTO[area.toUpperCase()] ?? area;
}
