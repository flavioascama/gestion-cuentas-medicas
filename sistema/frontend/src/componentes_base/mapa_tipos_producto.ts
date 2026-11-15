// Tipo de producto de farmacia (TEDEF, T4 campo 7): un solo lugar que
// traduce la letra del estandar a su nombre visible, igual que
// mapa_roles.ts y mapa_estados.ts.

const _ETIQUETAS_TIPO_PRODUCTO: Record<string, string> = {
  M: "Medicamento",
  I: "Insumo o dispositivo médico",
  B: "Producto sanitario o cosmético",
  A: "Suplemento alimenticio",
};

export function etiqueta_tipo_producto(tipo: string | null | undefined): string {
  if (!tipo) return "—";
  return _ETIQUETAS_TIPO_PRODUCTO[tipo] ?? tipo;
}
